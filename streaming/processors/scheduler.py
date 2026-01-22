"""
Pipeline Scheduler
==================

Manages scheduled execution of data processing pipelines. Provides
a flexible scheduler that can run multiple pipelines at different
intervals with proper error handling and monitoring.

Features:
- Cron-like scheduling for pipelines
- Concurrent pipeline execution
- Error recovery and retry logic
- Health monitoring and metrics
- Graceful shutdown handling
"""

import logging
import asyncio
import signal
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from enum import Enum

logger = logging.getLogger(__name__)


class JobStatus(Enum):
    """Status of a scheduled job."""
    IDLE = "idle"
    RUNNING = "running"
    FAILED = "failed"
    DISABLED = "disabled"


@dataclass
class JobConfig:
    """
    Configuration for a scheduled job.
    
    Attributes:
        name: Unique job identifier
        interval_seconds: How often to run the job
        run_immediately: Whether to run on scheduler start
        max_retries: Number of retries on failure
        retry_delay_seconds: Delay between retries
        timeout_seconds: Maximum job execution time
        enabled: Whether the job is active
    """
    name: str
    interval_seconds: int
    run_immediately: bool = True
    max_retries: int = 3
    retry_delay_seconds: int = 30
    timeout_seconds: Optional[int] = None
    enabled: bool = True


@dataclass
class JobState:
    """Runtime state for a scheduled job."""
    config: JobConfig
    status: JobStatus = JobStatus.IDLE
    last_run: Optional[datetime] = None
    last_success: Optional[datetime] = None
    last_error: Optional[str] = None
    run_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    consecutive_failures: int = 0


class PipelineScheduler:
    """
    Scheduler for data processing pipelines.
    
    Manages the lifecycle of multiple pipeline jobs, ensuring they
    run at their configured intervals with proper error handling.
    
    Example Usage:
        # Create scheduler
        scheduler = PipelineScheduler()
        
        # Register pipelines
        scheduler.register_job(
            name="news_pipeline",
            callback=news_pipeline.run,
            interval_seconds=300,  # 5 minutes
        )
        
        scheduler.register_job(
            name="market_data",
            callback=market_pipeline.run,
            interval_seconds=60,  # 1 minute
        )
        
        # Start scheduler
        await scheduler.start()
        
        # Scheduler runs until stopped
        await scheduler.wait()
        
        # Or stop programmatically
        await scheduler.stop()
    """
    
    def __init__(self):
        """Initialize the scheduler."""
        self.jobs: Dict[str, JobState] = {}
        self.callbacks: Dict[str, Callable] = {}
        self._running = False
        self._tasks: Dict[str, asyncio.Task] = {}
        self._shutdown_event = asyncio.Event()
    
    def register_job(
        self,
        name: str,
        callback: Callable,
        interval_seconds: int,
        run_immediately: bool = True,
        max_retries: int = 3,
        timeout_seconds: Optional[int] = None,
        enabled: bool = True,
    ):
        """
        Register a pipeline job with the scheduler.
        
        Args:
            name: Unique job identifier
            callback: Async function to execute (should return metrics dict)
            interval_seconds: How often to run
            run_immediately: Run once immediately on start
            max_retries: Retry count on failure
            timeout_seconds: Maximum execution time
            enabled: Whether job is active
        """
        config = JobConfig(
            name=name,
            interval_seconds=interval_seconds,
            run_immediately=run_immediately,
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
            enabled=enabled,
        )
        
        self.jobs[name] = JobState(config=config)
        self.callbacks[name] = callback
        
        logger.info(f"Registered job: {name} (interval: {interval_seconds}s)")
    
    def enable_job(self, name: str):
        """Enable a disabled job."""
        if name in self.jobs:
            self.jobs[name].config.enabled = True
            self.jobs[name].status = JobStatus.IDLE
            logger.info(f"Enabled job: {name}")
    
    def disable_job(self, name: str):
        """Disable a job (stops running)."""
        if name in self.jobs:
            self.jobs[name].config.enabled = False
            self.jobs[name].status = JobStatus.DISABLED
            logger.info(f"Disabled job: {name}")
    
    async def start(self):
        """
        Start the scheduler.
        
        Begins running all enabled jobs at their configured intervals.
        """
        if self._running:
            logger.warning("Scheduler already running")
            return
        
        self._running = True
        self._shutdown_event.clear()
        
        logger.info(f"Starting scheduler with {len(self.jobs)} jobs")
        
        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()
        
        # Start job tasks
        for name, state in self.jobs.items():
            if state.config.enabled:
                task = asyncio.create_task(self._run_job_loop(name))
                self._tasks[name] = task
        
        logger.info("Scheduler started")
    
    async def stop(self):
        """
        Stop the scheduler gracefully.
        
        Waits for currently running jobs to complete before stopping.
        """
        if not self._running:
            return
        
        logger.info("Stopping scheduler...")
        self._running = False
        self._shutdown_event.set()
        
        # Cancel all job tasks
        for name, task in self._tasks.items():
            if not task.done():
                task.cancel()
        
        # Wait for tasks to complete
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        
        self._tasks.clear()
        logger.info("Scheduler stopped")
    
    async def wait(self):
        """Wait for the scheduler to stop (blocks until shutdown)."""
        await self._shutdown_event.wait()
    
    async def _run_job_loop(self, name: str):
        """
        Main loop for a single job.
        
        Handles scheduling, execution, and error recovery for one job.
        """
        state = self.jobs[name]
        callback = self.callbacks[name]
        config = state.config
        
        # Run immediately if configured
        if config.run_immediately:
            await self._execute_job(name, state, callback)
        
        # Main scheduling loop
        while self._running and config.enabled:
            try:
                # Wait for next interval
                await asyncio.sleep(config.interval_seconds)
                
                if not self._running or not config.enabled:
                    break
                
                # Execute job
                await self._execute_job(name, state, callback)
                
            except asyncio.CancelledError:
                logger.debug(f"Job {name} cancelled")
                break
            except Exception as e:
                logger.error(f"Unexpected error in job {name}: {e}")
    
    async def _execute_job(
        self,
        name: str,
        state: JobState,
        callback: Callable,
    ):
        """
        Execute a job with retry logic and timeout handling.
        """
        config = state.config
        
        for attempt in range(config.max_retries + 1):
            try:
                state.status = JobStatus.RUNNING
                state.last_run = datetime.utcnow()
                state.run_count += 1
                
                logger.info(f"Executing job: {name} (attempt {attempt + 1})")
                
                # Execute with optional timeout
                if config.timeout_seconds:
                    result = await asyncio.wait_for(
                        callback(),
                        timeout=config.timeout_seconds
                    )
                else:
                    result = await callback()
                
                # Success
                state.status = JobStatus.IDLE
                state.last_success = datetime.utcnow()
                state.success_count += 1
                state.consecutive_failures = 0
                state.last_error = None
                
                logger.info(f"Job {name} completed successfully")
                return result
                
            except asyncio.TimeoutError:
                error_msg = f"Job timed out after {config.timeout_seconds}s"
                logger.error(f"Job {name}: {error_msg}")
                state.last_error = error_msg
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Job {name} failed: {error_msg}")
                state.last_error = error_msg
            
            # Handle failure
            state.failure_count += 1
            state.consecutive_failures += 1
            
            # Retry if attempts remaining
            if attempt < config.max_retries:
                logger.info(f"Retrying job {name} in {config.retry_delay_seconds}s")
                await asyncio.sleep(config.retry_delay_seconds)
            else:
                state.status = JobStatus.FAILED
                logger.error(f"Job {name} failed after {config.max_retries + 1} attempts")
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        loop = asyncio.get_event_loop()
        
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(
                    sig,
                    lambda: asyncio.create_task(self.stop())
                )
            except NotImplementedError:
                # Windows doesn't support add_signal_handler
                pass
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get scheduler status for monitoring.
        
        Returns dict with overall status and per-job details.
        """
        job_statuses = {}
        for name, state in self.jobs.items():
            job_statuses[name] = {
                "status": state.status.value,
                "enabled": state.config.enabled,
                "interval_seconds": state.config.interval_seconds,
                "last_run": state.last_run.isoformat() if state.last_run else None,
                "last_success": state.last_success.isoformat() if state.last_success else None,
                "last_error": state.last_error,
                "run_count": state.run_count,
                "success_count": state.success_count,
                "failure_count": state.failure_count,
                "consecutive_failures": state.consecutive_failures,
            }
        
        return {
            "running": self._running,
            "job_count": len(self.jobs),
            "enabled_jobs": sum(1 for j in self.jobs.values() if j.config.enabled),
            "jobs": job_statuses,
        }
    
    async def run_job_now(self, name: str) -> Any:
        """
        Manually trigger a job execution.
        
        Useful for testing or manual intervention.
        """
        if name not in self.jobs:
            raise ValueError(f"Unknown job: {name}")
        
        state = self.jobs[name]
        callback = self.callbacks[name]
        
        return await self._execute_job(name, state, callback)

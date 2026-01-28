#!/usr/bin/env python3
"""
StartUpApplication - Complete Application Startup Script
=========================================================

This script orchestrates local startup of the AutoTrader AI stack (intended for bootstrapping a new machine):
1. (Optional) Clone or update the Git repository
2. Start the Docker Compose stack (infrastructure + web-app + api-gateway + ML services)
3. Run PostgreSQL migrations
4. Run basic smoke tests (API Gateway / Recommendation Engine / Web App)

Notes:
- The authoritative local stack is defined in infrastructure/docker/docker-compose.yml.
- Some optional services (e.g., Jim Cramer / Big Cap Losers) may require API keys via environment variables.
- Connector/API key checks are optional and can be skipped with --skip-tests.

Usage:
    python scripts/StartUpApplication.py
    python scripts/StartUpApplication.py --skip-docker
    python scripts/StartUpApplication.py --skip-tests
    python scripts/StartUpApplication.py --symbols AAPL,MSFT,GOOGL

Author: AutoTrader Team
"""

import asyncio
import subprocess
import sys
import os
import time
import json
import argparse
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum

# Add paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'ml-services'))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'streaming'))


class StepStatus(Enum):
    PENDING = "⏳"
    RUNNING = "🔄"
    SUCCESS = "✅"
    WARNING = "⚠️"
    FAILED = "❌"
    SKIPPED = "⏭️"


@dataclass
class StepResult:
    """Result of a startup step."""
    name: str
    status: StepStatus
    message: str
    duration_seconds: float = 0.0
    details: List[str] = field(default_factory=list)
    sub_results: List['StepResult'] = field(default_factory=list)


def _run(cmd: List[str], cwd: Optional[str] = None, env: Optional[Dict[str, str]] = None, timeout: int = 120) -> subprocess.CompletedProcess:
    """Run a command with good defaults."""
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, env=env, timeout=timeout)


def _which(cmd: str) -> bool:
    return subprocess.run(["bash", "-lc", f"command -v {cmd}"], capture_output=True, text=True).returncode == 0


def _is_git_repo(path: str) -> bool:
    return os.path.isdir(os.path.join(path, ".git"))


def _repo_looks_like_autotrader(path: str) -> bool:
    return os.path.exists(os.path.join(path, "infrastructure", "docker", "docker-compose.yml")) and os.path.exists(os.path.join(path, "web-app"))


class StartUpApplication:
    """Main startup orchestrator."""
    
    # Default watchlist symbols
    DEFAULT_WATCHLIST = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "META", 
        "NVDA", "TSLA", "JPM", "V", "JNJ"
    ]
    
    # Docker services to check. These should align with infrastructure/docker/docker-compose.yml
    # NOTE: We treat these as "must be running" for a healthy local environment.
    DOCKER_SERVICES = [
        "postgres",
        "redis",
        "kafka",
        "zookeeper",
        "clickhouse",
        "vault",
        "api-gateway",
        "recommendation-engine",
        "web-app",
        "news-ingestion",
        "connector-health",
        # Optional (started conditionally / best-effort)
        "jim-cramer-service",
        "big-cap-losers-service",
    ]
    
    # Data connectors to test
    DATA_CONNECTORS = [
        ("Polygon", "polygon"),
        ("NewsAPI", "newsapi"),
        ("Finnhub", "finnhub"),
        ("Benzinga", "benzinga"),
        ("FMP", "fmp"),
        ("Alpha Vantage", "alpha_vantage"),
    ]
    
    # LLM connectors to test
    LLM_CONNECTORS = [
        ("OpenAI", "openai"),
        ("Anthropic", "anthropic"),
        ("Groq", "groq"),
    ]
    
    def __init__(
        self,
        watchlist: List[str] = None,
        skip_docker: bool = False,
        skip_tests: bool = False,
        skip_news: bool = False,
        verbose: bool = True,
        repo_url: Optional[str] = None,
        branch: str = "main",
        target_dir: Optional[str] = None,
        fresh_clone: bool = False,
        skip_build: bool = False,
        prune_docker: bool = False,
    ):
        self.watchlist = watchlist or self.DEFAULT_WATCHLIST
        self.skip_docker = skip_docker
        self.skip_tests = skip_tests
        self.skip_news = skip_news
        self.verbose = verbose
        self.repo_url = repo_url
        self.branch = branch
        self.target_dir = target_dir
        self.fresh_clone = fresh_clone
        self.skip_build = skip_build
        self.prune_docker = prune_docker
        self.results: List[StepResult] = []
        self.start_time = None
        
    def log(self, message: str, level: str = "INFO"):
        """Log a message."""
        if self.verbose:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] {message}")
    
    def print_header(self):
        """Print startup header."""
        print("\n" + "=" * 70)
        print("🚀 AUTOTRADER APPLICATION STARTUP")
        print("=" * 70)
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Watchlist: {', '.join(self.watchlist)}")
        print("=" * 70 + "\n")
    
    def print_step(self, step_num: int, total: int, name: str):
        """Print step header."""
        print(f"\n{'─' * 70}")
        print(f"📌 Step {step_num}/{total}: {name}")
        print(f"{'─' * 70}")
    
    # =========================================================================
    # STEP 0: Prepare Repo (clone/pull)
    # =========================================================================

    async def step0_prepare_repo(self) -> StepResult:
        """Optional: clone/pull repo for fresh machine bootstrap."""
        start = time.time()

        if not self.repo_url:
            return StepResult(
                name="Prepare Repo",
                status=StepStatus.SKIPPED,
                message="No repo URL provided (assuming already in repo)",
                duration_seconds=time.time() - start,
            )

        if not _which('git'):
            return StepResult(
                name="Prepare Repo",
                status=StepStatus.FAILED,
                message="git is not installed (required for --repo-url)",
                duration_seconds=time.time() - start,
            )

        target = self.target_dir or os.path.join(os.path.expanduser('~'), 'autotrader-ai')

        try:
            # If we're already in the target and it looks correct, just pull.
            if _is_git_repo(target) and _repo_looks_like_autotrader(target) and not self.fresh_clone:
                self.log(f"Updating existing repo at {target}...")
                _run(["git", "fetch", "--all"], cwd=target, timeout=120)
                _run(["git", "checkout", self.branch], cwd=target, timeout=60)
                _run(["git", "pull"], cwd=target, timeout=120)
                return StepResult(
                    name="Prepare Repo",
                    status=StepStatus.SUCCESS,
                    message=f"Updated repo in {target} (branch: {self.branch})",
                    duration_seconds=time.time() - start,
                )

            # Fresh clone
            if os.path.exists(target) and self.fresh_clone:
                return StepResult(
                    name="Prepare Repo",
                    status=StepStatus.FAILED,
                    message=f"Target dir exists but --fresh-clone specified: {target} (please remove it)",
                    duration_seconds=time.time() - start,
                )

            self.log(f"Cloning repo from {self.repo_url} into {target}...")
            _run(["git", "clone", "--branch", self.branch, self.repo_url, target], timeout=300)

            return StepResult(
                name="Prepare Repo",
                status=StepStatus.SUCCESS,
                message=f"Cloned repo to {target} (branch: {self.branch})",
                duration_seconds=time.time() - start,
                details=[
                    "NOTE: If you ran this script from a different directory, re-run it from inside the cloned repo:",
                    f"  cd {target} && python3 scripts/StartUpApplication.py",
                ],
            )
        except subprocess.TimeoutExpired:
            return StepResult(
                name="Prepare Repo",
                status=StepStatus.FAILED,
                message="git operation timed out",
                duration_seconds=time.time() - start,
            )
        except Exception as e:
            return StepResult(
                name="Prepare Repo",
                status=StepStatus.FAILED,
                message=str(e)[:80],
                duration_seconds=time.time() - start,
            )

    # =========================================================================
    # STEP 1: Start Docker Containers
    # =========================================================================
    
    async def step1_start_docker_containers(self) -> StepResult:
        """Start all Docker containers."""
        start = time.time()
        sub_results = []
        
        if self.skip_docker:
            return StepResult(
                name="Start Docker Containers",
                status=StepStatus.SKIPPED,
                message="Skipped by user request",
                duration_seconds=0,
            )
        
        self.log("Starting Docker containers...")
        
        # Check if Docker is available
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                return StepResult(
                    name="Start Docker Containers",
                    status=StepStatus.FAILED,
                    message="Docker is not running or not available",
                    duration_seconds=time.time() - start,
                )
        except Exception as e:
            return StepResult(
                name="Start Docker Containers",
                status=StepStatus.FAILED,
                message=f"Docker check failed: {str(e)}",
                duration_seconds=time.time() - start,
            )
        
        # Start docker compose stack
        # Prefer `docker compose` (plugin) but fall back to legacy `docker-compose`.
        docker_compose_path = os.path.join(PROJECT_ROOT, "infrastructure", "docker", "docker-compose.yml")
        
        try:
            # Optional: free disk space proactively (helps on fresh machines)
            if self.prune_docker:
                self.log("Pruning unused Docker data (docker system prune -f)...")
                try:
                    _run(["docker", "system", "prune", "-f"], timeout=600)
                except Exception as e:
                    self.log(f"  ⚠️ docker prune failed: {e}")

            compose_bin = "docker-compose"
            if _which("docker"):
                # `docker compose` is preferred on newer installs
                try:
                    probe = subprocess.run(["docker", "compose", "version"], capture_output=True, text=True, timeout=5)
                    if probe.returncode == 0:
                        compose_bin = "docker"
                except Exception:
                    pass

            up_cmd = [compose_bin]
            if compose_bin == "docker":
                up_cmd += ["compose", "-f", docker_compose_path, "up", "-d"]
            else:
                up_cmd += ["-f", docker_compose_path, "up", "-d"]
            if not self.skip_build:
                # Ensure changes are built (recommendation-engine, api-gateway, web-app)
                up_cmd.append("--build")

            self.log(f"Running {' '.join(up_cmd)}...")
            result = subprocess.run(
                up_cmd,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=PROJECT_ROOT,
            )
            
            if result.returncode != 0:
                self.log(f"docker-compose stderr: {result.stderr}")
        except subprocess.TimeoutExpired:
            return StepResult(
                name="Start Docker Containers",
                status=StepStatus.FAILED,
                message="Docker compose timed out after 120 seconds",
                duration_seconds=time.time() - start,
            )
        except Exception as e:
            return StepResult(
                name="Start Docker Containers",
                status=StepStatus.FAILED,
                message=f"Docker compose failed: {str(e)}",
                duration_seconds=time.time() - start,
            )
        
        # Wait for containers to start and become healthy
        await asyncio.sleep(5)

        # Check each service (best-effort; some are optional)
        for service in self.DOCKER_SERVICES:
            status, msg = await self._check_docker_service(service)
            if service in ("jim-cramer-service", "big-cap-losers-service") and status == StepStatus.FAILED:
                status = StepStatus.SKIPPED
                msg = "Optional service not running"
            sub_results.append(StepResult(
                name=service,
                status=status,
                message=msg,
            ))
            self.log(f"  {status.value} {service}: {msg}")
        
        # Determine overall status
        failed = [r for r in sub_results if r.status == StepStatus.FAILED]
        if failed:
            overall_status = StepStatus.WARNING
            overall_message = f"{len(failed)}/{len(sub_results)} services failed to start"
        else:
            overall_status = StepStatus.SUCCESS
            overall_message = f"All {len(sub_results)} services started successfully"
        
        return StepResult(
            name="Start Docker Containers",
            status=overall_status,
            message=overall_message,
            duration_seconds=time.time() - start,
            sub_results=sub_results,
        )
    
    async def _check_docker_service(self, service: str) -> Tuple[StepStatus, str]:
        """Check if a Docker service is running."""
        try:
            result = subprocess.run(
                ["docker", "ps", "--filter", f"name={service}", "--format", "{{.Status}}"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            status = result.stdout.strip()
            if "Up" in status:
                return StepStatus.SUCCESS, f"Running ({status})"
            elif status:
                return StepStatus.WARNING, f"Status: {status}"
            else:
                return StepStatus.FAILED, "Not running"
        except Exception as e:
            return StepStatus.FAILED, str(e)
    
    # =========================================================================
    # STEP 1.5: Run DB Migrations (Postgres)
    # =========================================================================

    async def step1_5_run_db_migrations(self) -> StepResult:
        start = time.time()

        migrate_script = os.path.join(PROJECT_ROOT, "database", "postgres", "migrate.sh")
        if not os.path.exists(migrate_script):
            return StepResult(
                name="Run DB Migrations",
                status=StepStatus.WARNING,
                message="Migration script not found (skipping)",
                duration_seconds=time.time() - start,
            )

        try:
            self.log("Running PostgreSQL migrations...")
            result = _run(["bash", migrate_script], cwd=os.path.dirname(migrate_script), timeout=300)
            if result.returncode != 0:
                return StepResult(
                    name="Run DB Migrations",
                    status=StepStatus.WARNING,
                    message=f"Migrations returned non-zero exit code: {result.returncode}",
                    duration_seconds=time.time() - start,
                    details=[result.stdout[-500:], result.stderr[-500:]],
                )
            return StepResult(
                name="Run DB Migrations",
                status=StepStatus.SUCCESS,
                message="Migrations applied",
                duration_seconds=time.time() - start,
            )
        except subprocess.TimeoutExpired:
            return StepResult(
                name="Run DB Migrations",
                status=StepStatus.FAILED,
                message="Migration timed out",
                duration_seconds=time.time() - start,
            )
        except Exception as e:
            return StepResult(
                name="Run DB Migrations",
                status=StepStatus.FAILED,
                message=str(e)[:80],
                duration_seconds=time.time() - start,
            )

    # =========================================================================
    # STEP 2: Verify and Fix Services
    # =========================================================================
    
    async def step2_verify_and_fix_services(self) -> StepResult:
        """Verify services are accessible and fix issues."""
        start = time.time()
        sub_results = []
        fixes_applied = []
        
        self.log("Verifying service connectivity...")
        
        # Check PostgreSQL
        pg_status, pg_msg, pg_fix = await self._check_postgres()
        sub_results.append(StepResult(name="PostgreSQL", status=pg_status, message=pg_msg))
        if pg_fix:
            fixes_applied.append(pg_fix)
        self.log(f"  {pg_status.value} PostgreSQL: {pg_msg}")
        
        # Check ClickHouse
        ch_status, ch_msg, ch_fix = await self._check_clickhouse()
        sub_results.append(StepResult(name="ClickHouse", status=ch_status, message=ch_msg))
        if ch_fix:
            fixes_applied.append(ch_fix)
        self.log(f"  {ch_status.value} ClickHouse: {ch_msg}")
        
        # Check Vault
        vault_status, vault_msg, vault_fix = await self._check_vault()
        sub_results.append(StepResult(name="Vault", status=vault_status, message=vault_msg))
        if vault_fix:
            fixes_applied.append(vault_fix)
        self.log(f"  {vault_status.value} Vault: {vault_msg}")
        
        # Check Redis
        redis_status, redis_msg, redis_fix = await self._check_redis()
        sub_results.append(StepResult(name="Redis", status=redis_status, message=redis_msg))
        if redis_fix:
            fixes_applied.append(redis_fix)
        self.log(f"  {redis_status.value} Redis: {redis_msg}")
        
        failed = [r for r in sub_results if r.status == StepStatus.FAILED]
        if failed:
            overall_status = StepStatus.WARNING
            overall_message = f"{len(failed)}/{len(sub_results)} services have issues"
        else:
            overall_status = StepStatus.SUCCESS
            overall_message = "All services verified"
        
        if fixes_applied:
            overall_message += f" ({len(fixes_applied)} fixes applied)"
        
        return StepResult(
            name="Verify and Fix Services",
            status=overall_status,
            message=overall_message,
            duration_seconds=time.time() - start,
            sub_results=sub_results,
            details=fixes_applied,
        )
    
    async def _check_postgres(self) -> Tuple[StepStatus, str, Optional[str]]:
        """Check PostgreSQL connectivity."""
        try:
            import asyncpg
            conn = await asyncpg.connect(
                host=os.getenv("POSTGRES_HOST", "localhost"),
                port=int(os.getenv("POSTGRES_PORT", "5432")),
                user=os.getenv("POSTGRES_USER", "autotrader"),
                password=os.getenv("POSTGRES_PASSWORD", "autotrader_dev_pass"),
                database=os.getenv("POSTGRES_DATABASE", "autotrader"),
                timeout=5,
            )
            await conn.close()
            return StepStatus.SUCCESS, "Connected successfully", None
        except ImportError:
            return StepStatus.WARNING, "asyncpg not installed", None
        except Exception as e:
            error = str(e)[:50]
            if "connection refused" in error.lower():
                return StepStatus.FAILED, f"Connection refused - service may not be running", None
            return StepStatus.FAILED, error, None
    
    async def _check_clickhouse(self) -> Tuple[StepStatus, str, Optional[str]]:
        """Check ClickHouse connectivity."""
        try:
            import clickhouse_connect
            client = clickhouse_connect.get_client(
                host='localhost',
                port=8123,
                username='default',
                password='clickhouse_dev_pass',
            )
            result = client.query("SELECT 1")
            client.close()
            return StepStatus.SUCCESS, "Connected successfully", None
        except ImportError:
            return StepStatus.WARNING, "clickhouse-connect not installed", None
        except Exception as e:
            return StepStatus.FAILED, str(e)[:50], None
    
    async def _check_vault(self) -> Tuple[StepStatus, str, Optional[str]]:
        """Check Vault connectivity."""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get("http://localhost:8200/v1/sys/health", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status in (200, 429, 472, 473, 501, 503):
                        return StepStatus.SUCCESS, f"Responding (status: {resp.status})", None
                    return StepStatus.WARNING, f"Unexpected status: {resp.status}", None
        except ImportError:
            return StepStatus.WARNING, "aiohttp not installed", None
        except Exception as e:
            return StepStatus.FAILED, str(e)[:50], None
    
    async def _check_redis(self) -> Tuple[StepStatus, str, Optional[str]]:
        """Check Redis connectivity."""
        try:
            import redis
            r = redis.Redis(host='localhost', port=6379, socket_connect_timeout=5)
            r.ping()
            r.close()
            return StepStatus.SUCCESS, "Connected successfully", None
        except ImportError:
            return StepStatus.WARNING, "redis not installed", None
        except Exception as e:
            return StepStatus.FAILED, str(e)[:50], None
    
    # =========================================================================
    # STEP 3: Test Data Connectors
    # =========================================================================
    
    async def step3_test_data_connectors(self) -> StepResult:
        """Test all data source connectors."""
        start = time.time()
        sub_results = []
        
        if self.skip_tests:
            return StepResult(
                name="Test Data Connectors",
                status=StepStatus.SKIPPED,
                message="Skipped by user request",
                duration_seconds=0,
            )
        
        self.log("Testing data connectors...")
        
        from vault_client import VaultClient
        
        vault_client = VaultClient()
        
        for name, key_name in self.DATA_CONNECTORS:
            try:
                secret = await vault_client.get_secret(key_name)
                api_key = secret.get('api_key') if secret else None
                
                if not api_key:
                    sub_results.append(StepResult(
                        name=name,
                        status=StepStatus.WARNING,
                        message="No API key configured",
                    ))
                    self.log(f"  ⚠️ {name}: No API key configured")
                    continue
                
                status, msg = await self._test_data_connector(name, api_key)
                sub_results.append(StepResult(name=name, status=status, message=msg))
                self.log(f"  {status.value} {name}: {msg}")
                
            except Exception as e:
                sub_results.append(StepResult(
                    name=name,
                    status=StepStatus.FAILED,
                    message=str(e)[:50],
                ))
                self.log(f"  ❌ {name}: {str(e)[:50]}")
        
        await vault_client.close()
        
        working = [r for r in sub_results if r.status == StepStatus.SUCCESS]
        failed = [r for r in sub_results if r.status == StepStatus.FAILED]
        
        if len(working) == 0:
            overall_status = StepStatus.FAILED
            overall_message = "No data connectors working"
        elif failed:
            overall_status = StepStatus.WARNING
            overall_message = f"{len(working)}/{len(sub_results)} connectors working"
        else:
            overall_status = StepStatus.SUCCESS
            overall_message = f"All {len(working)} connectors working"
        
        return StepResult(
            name="Test Data Connectors",
            status=overall_status,
            message=overall_message,
            duration_seconds=time.time() - start,
            sub_results=sub_results,
        )
    
    async def _test_data_connector(self, name: str, api_key: str) -> Tuple[StepStatus, str]:
        """Test a specific data connector."""
        import aiohttp
        
        test_urls = {
            "Polygon": f"https://api.massive.com/v2/aggs/ticker/AAPL/range/1/day/2026-01-15/2026-01-21?apiKey={api_key}&limit=1",
            "NewsAPI": f"https://newsapi.org/v2/everything?q=stocks&pageSize=1&apiKey={api_key}",
            "Finnhub": f"https://finnhub.io/api/v1/news?category=general&token={api_key}",
            "Benzinga": f"https://api.benzinga.com/api/v2/news?token={api_key}&pageSize=1",
            "FMP": f"https://financialmodelingprep.com/stable/quote-short?symbol=AAPL&apikey={api_key}",
            "Alpha Vantage": f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=AAPL&apikey={api_key}",
        }
        
        url = test_urls.get(name)
        if not url:
            return StepStatus.WARNING, "No test URL configured"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 200:
                        return StepStatus.SUCCESS, f"HTTP 200 OK"
                    elif resp.status == 429:
                        return StepStatus.WARNING, "Rate limited (429)"
                    elif resp.status == 402:
                        return StepStatus.WARNING, "Subscription required (402)"
                    else:
                        return StepStatus.FAILED, f"HTTP {resp.status}"
        except asyncio.TimeoutError:
            return StepStatus.FAILED, "Request timed out"
        except Exception as e:
            return StepStatus.FAILED, str(e)[:30]
    
    # =========================================================================
    # STEP 4: Test LLM Connectors
    # =========================================================================
    
    async def step4_test_llm_connectors(self) -> StepResult:
        """Test all LLM connectors."""
        start = time.time()
        sub_results = []
        
        if self.skip_tests:
            return StepResult(
                name="Test LLM Connectors",
                status=StepStatus.SKIPPED,
                message="Skipped by user request",
                duration_seconds=0,
            )
        
        self.log("Testing LLM connectors...")
        
        from vault_client import VaultClient
        vault_client = VaultClient()
        
        for name, key_name in self.LLM_CONNECTORS:
            try:
                secret = await vault_client.get_secret(key_name)
                api_key = secret.get('api_key') if secret else None
                
                if not api_key:
                    sub_results.append(StepResult(
                        name=name,
                        status=StepStatus.WARNING,
                        message="No API key configured",
                    ))
                    self.log(f"  ⚠️ {name}: No API key configured")
                    continue
                
                status, msg = await self._test_llm_connector(name, api_key)
                sub_results.append(StepResult(name=name, status=status, message=msg))
                self.log(f"  {status.value} {name}: {msg}")
                
            except Exception as e:
                sub_results.append(StepResult(
                    name=name,
                    status=StepStatus.FAILED,
                    message=str(e)[:50],
                ))
                self.log(f"  ❌ {name}: {str(e)[:50]}")
        
        await vault_client.close()
        
        working = [r for r in sub_results if r.status == StepStatus.SUCCESS]
        
        if len(working) == 0:
            overall_status = StepStatus.FAILED
            overall_message = "No LLM connectors working"
        elif len(working) < len(sub_results):
            overall_status = StepStatus.WARNING
            overall_message = f"{len(working)}/{len(sub_results)} LLM connectors working"
        else:
            overall_status = StepStatus.SUCCESS
            overall_message = f"All {len(working)} LLM connectors working"
        
        return StepResult(
            name="Test LLM Connectors",
            status=overall_status,
            message=overall_message,
            duration_seconds=time.time() - start,
            sub_results=sub_results,
        )
    
    async def _test_llm_connector(self, name: str, api_key: str) -> Tuple[StepStatus, str]:
        """Test a specific LLM connector."""
        try:
            if name == "OpenAI":
                from openai import AsyncOpenAI
                client = AsyncOpenAI(api_key=api_key)
                await client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": "Say 'OK'"}],
                    max_tokens=5,
                )
                return StepStatus.SUCCESS, f"Working (gpt-4o-mini)"
                
            elif name == "Anthropic":
                from anthropic import AsyncAnthropic
                client = AsyncAnthropic(api_key=api_key)
                await client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=5,
                    messages=[{"role": "user", "content": "Say 'OK'"}],
                )
                return StepStatus.SUCCESS, f"Working (claude-3-haiku)"
                
            elif name == "Groq":
                from groq import AsyncGroq
                client = AsyncGroq(api_key=api_key)
                await client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "user", "content": "Say 'OK'"}],
                    max_tokens=5,
                )
                return StepStatus.SUCCESS, f"Working (llama-3.1-8b)"
            
            return StepStatus.WARNING, "Unknown provider"
            
        except Exception as e:
            error = str(e).lower()
            if "quota" in error or "rate" in error:
                return StepStatus.WARNING, "Rate/quota limited"
            elif "unauthorized" in error or "invalid" in error:
                return StepStatus.FAILED, "Invalid API key"
            return StepStatus.FAILED, str(e)[:40]
    
    # =========================================================================
    # STEP 5: Run Recommendations for Watchlist
    # =========================================================================
    
    async def step5_run_recommendations(self) -> StepResult:
        """(Optional) Run recommendations for all watchlist symbols.

        NOTE: For fresh machine bootstrap, prefer using the running recommendation-engine HTTP API.
        This avoids needing local Python deps to import the engine.
        """
        start = time.time()
        sub_results = []
        recommendations = []
        
        self.log(f"Running recommendations for {len(self.watchlist)} symbols...")
        
        # Set ClickHouse environment variables
        os.environ['CLICKHOUSE_HOST'] = 'localhost'
        os.environ['CLICKHOUSE_PORT'] = '8123'
        os.environ['CLICKHOUSE_USER'] = 'default'
        os.environ['CLICKHOUSE_PASSWORD'] = 'clickhouse_dev_pass'
        
        try:
            import aiohttp

            # Use api-gateway on-demand endpoint (does NOT persist to DB) as a smoke test.
            # This validates recommendation-engine is healthy and can generate for symbols.
            async with aiohttp.ClientSession() as session:
                for symbol in self.watchlist:
                    try:
                        self.log(f"  Generating on-demand recommendation for {symbol} via API...")
                        async with session.post(
                            "http://localhost:3001/api/v1/recommendations/on-demand",
                            json={"symbol": symbol, "companyName": symbol},
                            timeout=aiohttp.ClientTimeout(total=60),
                        ) as resp:
                            if resp.status != 200:
                                body = await resp.text()
                                raise RuntimeError(f"HTTP {resp.status}: {body[:120]}")
                            data = await resp.json()
                            sub_results.append(StepResult(
                                name=symbol,
                                status=StepStatus.SUCCESS,
                                message=f"{data.get('action')} (score: {data.get('score')}, conf: {data.get('confidence')})",
                            ))
                    except Exception as e:
                        sub_results.append(StepResult(
                            name=symbol,
                            status=StepStatus.WARNING,
                            message=str(e)[:80],
                        ))

        except ImportError:
            return StepResult(
                name="Run Recommendations",
                status=StepStatus.WARNING,
                message="aiohttp not installed; skipping recommendation smoke test",
                duration_seconds=time.time() - start,
            )
        except Exception as e:
            return StepResult(
                name="Run Recommendations",
                status=StepStatus.WARNING,
                message=f"Recommendation smoke test failed: {str(e)[:80]}",
                duration_seconds=time.time() - start,
            )
        
        successful = [r for r in sub_results if r.status == StepStatus.SUCCESS]
        
        if len(successful) == 0:
            overall_status = StepStatus.FAILED
            overall_message = "No recommendations generated"
        elif len(successful) < len(self.watchlist):
            overall_status = StepStatus.WARNING
            overall_message = f"{len(successful)}/{len(self.watchlist)} recommendations generated"
        else:
            overall_status = StepStatus.SUCCESS
            overall_message = f"All {len(successful)} recommendations generated"
        
        return StepResult(
            name="Run Recommendations",
            status=overall_status,
            message=overall_message,
            duration_seconds=time.time() - start,
            sub_results=sub_results,
            details=[f"{r.symbol}: {r.action}" for r in recommendations],
        )
    
    async def _store_recommendations(self, recommendations: List):
        """Store recommendations in PostgreSQL using the full schema."""
        if not recommendations:
            return
        
        try:
            import asyncpg
            import json
            
            # Get credentials from environment or use defaults
            pg_host = os.getenv("POSTGRES_HOST", "localhost")
            pg_port = int(os.getenv("POSTGRES_PORT", "5432"))
            pg_user = os.getenv("POSTGRES_USER", "autotrader")
            pg_password = os.getenv("POSTGRES_PASSWORD", "autotrader_dev_pass")
            pg_database = os.getenv("POSTGRES_DATABASE", "autotrader")
            
            conn = await asyncpg.connect(
                host=pg_host,
                port=pg_port,
                user=pg_user,
                password=pg_password,
                database=pg_database,
            )
            
            # Insert recommendations using the schema from V5__stock_recommendations.sql
            insert_sql = """
                INSERT INTO stock_recommendations (
                    symbol, action, score, normalized_score, confidence, 
                    price_at_recommendation, news_sentiment_score, news_momentum_score,
                    technical_trend_score, technical_momentum_score, rsi, macd_histogram,
                    price_vs_sma20, news_sentiment_1d, article_count_24h, explanation,
                    generated_at, data_sources_used
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
            """
            
            for rec in recommendations:
                # Handle explanation - could be string or dict
                explanation = rec.explanation
                if isinstance(explanation, dict):
                    explanation = json.dumps(explanation)
                elif not isinstance(explanation, str):
                    explanation = str(explanation) if explanation else ""
                
                await conn.execute(
                    insert_sql,
                    rec.symbol,
                    rec.action,
                    float(rec.score) if rec.score is not None else None,
                    float(rec.normalized_score) if rec.normalized_score is not None else None,
                    float(rec.confidence) if rec.confidence is not None else None,
                    float(rec.price_at_recommendation) if rec.price_at_recommendation is not None else None,
                    float(rec.news_sentiment_score) if rec.news_sentiment_score is not None else None,
                    float(rec.news_momentum_score) if rec.news_momentum_score is not None else None,
                    float(rec.technical_trend_score) if rec.technical_trend_score is not None else None,
                    float(rec.technical_momentum_score) if rec.technical_momentum_score is not None else None,
                    float(rec.rsi) if rec.rsi is not None else None,
                    float(rec.macd_histogram) if rec.macd_histogram is not None else None,
                    float(rec.price_vs_sma20) if rec.price_vs_sma20 is not None else None,
                    float(rec.news_sentiment_1d) if rec.news_sentiment_1d is not None else None,
                    int(rec.article_count_24h) if rec.article_count_24h is not None else None,
                    explanation[:2000] if explanation else "",  # Limit length
                    rec.generated_at,
                    rec.data_sources_used if hasattr(rec, 'data_sources_used') and rec.data_sources_used else [],
                )
            
            await conn.close()
            
            self.log(f"  ✅ Stored {len(recommendations)} recommendations in database")
            
        except ImportError:
            self.log("  ⚠️ asyncpg not installed - skipping database storage")
        except Exception as e:
            import traceback
            self.log(f"  ⚠️ Failed to store recommendations: {str(e)}")
            self.log(f"      {traceback.format_exc()[:200]}")
    
    # =========================================================================
    # STEP 6: Start News Sentiment Service
    # =========================================================================
    
    async def step6_start_news_sentiment_service(self) -> StepResult:
        """Start the news ingestion service with sentiment analysis."""
        start = time.time()
        
        if self.skip_news:
            return StepResult(
                name="News Sentiment Service",
                status=StepStatus.SKIPPED,
                message="Skipped by user request",
                duration_seconds=0,
            )
        
        self.log("Starting News Sentiment Service...")
        
        try:
            # Import and initialize the news ingestion service
            news_service_path = os.path.join(PROJECT_ROOT, 'ml-services')
            sys.path.insert(0, news_service_path)
            
            from news_ingestion_service import NewsIngestionService
            
            # Set ClickHouse environment variables
            os.environ['CLICKHOUSE_HOST'] = 'localhost'
            os.environ['CLICKHOUSE_PORT'] = '8123'
            os.environ['CLICKHOUSE_USER'] = 'default'
            os.environ['CLICKHOUSE_PASSWORD'] = 'clickhouse_dev_pass'
            
            # Create and initialize service
            service = NewsIngestionService(
                symbols=self.watchlist,
                clickhouse_host='localhost',
                clickhouse_port=8123,
                clickhouse_user='default',
                clickhouse_password='clickhouse_dev_pass',
                enable_sentiment=True,
            )
            
            self.log("  Initializing connectors and sentiment analyzer...")
            await service.initialize()
            
            # Run one ingestion cycle
            self.log("  Fetching news and analyzing sentiment...")
            result = await service.run_once()
            
            articles_processed = result.get('articles_processed', 0)
            duration = result.get('duration_seconds', 0)
            
            # Close service
            await service.close()
            
            if articles_processed > 0:
                return StepResult(
                    name="News Sentiment Service",
                    status=StepStatus.SUCCESS,
                    message=f"Processed {articles_processed} articles with sentiment analysis",
                    duration_seconds=time.time() - start,
                    details=[
                        f"Articles processed: {articles_processed}",
                        f"Symbols tracked: {', '.join(self.watchlist)}",
                        f"Processing time: {duration:.1f}s",
                    ],
                )
            else:
                return StepResult(
                    name="News Sentiment Service",
                    status=StepStatus.WARNING,
                    message="No new articles found (may be duplicates)",
                    duration_seconds=time.time() - start,
                )
                
        except ImportError as e:
            self.log(f"  ⚠️ News ingestion service not available: {e}")
            return StepResult(
                name="News Sentiment Service",
                status=StepStatus.WARNING,
                message=f"Service not available: {str(e)[:40]}",
                duration_seconds=time.time() - start,
            )
        except Exception as e:
            import traceback
            self.log(f"  ❌ News sentiment service failed: {e}")
            self.log(f"      {traceback.format_exc()[:200]}")
            return StepResult(
                name="News Sentiment Service",
                status=StepStatus.FAILED,
                message=str(e)[:50],
                duration_seconds=time.time() - start,
            )
    
    # =========================================================================
    # STEP 7: Start Jim Cramer Service
    # =========================================================================
    
    async def step7_start_jim_cramer_service(self) -> StepResult:
        """Start the Jim Cramer service with GROQ API key from Vault."""
        start = time.time()
        
        self.log("Starting Jim Cramer Service...")
        
        try:
            # Get GROQ API key from Vault
            self.log("  Retrieving GROQ API key from Vault...")
            result = subprocess.run(
                ["docker", "exec", "autotrader-vault", "sh", "-c",
                 "VAULT_TOKEN=dev-root-token vault kv get -field=api_key secret/autotrader/config/groq"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            
            groq_api_key = result.stdout.strip()
            if not groq_api_key:
                return StepResult(
                    name="Jim Cramer Service",
                    status=StepStatus.WARNING,
                    message="Could not retrieve GROQ API key from Vault",
                    duration_seconds=time.time() - start,
                )
            
            self.log("  ✅ GROQ API key retrieved")
            
            # Set environment variable and start the service
            os.environ['GROQ_API_KEY'] = groq_api_key
            
            docker_compose_path = os.path.join(PROJECT_ROOT, "infrastructure", "docker", "docker-compose.yml")
            
            self.log("  Starting Jim Cramer container...")
            result = subprocess.run(
                ["docker-compose", "-f", docker_compose_path, "up", "-d", "--build", "jim-cramer-service"],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=PROJECT_ROOT,
                env={**os.environ, 'GROQ_API_KEY': groq_api_key},
            )
            
            if result.returncode != 0:
                self.log(f"  ⚠️ docker-compose stderr: {result.stderr[:200]}")
            
            # Wait for container to start and check logs
            await asyncio.sleep(5)
            
            # Check if container is running
            check_result = subprocess.run(
                ["docker", "logs", "--tail", "10", "autotrader-jim-cramer"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            
            logs = check_result.stdout + check_result.stderr
            
            if "JIM CRAMER SERVICE - SCHEDULED MODE" in logs:
                # Check if GROQ is configured
                if "providers: ['groq']" in logs or "providers: [\"groq\"]" in logs:
                    return StepResult(
                        name="Jim Cramer Service",
                        status=StepStatus.SUCCESS,
                        message="Started with GROQ LLM provider (runs daily at 9 AM PST)",
                        duration_seconds=time.time() - start,
                        details=[
                            "GROQ API key configured from Vault",
                            "Scheduled to run daily at 9:00 AM PST (17:00 UTC)",
                            "View logs: docker logs -f autotrader-jim-cramer",
                        ],
                    )
                else:
                    return StepResult(
                        name="Jim Cramer Service",
                        status=StepStatus.WARNING,
                        message="Started but GROQ not detected in logs",
                        duration_seconds=time.time() - start,
                    )
            else:
                return StepResult(
                    name="Jim Cramer Service",
                    status=StepStatus.WARNING,
                    message="Container started but service mode not confirmed",
                    duration_seconds=time.time() - start,
                )
                
        except subprocess.TimeoutExpired:
            return StepResult(
                name="Jim Cramer Service",
                status=StepStatus.FAILED,
                message="Timed out starting service",
                duration_seconds=time.time() - start,
            )
        except Exception as e:
            return StepResult(
                name="Jim Cramer Service",
                status=StepStatus.FAILED,
                message=str(e)[:50],
                duration_seconds=time.time() - start,
            )
    
    # =========================================================================
    # STEP 8: Start Big Cap Losers Service
    # =========================================================================
    
    async def step8_start_big_cap_losers_service(self) -> StepResult:
        """Start the Big Cap Losers service with HTTP server."""
        start = time.time()
        
        self.log("Starting Big Cap Losers Service...")
        
        try:
            docker_compose_path = os.path.join(PROJECT_ROOT, "infrastructure", "docker", "docker-compose.yml")
            
            self.log("  Starting Big Cap Losers container...")
            result = subprocess.run(
                ["docker-compose", "-f", docker_compose_path, "up", "-d", "--build", "big-cap-losers-service"],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=PROJECT_ROOT,
            )
            
            if result.returncode != 0:
                self.log(f"  ⚠️ docker-compose stderr: {result.stderr[:200]}")
            
            # Wait for container to start
            await asyncio.sleep(5)
            
            # Check if HTTP server is responding
            import aiohttp
            try:
                async with aiohttp.ClientSession() as session:
                    # Try to reach the health endpoint
                    async with session.get(
                        "http://localhost:8001/health",
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as resp:
                        if resp.status == 200:
                            return StepResult(
                                name="Big Cap Losers Service",
                                status=StepStatus.SUCCESS,
                                message="Started with HTTP server on port 8001",
                                duration_seconds=time.time() - start,
                                details=[
                                    "HTTP server running on port 8001",
                                    "Crawls Yahoo Finance every 1 hour",
                                    "Refresh endpoint: POST /refresh",
                                    "Health check: GET /health",
                                ],
                            )
            except Exception as e:
                self.log(f"  ⚠️ HTTP health check failed: {e}")
            
            # Check container logs as fallback
            check_result = subprocess.run(
                ["docker", "logs", "--tail", "10", "autotrader-big-cap-losers"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            
            logs = check_result.stdout + check_result.stderr
            
            if "HTTP server listening" in logs or "listening on port" in logs.lower():
                return StepResult(
                    name="Big Cap Losers Service",
                    status=StepStatus.SUCCESS,
                    message="Started (HTTP server detected in logs)",
                    duration_seconds=time.time() - start,
                )
            elif "BIG CAP LOSERS" in logs.upper():
                return StepResult(
                    name="Big Cap Losers Service",
                    status=StepStatus.WARNING,
                    message="Container running but HTTP server not confirmed",
                    duration_seconds=time.time() - start,
                )
            else:
                return StepResult(
                    name="Big Cap Losers Service",
                    status=StepStatus.WARNING,
                    message="Container started but service not confirmed",
                    duration_seconds=time.time() - start,
                )
                
        except subprocess.TimeoutExpired:
            return StepResult(
                name="Big Cap Losers Service",
                status=StepStatus.FAILED,
                message="Timed out starting service",
                duration_seconds=time.time() - start,
            )
        except Exception as e:
            return StepResult(
                name="Big Cap Losers Service",
                status=StepStatus.FAILED,
                message=str(e)[:50],
                duration_seconds=time.time() - start,
            )
    
    # =========================================================================
    # STEP 9: Start API Gateway
    # =========================================================================
    
    async def step9_start_api_gateway(self) -> StepResult:
        """Start the API Gateway service."""
        start = time.time()
        
        self.log("Starting API Gateway...")
        
        try:
            docker_compose_path = os.path.join(PROJECT_ROOT, "infrastructure", "docker", "docker-compose.yml")
            
            self.log("  Starting API Gateway container...")
            result = subprocess.run(
                ["docker-compose", "-f", docker_compose_path, "up", "-d", "api-gateway"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=PROJECT_ROOT,
            )
            
            if result.returncode != 0:
                self.log(f"  ⚠️ docker-compose stderr: {result.stderr[:200]}")
            
            # Wait for service to start
            await asyncio.sleep(3)
            
            # Check if API Gateway is responding
            import aiohttp
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        "http://localhost:3001/health",
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as resp:
                        if resp.status == 200:
                            return StepResult(
                                name="API Gateway",
                                status=StepStatus.SUCCESS,
                                message="Running on port 3001",
                                duration_seconds=time.time() - start,
                                details=[
                                    "API Gateway: http://localhost:3001",
                                    "Health check: http://localhost:3001/health",
                                ],
                            )
                        else:
                            return StepResult(
                                name="API Gateway",
                                status=StepStatus.WARNING,
                                message=f"Responding with status {resp.status}",
                                duration_seconds=time.time() - start,
                            )
            except Exception as e:
                return StepResult(
                    name="API Gateway",
                    status=StepStatus.WARNING,
                    message=f"Health check failed: {str(e)[:30]}",
                    duration_seconds=time.time() - start,
                )
                
        except subprocess.TimeoutExpired:
            return StepResult(
                name="API Gateway",
                status=StepStatus.FAILED,
                message="Timed out starting service",
                duration_seconds=time.time() - start,
            )
        except Exception as e:
            return StepResult(
                name="API Gateway",
                status=StepStatus.FAILED,
                message=str(e)[:50],
                duration_seconds=time.time() - start,
            )
    
    # =========================================================================
    # STEP 10: Smoke test core services (compose stack)
    # =========================================================================

    async def step10_smoke_test_services(self) -> StepResult:
        """Smoke test key HTTP endpoints.

        We intentionally keep this lightweight and avoid requiring local dependencies.
        """
        start = time.time()
        sub_results: List[StepResult] = []

        try:
            import aiohttp
        except ImportError:
            return StepResult(
                name="Smoke Test Services",
                status=StepStatus.WARNING,
                message="aiohttp not installed; skipping HTTP smoke tests",
                duration_seconds=time.time() - start,
            )

        async with aiohttp.ClientSession() as session:
            # API Gateway
            try:
                async with session.get("http://localhost:3001/health", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        sub_results.append(StepResult("api-gateway /health", StepStatus.SUCCESS, "OK"))
                    else:
                        sub_results.append(StepResult("api-gateway /health", StepStatus.WARNING, f"HTTP {resp.status}"))
            except Exception as e:
                sub_results.append(StepResult("api-gateway /health", StepStatus.FAILED, str(e)[:80]))

            # Recommendation Engine
            try:
                async with session.get("http://localhost:8000/health", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        sub_results.append(StepResult("recommendation-engine /health", StepStatus.SUCCESS, "OK"))
                    else:
                        sub_results.append(StepResult("recommendation-engine /health", StepStatus.WARNING, f"HTTP {resp.status}"))
            except Exception as e:
                sub_results.append(StepResult("recommendation-engine /health", StepStatus.FAILED, str(e)[:80]))

            # Web App
            try:
                async with session.get("http://localhost:5173/", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status in (200, 304):
                        sub_results.append(StepResult("web-app /", StepStatus.SUCCESS, "OK"))
                    else:
                        sub_results.append(StepResult("web-app /", StepStatus.WARNING, f"HTTP {resp.status}"))
            except Exception as e:
                sub_results.append(StepResult("web-app /", StepStatus.FAILED, str(e)[:80]))

        failed = [r for r in sub_results if r.status == StepStatus.FAILED]
        warning = [r for r in sub_results if r.status == StepStatus.WARNING]
        if failed:
            status = StepStatus.WARNING
            message = f"{len(failed)}/{len(sub_results)} smoke checks failed"
        elif warning:
            status = StepStatus.WARNING
            message = f"{len(warning)}/{len(sub_results)} smoke checks returned warnings"
        else:
            status = StepStatus.SUCCESS
            message = "All smoke checks passed"

        return StepResult(
            name="Smoke Test Services",
            status=status,
            message=message,
            duration_seconds=time.time() - start,
            sub_results=sub_results,
        )

    # =========================================================================
    # (Legacy) STEP 10: Start Frontend (Web App)
    # =========================================================================
    
    async def step10_start_frontend(self) -> StepResult:
        """(Deprecated) Previously started the frontend locally via npm.

        The recommended local setup runs the web app via Docker Compose (service: web-app).
        """
        start = time.time()
        
        self.log("Starting Frontend (Web App)...")
        
        try:
            # Check if npm/node is available
            node_paths = [
                os.path.expanduser("~/.nvm/versions/node/v20.16.0/bin"),
                "/usr/local/bin",
                "/usr/bin",
            ]
            
            npm_path = None
            for path in node_paths:
                potential_npm = os.path.join(path, "npm")
                if os.path.exists(potential_npm):
                    npm_path = potential_npm
                    os.environ['PATH'] = f"{path}:{os.environ.get('PATH', '')}"
                    break
            
            if not npm_path:
                # Try Docker-based frontend
                self.log("  npm not found locally, trying Docker...")
                docker_compose_path = os.path.join(PROJECT_ROOT, "infrastructure", "docker", "docker-compose.yml")
                
                result = subprocess.run(
                    ["docker-compose", "-f", docker_compose_path, "up", "-d", "web-app"],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    cwd=PROJECT_ROOT,
                )
                
                await asyncio.sleep(5)
                
                # Check Docker container
                import aiohttp
                for port in [5173, 5174, 3000]:
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(
                                f"http://localhost:{port}/",
                                timeout=aiohttp.ClientTimeout(total=5)
                            ) as resp:
                                if resp.status == 200:
                                    return StepResult(
                                        name="Frontend",
                                        status=StepStatus.SUCCESS,
                                        message=f"Running on port {port} (Docker)",
                                        duration_seconds=time.time() - start,
                                        details=[f"Frontend URL: http://localhost:{port}"],
                                    )
                    except:
                        continue
                
                return StepResult(
                    name="Frontend",
                    status=StepStatus.WARNING,
                    message="Docker container started but not responding",
                    duration_seconds=time.time() - start,
                )
            
            # Start with npm locally
            web_app_dir = os.path.join(PROJECT_ROOT, "web-app")
            
            # Check if already running
            import aiohttp
            for port in [5173, 5174]:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            f"http://localhost:{port}/",
                            timeout=aiohttp.ClientTimeout(total=3)
                        ) as resp:
                            if resp.status == 200:
                                self.log(f"  ✅ Frontend already running on port {port}")
                                return StepResult(
                                    name="Frontend",
                                    status=StepStatus.SUCCESS,
                                    message=f"Already running on port {port}",
                                    duration_seconds=time.time() - start,
                                    details=[f"Frontend URL: http://localhost:{port}"],
                                )
                except:
                    continue
            
            # Start Vite dev server in background
            self.log("  Starting Vite dev server...")
            log_file = os.path.join(PROJECT_ROOT, "frontend.log")
            
            with open(log_file, 'w') as f:
                process = subprocess.Popen(
                    ["npm", "run", "dev"],
                    cwd=web_app_dir,
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    env=os.environ,
                )
            
            # Wait for server to start
            await asyncio.sleep(5)
            
            # Check if running
            for port in [5173, 5174]:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            f"http://localhost:{port}/",
                            timeout=aiohttp.ClientTimeout(total=5)
                        ) as resp:
                            if resp.status == 200:
                                return StepResult(
                                    name="Frontend",
                                    status=StepStatus.SUCCESS,
                                    message=f"Started on port {port}",
                                    duration_seconds=time.time() - start,
                                    details=[
                                        f"Frontend URL: http://localhost:{port}",
                                        f"Log file: {log_file}",
                                    ],
                                )
                except:
                    continue
            
            return StepResult(
                name="Frontend",
                status=StepStatus.WARNING,
                message="Started but not responding yet",
                duration_seconds=time.time() - start,
            )
                
        except Exception as e:
            return StepResult(
                name="Frontend",
                status=StepStatus.FAILED,
                message=str(e)[:50],
                duration_seconds=time.time() - start,
            )
    
    # =========================================================================
    # STEP 11: Refresh UI / Signal Completion
    # =========================================================================
    
    async def step11_refresh_ui(self) -> StepResult:
        """Signal UI to refresh recommendations data."""
        start = time.time()
        
        self.log("Signaling UI refresh...")
        
        # Method 1: Write a timestamp file that the UI can poll
        refresh_file = os.path.join(PROJECT_ROOT, '.recommendations_updated')
        try:
            with open(refresh_file, 'w') as f:
                f.write(datetime.now().isoformat())
            self.log(f"  ✅ Created refresh signal file")
        except Exception as e:
            self.log(f"  ⚠️ Could not create refresh file: {e}")
        
        # Method 2: Try to notify via Redis pub/sub
        try:
            import redis
            r = redis.Redis(host='localhost', port=6379)
            r.publish('recommendations_updated', json.dumps({
                'timestamp': datetime.now().isoformat(),
                'symbols': self.watchlist,
            }))
            r.close()
            self.log(f"  ✅ Published Redis notification")
        except ImportError:
            self.log(f"  ⚠️ Redis not installed - skipping pub/sub notification")
        except Exception as e:
            self.log(f"  ⚠️ Redis notification failed: {str(e)[:50]}")
        
        # Method 3: Call the web app's refresh endpoint (if running)
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "http://localhost:3000/api/refresh-recommendations",
                    json={'symbols': self.watchlist},
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status == 200:
                        self.log(f"  ✅ Web app refresh endpoint called")
                    else:
                        self.log(f"  ⚠️ Web app returned status {resp.status}")
        except Exception as e:
            self.log(f"  ⚠️ Web app not reachable (this is OK if not running)")
        
        return StepResult(
            name="Refresh UI",
            status=StepStatus.SUCCESS,
            message="Refresh signals sent",
            duration_seconds=time.time() - start,
        )
    
    # =========================================================================
    # Main Execution
    # =========================================================================
    
    async def run(self) -> List[StepResult]:
        """Run all startup steps."""
        self.start_time = time.time()
        self.print_header()
        
        steps = [
            ("Prepare Repo", self.step0_prepare_repo),
            ("Start Docker Containers", self.step1_start_docker_containers),
            ("Run DB Migrations", self.step1_5_run_db_migrations),
            ("Verify and Fix Services", self.step2_verify_and_fix_services),
            ("Test Data Connectors", self.step3_test_data_connectors),
            ("Test LLM Connectors", self.step4_test_llm_connectors),
            ("Run Recommendations", self.step5_run_recommendations),
            ("Smoke Test Services", self.step10_smoke_test_services),
        ]
        
        total_steps = len(steps)
        
        for i, (name, step_func) in enumerate(steps, 1):
            self.print_step(i, total_steps, name)
            
            try:
                result = await step_func()
                self.results.append(result)
            except Exception as e:
                self.results.append(StepResult(
                    name=name,
                    status=StepStatus.FAILED,
                    message=f"Unexpected error: {str(e)[:50]}",
                    duration_seconds=0,
                ))
        
        self.print_summary()
        return self.results
    
    def print_summary(self):
        """Print final summary of all steps."""
        total_duration = time.time() - self.start_time
        
        print("\n" + "=" * 70)
        print("📋 STARTUP SUMMARY")
        print("=" * 70)
        
        # Step results table
        print("\n┌─────────────────────────────────────┬──────────┬──────────┐")
        print("│ Step                                │ Status   │ Duration │")
        print("├─────────────────────────────────────┼──────────┼──────────┤")
        
        for result in self.results:
            name = result.name[:35].ljust(35)
            status = result.status.value
            duration = f"{result.duration_seconds:.1f}s".rjust(8)
            print(f"│ {name} │ {status}       │ {duration} │")
        
        print("└─────────────────────────────────────┴──────────┴──────────┘")
        
        # Count statuses
        success = len([r for r in self.results if r.status == StepStatus.SUCCESS])
        warning = len([r for r in self.results if r.status == StepStatus.WARNING])
        failed = len([r for r in self.results if r.status == StepStatus.FAILED])
        skipped = len([r for r in self.results if r.status == StepStatus.SKIPPED])
        
        print(f"\n📊 Results: {success} ✅ Success | {warning} ⚠️ Warning | {failed} ❌ Failed | {skipped} ⏭️ Skipped")
        print(f"⏱️  Total Duration: {total_duration:.1f} seconds")
        
        # Detailed sub-results
        for result in self.results:
            if result.sub_results:
                print(f"\n📝 {result.name} Details:")
                for sub in result.sub_results:
                    print(f"   {sub.status.value} {sub.name}: {sub.message}")
        
        # Recommendations summary
        rec_result = next((r for r in self.results if r.name == "Run Recommendations"), None)
        if rec_result and rec_result.details:
            print(f"\n💹 Recommendations Generated:")
            for detail in rec_result.details:
                print(f"   • {detail}")
        
        # Final status
        print("\n" + "=" * 70)
        if failed > 0:
            print("❌ STARTUP COMPLETED WITH ERRORS")
        elif warning > 0:
            print("⚠️ STARTUP COMPLETED WITH WARNINGS")
        else:
            print("✅ STARTUP COMPLETED SUCCESSFULLY")
        print("=" * 70 + "\n")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="AutoTrader Application Startup Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/StartUpApplication.py

  # Fresh machine bootstrap (clone + start)
  python scripts/StartUpApplication.py --repo-url https://github.com/YOUR_USERNAME/autotrader-ai.git --branch main

  # Start without rebuilding images
  python scripts/StartUpApplication.py --skip-build

  # Skip connector/API key tests
  python scripts/StartUpApplication.py --skip-tests

  # Custom watchlist for smoke-testing recommendations
  python scripts/StartUpApplication.py --symbols AAPL,MSFT
        """
    )
    
    parser.add_argument(
        "--skip-docker",
        action="store_true",
        help="Skip starting Docker containers"
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip connector tests"
    )
    parser.add_argument(
        "--skip-news",
        action="store_true",
        help="Skip news sentiment service"
    )
    parser.add_argument(
        "--symbols",
        type=str,
        help="Comma-separated list of stock symbols for watchlist"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce output verbosity"
    )

    # Repo bootstrap options
    parser.add_argument(
        "--repo-url",
        type=str,
        default=None,
        help="Optional Git repository URL to clone/pull (for new machine bootstrap)"
    )
    parser.add_argument(
        "--branch",
        type=str,
        default="main",
        help="Git branch to checkout when using --repo-url (default: main)"
    )
    parser.add_argument(
        "--target-dir",
        type=str,
        default=None,
        help="Target directory for --repo-url clone/pull (default: ~/autotrader-ai)"
    )
    parser.add_argument(
        "--fresh-clone",
        action="store_true",
        help="Fail if target dir exists when using --repo-url (safety for new machine)"
    )

    # Docker/compose options
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip docker compose --build"
    )
    parser.add_argument(
        "--prune-docker",
        action="store_true",
        help="Run docker system prune -f before starting (can help on low disk)"
    )

    args = parser.parse_args()
    
    # Parse symbols
    watchlist = None
    if args.symbols:
        watchlist = [s.strip().upper() for s in args.symbols.split(",")]
    
    # Create and run startup
    startup = StartUpApplication(
        watchlist=watchlist,
        skip_docker=args.skip_docker,
        skip_tests=args.skip_tests,
        skip_news=args.skip_news,
        verbose=not args.quiet,
        repo_url=args.repo_url,
        branch=args.branch,
        target_dir=args.target_dir,
        fresh_clone=args.fresh_clone,
        skip_build=args.skip_build,
        prune_docker=args.prune_docker,
    )
    
    await startup.run()


if __name__ == "__main__":
    asyncio.run(main())

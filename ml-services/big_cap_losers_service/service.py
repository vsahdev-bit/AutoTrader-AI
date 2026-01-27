"""
Big Cap Losers Service
Runs every 2 hours to crawl Yahoo Finance losers and track big cap stocks (>$50B)
that have fallen significantly.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

import asyncpg

try:
    from .crawler import BigCapLosersCrawler, StockLoser
except ImportError:
    from crawler import BigCapLosersCrawler, StockLoser

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://autotrader:autotrader_dev_pass@localhost:5432/autotrader')
MIN_MARKET_CAP = 1_000_000_000  # $1B
SIGNIFICANT_DROP_THRESHOLD = -10.0  # 10% drop


class BigCapLosersService:
    """Service to crawl, analyze, and store big cap losers data"""
    
    def __init__(self):
        self.crawler: Optional[BigCapLosersCrawler] = None
        self.db_pool: Optional[asyncpg.Pool] = None
    
    async def initialize(self):
        """Initialize the service"""
        # Initialize crawler
        self.crawler = BigCapLosersCrawler(min_market_cap=MIN_MARKET_CAP)
        await self.crawler.initialize()
        
        # Initialize database connection
        self.db_pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=2,
            max_size=5,
        )
        
        logger.info("BigCapLosersService initialized")
    
    async def close(self):
        """Close connections"""
        if self.crawler:
            await self.crawler.close()
        if self.db_pool:
            await self.db_pool.close()
        logger.info("BigCapLosersService closed")
    
    async def store_loser(self, loser: StockLoser, trading_date: datetime) -> int:
        """Store a single loser record in the database"""
        async with self.db_pool.acquire() as conn:
            # Check for existing record with same symbol and similar crawl time (within 1 hour)
            existing = await conn.fetchval("""
                SELECT id FROM big_cap_losers 
                WHERE symbol = $1 
                AND crawled_at > NOW() - INTERVAL '1 hour'
            """, loser.symbol)
            
            if existing:
                # Update existing record
                await conn.execute("""
                    UPDATE big_cap_losers SET
                        current_price = $2,
                        price_change = $3,
                        percent_change = $4,
                        market_cap = $5,
                        market_cap_formatted = $6,
                        volume = $7,
                        crawled_at = NOW()
                    WHERE id = $1
                """, existing, loser.current_price, loser.price_change,
                    loser.percent_change, loser.market_cap, loser.market_cap_formatted,
                    loser.volume)
                return existing
            
            # Insert new record
            record_id = await conn.fetchval("""
                INSERT INTO big_cap_losers (
                    symbol, company_name, current_price, price_change, percent_change,
                    market_cap, market_cap_formatted, volume, avg_volume,
                    day_high, day_low, fifty_two_week_high, fifty_two_week_low,
                    pe_ratio, trading_date, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                RETURNING id
            """,
                loser.symbol,
                loser.company_name,
                loser.current_price,
                loser.price_change,
                loser.percent_change,
                loser.market_cap,
                loser.market_cap_formatted,
                loser.volume,
                loser.avg_volume,
                loser.day_high,
                loser.day_low,
                loser.fifty_two_week_high,
                loser.fifty_two_week_low,
                loser.pe_ratio,
                trading_date.date(),
                json.dumps(loser.metadata or {}),
            )
            return record_id
    
    async def generate_daily_summary(self, losers: List[StockLoser], trading_date: datetime):
        """Generate and store daily summary"""
        if not losers:
            return
        
        # Calculate statistics
        over_15_percent = [l for l in losers if l.percent_change <= SIGNIFICANT_DROP_THRESHOLD]
        worst_performer = min(losers, key=lambda x: x.percent_change)
        
        # Top losers list
        top_losers = [
            {
                'symbol': l.symbol,
                'company_name': l.company_name,
                'percent_change': l.percent_change,
                'market_cap': l.market_cap,
                'market_cap_formatted': l.market_cap_formatted,
                'current_price': l.current_price,
            }
            for l in sorted(losers, key=lambda x: x.percent_change)[:20]
        ]
        
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO big_cap_losers_daily_summary (
                    summary_date, total_stocks_tracked, stocks_over_15_percent_drop,
                    worst_performer_symbol, worst_performer_drop, top_losers, generated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, NOW())
                ON CONFLICT (summary_date) DO UPDATE SET
                    total_stocks_tracked = EXCLUDED.total_stocks_tracked,
                    stocks_over_15_percent_drop = EXCLUDED.stocks_over_15_percent_drop,
                    worst_performer_symbol = EXCLUDED.worst_performer_symbol,
                    worst_performer_drop = EXCLUDED.worst_performer_drop,
                    top_losers = EXCLUDED.top_losers,
                    generated_at = NOW()
            """,
                trading_date.date(),
                len(losers),
                len(over_15_percent),
                worst_performer.symbol,
                worst_performer.percent_change,
                json.dumps(top_losers),
            )
        
        logger.info(f"Daily summary generated: {len(losers)} stocks, {len(over_15_percent)} over 15% drop")
    
    async def log_crawl(self, stats: Dict[str, Any]):
        """Log crawl operation"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO big_cap_losers_crawl_logs (
                    total_losers_found, big_cap_losers_found, over_15_percent_found,
                    status, started_at, completed_at, duration_seconds, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
                stats.get('total_losers', 0),
                stats.get('big_cap_losers', 0),
                stats.get('over_15_percent', 0),
                stats.get('status', 'success'),
                stats['started_at'],
                stats['completed_at'],
                stats.get('duration_seconds', 0),
                json.dumps(stats.get('metadata', {})),
            )
    
    async def cleanup_old_data(self) -> Dict[str, int]:
        """Delete rows older than 2 hours from big_cap_losers and big_cap_losers_recommendations tables.
        
        Returns:
            Dictionary with counts of deleted rows from each table
        """
        deleted_counts = {'losers': 0, 'recommendations': 0, 'crawl_logs': 0}
        
        try:
            async with self.db_pool.acquire() as conn:
                # Delete old recommendations first (due to foreign key constraint)
                result = await conn.execute("""
                    DELETE FROM big_cap_losers_recommendations
                    WHERE created_at < NOW() - INTERVAL '2 hours'
                """)
                deleted_counts['recommendations'] = int(result.split()[-1]) if result else 0
                
                # Delete old losers
                result = await conn.execute("""
                    DELETE FROM big_cap_losers
                    WHERE crawled_at < NOW() - INTERVAL '2 hours'
                """)
                deleted_counts['losers'] = int(result.split()[-1]) if result else 0
                
                # Also clean up old crawl logs (keep for 1 day for debugging)
                result = await conn.execute("""
                    DELETE FROM big_cap_losers_crawl_logs
                    WHERE crawl_timestamp < NOW() - INTERVAL '1 day'
                """)
                deleted_counts['crawl_logs'] = int(result.split()[-1]) if result else 0
                
            logger.info(f"Cleanup completed: deleted {deleted_counts['losers']} losers, "
                       f"{deleted_counts['recommendations']} recommendations older than 2 hours, "
                       f"{deleted_counts['crawl_logs']} crawl logs older than 1 day")
                       
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
        
        return deleted_counts
    
    async def run(self) -> Dict[str, Any]:
        """Run a single crawl cycle"""
        started_at = datetime.utcnow()
        stats = {
            'started_at': started_at,
            'total_losers': 0,
            'big_cap_losers': 0,
            'over_15_percent': 0,
            'stored': 0,
            'status': 'success',
        }
        
        try:
            logger.info("=" * 60)
            logger.info("BIG CAP LOSERS SERVICE - CRAWL STARTING")
            logger.info("=" * 60)
            
            # Crawl Yahoo Finance
            losers = await self.crawler.crawl()
            stats['big_cap_losers'] = len(losers)
            
            # Store each loser
            trading_date = datetime.utcnow()
            stored_count = 0
            over_15_count = 0
            
            for loser in losers:
                try:
                    await self.store_loser(loser, trading_date)
                    stored_count += 1
                    
                    if loser.percent_change <= SIGNIFICANT_DROP_THRESHOLD:
                        over_15_count += 1
                        logger.warning(f"🔴 SIGNIFICANT DROP: {loser.symbol} down {loser.percent_change:.2f}% ({loser.market_cap_formatted})")
                    
                except Exception as e:
                    logger.error(f"Error storing {loser.symbol}: {e}")
            
            stats['stored'] = stored_count
            stats['over_15_percent'] = over_15_count
            
            # Generate daily summary
            await self.generate_daily_summary(losers, trading_date)
            
            completed_at = datetime.utcnow()
            stats['completed_at'] = completed_at
            stats['duration_seconds'] = int((completed_at - started_at).total_seconds())
            
            # Log the crawl
            await self.log_crawl(stats)
            
            logger.info("=" * 60)
            logger.info("CRAWL COMPLETE")
            logger.info(f"  Big cap losers found: {stats['big_cap_losers']}")
            logger.info(f"  Over 10% drop: {stats['over_15_percent']}")
            logger.info(f"  Duration: {stats['duration_seconds']}s")
            logger.info("=" * 60)
            
            # Trigger recommendation generation for all big cap losers
            if stats['big_cap_losers'] > 0:
                logger.info("Triggering recommendation generation for big cap losers...")
                recommendations_generated = await self.trigger_recommendations()
                stats['recommendations_generated'] = recommendations_generated
            
            # Cleanup old data (older than 1 day)
            logger.info("Cleaning up old data...")
            cleanup_counts = await self.cleanup_old_data()
            stats['cleanup'] = cleanup_counts
            
        except Exception as e:
            stats['status'] = 'failed'
            stats['error'] = str(e)
            stats['completed_at'] = datetime.utcnow()
            logger.error(f"Crawl failed: {e}")
            
            # Log failed crawl
            try:
                await self.log_crawl(stats)
            except:
                pass
        
        return stats
    
    async def trigger_recommendations(self) -> int:
        """Generate recommendations for all big cap losers with regime data.
        
        Returns:
            Number of recommendations generated
        """
        import aiohttp
        
        async def fetch_regime(session, symbol):
            """Fetch market regime for a symbol."""
            try:
                async with session.get(
                    f"http://recommendation-engine:8000/regime/{symbol}",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('regime', {})
            except Exception as e:
                logger.debug(f"Could not fetch regime for {symbol}: {e}")
            return None
        
        saved = 0
        try:
            async with self.db_pool.acquire() as conn:
                # Get all current big cap losers
                rows = await conn.fetch("""
                    SELECT DISTINCT ON (symbol) id, symbol, current_price, percent_change, market_cap, market_cap_formatted
                    FROM big_cap_losers
                    WHERE market_cap >= 1000000000
                    ORDER BY symbol, crawled_at DESC
                """)
            
            if not rows:
                logger.info("No symbols to generate recommendations for")
                return 0
            
            logger.info(f"Generating recommendations for {len(rows)} symbols")
            
            async with aiohttp.ClientSession() as session:
                async with self.db_pool.acquire() as conn:
                    for row in rows:
                        try:
                            symbol = row['symbol']
                            percent_drop = float(row['percent_change'] or 0)
                            
                            # Fetch market regime
                            regime_data = await fetch_regime(session, symbol)
                            market_regime = None
                            regime_confidence = None
                            
                            if regime_data:
                                market_regime = regime_data.get('label') or regime_data.get('volatility')
                                # Use confidence if available, otherwise use risk_score
                                regime_confidence = regime_data.get('confidence') or regime_data.get('risk_score')
                            
                            # Calculate a meaningful score based on multiple factors
                            drop_magnitude = abs(percent_drop)
                            market_cap_val = float(row['market_cap'] if 'market_cap' in row.keys() else 0)
                            
                            # Base score from drop magnitude (contrarian: bigger drop = potentially better opportunity)
                            # Maps -5% to -25%+ drop to 0.4-0.8 score range
                            drop_score = min(0.8, max(0.4, 0.4 + (drop_magnitude - 5) * 0.02))
                            
                            # Market cap factor: larger companies are generally safer (slight boost)
                            cap_boost = 0
                            if market_cap_val >= 100_000_000_000:  # >$100B
                                cap_boost = 0.05
                            elif market_cap_val >= 50_000_000_000:  # >$50B
                                cap_boost = 0.03
                            elif market_cap_val >= 10_000_000_000:  # >$10B
                                cap_boost = 0.01
                            
                            # Regime adjustment: if we have regime data, adjust based on risk
                            regime_adjust = 0
                            if regime_confidence is not None:
                                # Lower risk_score is better, so invert it
                                regime_adjust = (0.5 - (regime_confidence or 0.5)) * 0.1
                            
                            # Calculate final normalized score (0-1 range)
                            normalized_score = min(0.95, max(0.3, drop_score + cap_boost + regime_adjust))
                            
                            # Determine action based on normalized score
                            if normalized_score >= 0.65:
                                action = 'BUY'
                            elif normalized_score <= 0.35:
                                action = 'SELL'
                            else:
                                action = 'HOLD'
                            
                            # Use regime confidence if available, otherwise calculate based on drop magnitude
                            confidence = regime_confidence if regime_confidence else (0.6 if drop_magnitude > 15 else 0.5 if drop_magnitude > 10 else 0.4)
                            
                            explanation = {
                                'summary': f"Stock has dropped {abs(percent_drop):.1f}% today. This significant move warrants careful analysis.",
                                'reasoning': 'Large single-day drops can indicate panic selling and potential oversold conditions.' if percent_drop <= -15 else 'Moderate drop detected. Monitor for further developments.',
                                'key_factors': [
                                    f"{abs(percent_drop):.1f}% daily decline",
                                    f"Market cap: {row['market_cap_formatted'] or 'Unknown'}",
                                    f"Market regime: {market_regime}" if market_regime else "Regime data pending"
                                ],
                                'risk_factors': [
                                    'Large price movements may indicate fundamental issues',
                                    'Further downside possible'
                                ]
                            }
                            
                            await conn.execute("""
                                INSERT INTO big_cap_losers_recommendations (
                                    big_cap_loser_id, symbol, action, score, normalized_score, confidence,
                                    market_regime, regime_confidence,
                                    price_at_recommendation, explanation, data_sources_used, generated_at
                                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW())
                            """,
                                row['id'],
                                symbol,
                                action,
                                normalized_score - 0.5,
                                normalized_score,
                                confidence,
                                market_regime,
                                regime_confidence,
                                row['current_price'],
                                json.dumps(explanation),
                                ['price_data', 'regime_data'] if market_regime else ['price_data']
                            )
                            saved += 1
                        except Exception as e:
                            logger.error(f"Error saving recommendation for {row['symbol']}: {e}")
            
            logger.info(f"✓ Generated {saved} recommendations")
                    
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
        
        return saved


async def run_once() -> Dict[str, Any]:
    """Run the service once (for manual execution)"""
    service = BigCapLosersService()
    await service.initialize()
    try:
        return await service.run()
    finally:
        await service.close()


async def run_scheduled():
    """Run the service on a schedule (every 1 hour)"""
    service = BigCapLosersService()
    await service.initialize()
    
    logger.info("=" * 60)
    logger.info("BIG CAP LOSERS SERVICE - SCHEDULED MODE")
    logger.info("=" * 60)
    logger.info("Scheduled to run every 1 hour")
    logger.info("Running initial crawl...")
    
    # Run once at startup
    await service.run()
    
    while True:
        # Calculate next run (1 hour from now)
        next_run = datetime.utcnow() + timedelta(hours=1)
        seconds_until_run = 1 * 60 * 60  # 1 hour in seconds
        
        logger.info(f"Next scheduled run: {next_run.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        
        # Sleep until next run
        await asyncio.sleep(seconds_until_run)
        
        # Run the service
        logger.info("Starting scheduled crawl...")
        try:
            await service.run()
        except Exception as e:
            logger.error(f"Error during scheduled run: {e}")


async def run_http_server():
    """Run HTTP server for manual refresh triggers"""
    from aiohttp import web
    
    service = BigCapLosersService()
    await service.initialize()
    
    async def handle_refresh(request):
        """Handle refresh request - crawls data and generates recommendations"""
        logger.info("Received manual refresh request")
        try:
            stats = await service.run()
            cleanup = stats.get('cleanup', {})
            return web.json_response({
                'success': True,
                'stats': {
                    'big_cap_losers': stats.get('big_cap_losers', 0),
                    'over_10_percent': stats.get('over_15_percent', 0),
                    'stored': stats.get('stored', 0),
                    'recommendations_generated': stats.get('recommendations_generated', 0),
                    'duration_seconds': stats.get('duration_seconds', 0),
                    'cleanup': cleanup,
                },
                'message': f"Found {stats.get('big_cap_losers', 0)} losers, generated {stats.get('recommendations_generated', 0)} recommendations, cleaned up {cleanup.get('losers', 0)} old records"
            })
        except Exception as e:
            logger.error(f"Refresh failed: {e}")
            return web.json_response({
                'success': False,
                'error': str(e)
            }, status=500)
    
    async def handle_health(request):
        """Health check endpoint"""
        return web.json_response({'status': 'healthy'})
    
    app = web.Application()
    app.router.add_post('/refresh', handle_refresh)
    app.router.add_get('/health', handle_health)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get('SERVICE_PORT', 8001))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    logger.info(f"HTTP server listening on port {port}")
    logger.info("Endpoints: POST /refresh, GET /health")
    
    # Run initial crawl
    logger.info("Running initial crawl...")
    await service.run()
    
    # Keep the server running and also run scheduled crawls
    while True:
        next_run = datetime.utcnow() + timedelta(hours=1)
        seconds_until_run = 1 * 60 * 60
        logger.info(f"Next scheduled run: {next_run.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        await asyncio.sleep(seconds_until_run)
        
        logger.info("Starting scheduled crawl...")
        try:
            await service.run()
        except Exception as e:
            logger.error(f"Error during scheduled run: {e}")


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--once':
        # Run once
        asyncio.run(run_once())
    elif len(sys.argv) > 1 and sys.argv[1] == '--http':
        # Run with HTTP server
        asyncio.run(run_http_server())
    else:
        # Run scheduled (default)
        asyncio.run(run_scheduled())

"""Big Cap Losers Service

Spec:
- Crawls Yahoo Finance losers page
- Filters market cap > $1B
- Stores top 25 losers (by percent change, most negative first)
- Replaces existing snapshot each run (delete+insert)
- For each symbol, calls the recommendation engine and stores the results
- Exposes /refresh for on-demand triggers (hourly schedule is external)
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
SIGNIFICANT_DROP_THRESHOLD = -10.0  # 10% drop (used for the 'over 10%' UI tab)
TOP_N = int(os.environ.get('TOP_N_LOSERS', '25'))


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
        """Insert a single loser record in the database.

        Per spec, we replace the snapshot each run (delete+insert), so this method
        always inserts.
        """
        async with self.db_pool.acquire() as conn:
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

            # Sort worst performers first (most negative percent_change) and take top N
            losers = sorted(losers, key=lambda x: x.percent_change)[:TOP_N]

            # Replace snapshot: delete all rows first
            async with self.db_pool.acquire() as conn:
                await conn.execute("DELETE FROM big_cap_losers")

            trading_date = datetime.utcnow()
            stored_count = 0
            over_10_count = 0

            loser_rows: List[Dict[str, Any]] = []

            # Insert losers
            for loser in losers:
                try:
                    loser_id = await self.store_loser(loser, trading_date)
                    stored_count += 1
                    if loser.percent_change <= SIGNIFICANT_DROP_THRESHOLD:
                        over_10_count += 1
                    loser_rows.append({"id": loser_id, "symbol": loser.symbol, "company_name": loser.company_name})
                except Exception as e:
                    logger.error(f"Error storing {loser.symbol}: {e}")

            stats['stored'] = stored_count
            stats['over_15_percent'] = over_10_count
            stats['top_n'] = TOP_N

            # Generate recommendations inline per loser (tolerate per-symbol failures)
            recommendations_generated = await self.generate_and_store_recommendations(loser_rows)
            stats['recommendations_generated'] = recommendations_generated
            
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
            
            # NOTE: recommendations are generated inline per-symbol above and stored on big_cap_losers rows.
            # Cleanup old data is no longer needed because we replace the snapshot each run.
            stats['cleanup'] = {"losers": 0, "recommendations": 0, "crawl_logs": 0}
            
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
    
    async def generate_and_store_recommendations(self, loser_rows: List[Dict[str, Any]]) -> int:
        """Generate recommendations for each loser row and store inline fields on big_cap_losers.

        This calls the recommendation-engine and stores action/score/confidence/regime/top_news/explanation.
        Per spec, failures are tolerated per-symbol and recorded in recommendation_error.
        """
        import aiohttp
        from .recommender import fetch_recommendation, map_recommendation_to_row

        if not loser_rows:
            return 0

        api_base = os.environ.get('PUBLIC_API_BASE', 'http://localhost:3001')

        saved = 0
        async with aiohttp.ClientSession() as session:
            async with self.db_pool.acquire() as conn:
                for row in loser_rows:
                    loser_id = row.get('id')
                    symbol = row.get('symbol')
                    if not loser_id or not symbol:
                        continue
                    try:
                        rec = await fetch_recommendation(session, symbol)
                        mapped = map_recommendation_to_row(rec, api_base=api_base, symbol=symbol)

                        await conn.execute(
                            """
                            UPDATE big_cap_losers SET
                                action = $2,
                                score = $3,
                                normalized_score = $4,
                                confidence = $5,
                                market_regime = $6,
                                regime_confidence = $7,
                                news_score = $8,
                                technical_score = $9,
                                details_url = $10,
                                top_news = $11,
                                explanation = $12,
                                recommendation_generated_at = $13,
                                recommendation_error = NULL
                            WHERE id = $1
                            """,
                            loser_id,
                            mapped.get('action'),
                            mapped.get('score'),
                            mapped.get('normalized_score'),
                            mapped.get('confidence'),
                            mapped.get('market_regime'),
                            mapped.get('regime_confidence'),
                            mapped.get('news_score'),
                            mapped.get('technical_score'),
                            mapped.get('details_url'),
                            json.dumps(mapped.get('top_news')) if mapped.get('top_news') is not None else None,
                            json.dumps(mapped.get('explanation')) if mapped.get('explanation') is not None else None,
                            mapped.get('recommendation_generated_at'),
                        )
                        saved += 1
                    except Exception as e:
                        logger.error(f"Recommendation failed for {symbol}: {e}")
                        await conn.execute(
                            """
                            UPDATE big_cap_losers SET
                                recommendation_error = $2,
                                recommendation_generated_at = NOW()
                            WHERE id = $1
                            """,
                            loser_id,
                            str(e)[:500],
                        )

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

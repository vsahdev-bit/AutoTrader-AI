"""
Nasdaq Data Link Connector
==========================

Fetches financial data from Nasdaq Data Link (formerly Quandl) API.
Nasdaq Data Link provides access to a wide variety of financial,
economic, and alternative datasets.

API Documentation: https://docs.data.nasdaq.com/

Features:
- Time-series financial data
- Fundamental data and ratios
- Economic indicators
- Alternative data sets
- Bulk data downloads

Rate Limits:
- Free tier: 50 calls/day, 1 call/second
- Premium: Higher limits based on subscription

Required API Key: Get at https://data.nasdaq.com/account/profile
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import logging
import os

from .base import BaseNewsConnector, NewsArticle, NewsSource, NewsCategory

logger = logging.getLogger(__name__)


class NasdaqDataLinkConnector(BaseNewsConnector):
    """
    Market data connector for Nasdaq Data Link API.
    
    Nasdaq Data Link (formerly Quandl) provides access to financial,
    economic, and alternative datasets. This connector focuses on
    stock price data and fundamental metrics.
    
    Example Usage:
        connector = NasdaqDataLinkConnector(api_key="your_key")
        
        # Fetch time series data
        data = await connector.get_time_series(
            database="WIKI",
            dataset="AAPL",
            start_date=datetime.utcnow() - timedelta(days=30)
        )
        
        # Fetch stock prices
        prices = await connector.get_stock_prices(
            symbol="AAPL",
            start_date=datetime.utcnow() - timedelta(days=365)
        )
    """
    
    source = NewsSource.NASDAQ_DATA_LINK
    base_url = "https://data.nasdaq.com/api/v3"
    rate_limit_per_minute = 60  # 1 call/second for free tier
    
    # Popular database codes
    WIKI_PRICES = "WIKI/PRICES"  # Historical stock prices (discontinued but archived)
    EOD = "EOD"  # End of day US stock prices
    ZACKS = "ZACKS"  # Zacks fundamental data
    SF1 = "SF1"  # Core US fundamentals
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        rate_limit: Optional[int] = None,
        timeout: int = 30,
    ):
        """
        Initialize the Nasdaq Data Link connector.
        
        Args:
            api_key: Nasdaq Data Link API key (or retrieved from Vault/NASDAQ_DATA_LINK_API_KEY env var)
            rate_limit: Override default rate limit
            timeout: HTTP request timeout in seconds
        """
        # API key will be loaded lazily from Vault if not provided
        self._api_key_override = api_key
        self._api_key_loaded = api_key is not None
        super().__init__(api_key=api_key, rate_limit=rate_limit, timeout=timeout)
    
    async def _ensure_api_key(self):
        """Load API key from Vault if not already loaded."""
        if not self._api_key_loaded:
            from .base import get_api_key_from_vault
            self.api_key = self._api_key_override or await get_api_key_from_vault('nasdaq_data_link')
            self._api_key_loaded = True
            if not self.api_key:
                logger.warning("No Nasdaq Data Link API key found in Vault or environment")
    
    async def fetch_news(
        self,
        symbols: Optional[List[str]] = None,
        since: Optional[datetime] = None,
        limit: int = 50,
    ) -> List[NewsArticle]:
        """
        Nasdaq Data Link doesn't provide news - this is a placeholder.
        
        This connector is primarily for market data, not news.
        Use other connectors (Polygon, IEX Cloud) for news.
        
        Returns:
            Empty list (news not supported)
        """
        logger.info("Nasdaq Data Link doesn't provide news data - use for market data only")
        return []
    
    async def get_time_series(
        self,
        database: str,
        dataset: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 1000,
        column_index: Optional[int] = None,
        collapse: Optional[str] = None,
        transform: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetch time series data from a specific database/dataset.
        
        Args:
            database: Database code (e.g., "WIKI", "EOD", "ZACKS")
            dataset: Dataset code (e.g., "AAPL", "FB")
            start_date: Start date for data
            end_date: End date for data
            limit: Maximum rows to return
            column_index: Specific column to return (1-indexed)
            collapse: Frequency collapse (daily, weekly, monthly, quarterly, annual)
            transform: Data transformation (diff, rdiff, rdiff_from, cumul, normalize)
            
        Returns:
            Dictionary with dataset info and data
        """
        # Load API key from Vault if not already loaded
        await self._ensure_api_key()
        
        if not self.api_key:
            raise ValueError("Nasdaq Data Link API key is required")
        
        url = f"{self.base_url}/datasets/{database}/{dataset}.json"
        
        params: Dict[str, Any] = {
            "api_key": self.api_key,
            "limit": limit,
        }
        
        if start_date:
            params["start_date"] = start_date.strftime("%Y-%m-%d")
        if end_date:
            params["end_date"] = end_date.strftime("%Y-%m-%d")
        if column_index:
            params["column_index"] = column_index
        if collapse:
            params["collapse"] = collapse
        if transform:
            params["transform"] = transform
        
        logger.info(f"Fetching Nasdaq Data Link: {database}/{dataset}")
        
        try:
            data = await self._make_request(url, params=params)
            
            dataset_data = data.get("dataset", {})
            return {
                "name": dataset_data.get("name"),
                "description": dataset_data.get("description"),
                "database_code": dataset_data.get("database_code"),
                "dataset_code": dataset_data.get("dataset_code"),
                "frequency": dataset_data.get("frequency"),
                "column_names": dataset_data.get("column_names", []),
                "data": dataset_data.get("data", []),
                "start_date": dataset_data.get("start_date"),
                "end_date": dataset_data.get("end_date"),
            }
            
        except Exception as e:
            logger.error(f"Failed to fetch time series: {e}")
            raise
    
    async def get_stock_prices(
        self,
        symbol: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        database: str = "EOD",
    ) -> List[Dict[str, Any]]:
        """
        Get historical stock prices for a symbol.
        
        Args:
            symbol: Stock ticker symbol
            start_date: Start date for price data
            end_date: End date for price data
            database: Database to use (EOD, WIKI, etc.)
            
        Returns:
            List of OHLCV price dictionaries
        """
        if not self.api_key:
            raise ValueError("Nasdaq Data Link API key is required")
        
        try:
            data = await self.get_time_series(
                database=database,
                dataset=symbol,
                start_date=start_date,
                end_date=end_date,
            )
            
            column_names = [c.lower() for c in data.get("column_names", [])]
            rows = data.get("data", [])
            
            # Map column names to standard format
            prices = []
            for row in rows:
                price_data = dict(zip(column_names, row))
                prices.append({
                    "date": price_data.get("date"),
                    "open": price_data.get("open") or price_data.get("adj_open"),
                    "high": price_data.get("high") or price_data.get("adj_high"),
                    "low": price_data.get("low") or price_data.get("adj_low"),
                    "close": price_data.get("close") or price_data.get("adj_close"),
                    "volume": price_data.get("volume") or price_data.get("adj_volume"),
                    "adjusted_close": price_data.get("adj_close") or price_data.get("adj. close"),
                    "dividend": price_data.get("dividend") or price_data.get("ex-dividend"),
                    "split": price_data.get("split") or price_data.get("split_ratio"),
                })
            
            logger.info(f"Fetched {len(prices)} price records from Nasdaq Data Link for {symbol}")
            return prices
            
        except Exception as e:
            logger.error(f"Failed to fetch stock prices for {symbol}: {e}")
            return []
    
    async def get_table_data(
        self,
        datatable_code: str,
        filters: Optional[Dict[str, Any]] = None,
        columns: Optional[List[str]] = None,
        per_page: int = 100,
    ) -> Dict[str, Any]:
        """
        Fetch data from a Nasdaq Data Link datatable.
        
        Datatables provide structured data with filtering capabilities.
        
        Args:
            datatable_code: Datatable code (e.g., "ZACKS/FC")
            filters: Dictionary of filter conditions
            columns: List of columns to return
            per_page: Number of rows per page
            
        Returns:
            Dictionary with table data and metadata
        """
        if not self.api_key:
            raise ValueError("Nasdaq Data Link API key is required")
        
        url = f"{self.base_url}/datatables/{datatable_code}.json"
        
        params: Dict[str, Any] = {
            "api_key": self.api_key,
            "per_page": per_page,
        }
        
        if filters:
            for key, value in filters.items():
                params[key] = value
        
        if columns:
            params["qopts.columns"] = ",".join(columns)
        
        logger.info(f"Fetching Nasdaq Data Link table: {datatable_code}")
        
        try:
            data = await self._make_request(url, params=params)
            
            datatable = data.get("datatable", {})
            return {
                "columns": datatable.get("columns", []),
                "data": datatable.get("data", []),
                "cursor_id": data.get("meta", {}).get("next_cursor_id"),
            }
            
        except Exception as e:
            logger.error(f"Failed to fetch table data: {e}")
            raise
    
    async def get_fundamentals(
        self,
        symbol: str,
        dimension: str = "MRY",
    ) -> Optional[Dict[str, Any]]:
        """
        Get fundamental data for a company.
        
        Uses the Sharadar Core US Fundamentals dataset (requires subscription).
        
        Args:
            symbol: Stock ticker symbol
            dimension: Data dimension (MRY=annual, MRQ=quarterly, ARY=annual restated)
            
        Returns:
            Dictionary with fundamental data or None
        """
        if not self.api_key:
            raise ValueError("Nasdaq Data Link API key is required")
        
        try:
            data = await self.get_table_data(
                datatable_code="SHARADAR/SF1",
                filters={
                    "ticker": symbol,
                    "dimension": dimension,
                },
                per_page=10,
            )
            
            if data.get("data"):
                columns = [c.get("name") for c in data.get("columns", [])]
                row = data["data"][0]
                return dict(zip(columns, row))
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to fetch fundamentals for {symbol}: {e}")
            return None
    
    async def get_economic_indicator(
        self,
        indicator: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get economic indicator data from FRED or other sources.
        
        Popular indicators:
        - FRED/GDP: US GDP
        - FRED/UNRATE: Unemployment rate
        - FRED/CPIAUCSL: Consumer Price Index
        - FRED/FEDFUNDS: Federal Funds Rate
        
        Args:
            indicator: Full indicator code (e.g., "FRED/GDP")
            start_date: Start date
            end_date: End date
            
        Returns:
            List of indicator values with dates
        """
        if "/" not in indicator:
            raise ValueError("Indicator must be in format 'DATABASE/CODE'")
        
        database, dataset = indicator.split("/", 1)
        
        try:
            data = await self.get_time_series(
                database=database,
                dataset=dataset,
                start_date=start_date,
                end_date=end_date,
            )
            
            column_names = data.get("column_names", ["Date", "Value"])
            rows = data.get("data", [])
            
            indicators = []
            for row in rows:
                indicators.append({
                    "date": row[0] if len(row) > 0 else None,
                    "value": row[1] if len(row) > 1 else None,
                })
            
            logger.info(f"Fetched {len(indicators)} data points for {indicator}")
            return indicators
            
        except Exception as e:
            logger.error(f"Failed to fetch economic indicator {indicator}: {e}")
            return []
    
    async def search_datasets(
        self,
        query: str,
        database_code: Optional[str] = None,
        per_page: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Search for datasets matching a query.
        
        Args:
            query: Search query string
            database_code: Limit search to specific database
            per_page: Number of results to return
            
        Returns:
            List of matching datasets
        """
        if not self.api_key:
            raise ValueError("Nasdaq Data Link API key is required")
        
        url = f"{self.base_url}/datasets.json"
        
        params: Dict[str, Any] = {
            "api_key": self.api_key,
            "query": query,
            "per_page": per_page,
        }
        
        if database_code:
            params["database_code"] = database_code
        
        try:
            data = await self._make_request(url, params=params)
            
            datasets = data.get("datasets", [])
            return [
                {
                    "id": ds.get("id"),
                    "database_code": ds.get("database_code"),
                    "dataset_code": ds.get("dataset_code"),
                    "name": ds.get("name"),
                    "description": ds.get("description"),
                    "frequency": ds.get("frequency"),
                    "type": ds.get("type"),
                }
                for ds in datasets
            ]
            
        except Exception as e:
            logger.error(f"Failed to search datasets: {e}")
            return []

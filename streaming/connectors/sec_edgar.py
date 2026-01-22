"""
SEC EDGAR Connector
===================

Fetches filings and company information from SEC EDGAR database.
EDGAR (Electronic Data Gathering, Analysis, and Retrieval) is the
SEC's public database of corporate filings.

API Documentation: https://www.sec.gov/developer

Features:
- 10-K, 10-Q, 8-K filings
- Form 4 (insider trading)
- 13F (institutional holdings)
- Company facts and submissions
- Full-text filing content
- No API key required (public data)

Rate Limits:
- 10 requests per second max
- User-Agent header required

Note: SEC requires a valid User-Agent with contact info.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import logging
import re

from .base import BaseNewsConnector, NewsArticle, NewsSource, NewsCategory

logger = logging.getLogger(__name__)


class SECEdgarConnector(BaseNewsConnector):
    """
    Connector for SEC EDGAR filings database.
    
    Provides access to official SEC filings which are critical
    for fundamental analysis and regulatory compliance monitoring.
    
    Example Usage:
        connector = SECEdgarConnector(user_agent="MyApp admin@myapp.com")
        
        # Fetch recent filings for a symbol
        filings = await connector.fetch_news(symbols=["AAPL"])
        
        # Fetch specific filing types
        form4s = await connector.fetch_filings(
            symbol="AAPL",
            form_types=["4"],  # Insider trading
            limit=20
        )
    """
    
    source = NewsSource.UNKNOWN
    base_url = "https://data.sec.gov"
    rate_limit_per_minute = 600  # 10 per second
    
    # Filing types and their categories
    FILING_CATEGORIES = {
        "10-K": NewsCategory.EARNINGS,
        "10-Q": NewsCategory.EARNINGS,
        "8-K": NewsCategory.GENERAL,
        "4": NewsCategory.EXECUTIVE,  # Insider trading
        "13F": NewsCategory.ANALYST,  # Institutional holdings
        "SC 13D": NewsCategory.MERGER_ACQUISITION,
        "SC 13G": NewsCategory.MERGER_ACQUISITION,
        "DEF 14A": NewsCategory.REGULATORY,  # Proxy statements
        "S-1": NewsCategory.GENERAL,  # IPO registration
        "424B": NewsCategory.GENERAL,  # Prospectus
    }
    
    # CIK mappings for common symbols (would normally be fetched from SEC)
    # This is a sample - full implementation would fetch from SEC API
    SYMBOL_TO_CIK = {
        "AAPL": "0000320193",
        "MSFT": "0000789019",
        "GOOGL": "0001652044",
        "AMZN": "0001018724",
        "META": "0001326801",
        "TSLA": "0001318605",
        "NVDA": "0001045810",
        "JPM": "0000019617",
        "V": "0001403161",
        "JNJ": "0000200406",
    }
    
    def __init__(
        self,
        user_agent: str = "AutoTrader AI Platform contact@autotrader.ai",
        **kwargs
    ):
        """
        Initialize SEC EDGAR connector.
        
        Args:
            user_agent: Required by SEC - format: "AppName contact@email.com"
        """
        super().__init__(api_key=None, **kwargs)
        self.user_agent = user_agent
        self.source_name = "SEC EDGAR"
    
    async def _make_request(
        self,
        url: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Override to add required User-Agent header."""
        headers = headers or {}
        headers["User-Agent"] = self.user_agent
        headers["Accept"] = "application/json"
        
        return await super()._make_request(url, method, params, headers)
    
    async def fetch_news(
        self,
        symbols: Optional[List[str]] = None,
        since: Optional[datetime] = None,
        limit: int = 50,
    ) -> List[NewsArticle]:
        """
        Fetch SEC filings as news articles.
        
        Converts SEC filings into NewsArticle format for unified
        processing with other news sources.
        
        Args:
            symbols: Stock symbols to fetch filings for
            since: Only return filings after this time
            limit: Maximum filings to return
            
        Returns:
            List of NewsArticle objects representing filings
        """
        all_articles = []
        
        if not symbols:
            # Fetch recent filings across all companies
            articles = await self._fetch_recent_filings(limit)
            all_articles.extend(articles)
        else:
            for symbol in symbols:
                try:
                    articles = await self._fetch_company_filings(symbol, limit)
                    all_articles.extend(articles)
                except Exception as e:
                    logger.error(f"Failed to fetch SEC filings for {symbol}: {e}")
        
        # Filter by time
        if since:
            all_articles = [a for a in all_articles if a.published_at >= since]
        
        self.articles_fetched += len(all_articles[:limit])
        return all_articles[:limit]
    
    async def _fetch_company_filings(
        self,
        symbol: str,
        limit: int,
    ) -> List[NewsArticle]:
        """Fetch filings for a specific company."""
        # Get CIK for symbol
        cik = await self._get_cik(symbol)
        if not cik:
            logger.warning(f"Could not find CIK for {symbol}")
            return []
        
        # Fetch submissions
        url = f"{self.base_url}/submissions/CIK{cik}.json"
        
        try:
            data = await self._make_request(url)
            
            # Parse recent filings
            recent = data.get("filings", {}).get("recent", {})
            
            forms = recent.get("form", [])
            dates = recent.get("filingDate", [])
            accessions = recent.get("accessionNumber", [])
            descriptions = recent.get("primaryDocument", [])
            
            articles = []
            company_name = data.get("name", symbol)
            
            for i in range(min(limit, len(forms))):
                form_type = forms[i]
                filing_date = dates[i]
                accession = accessions[i].replace("-", "")
                
                # Parse date
                try:
                    published_at = datetime.strptime(filing_date, "%Y-%m-%d")
                except ValueError:
                    published_at = datetime.utcnow()
                
                # Determine category
                category = self.FILING_CATEGORIES.get(form_type, NewsCategory.REGULATORY)
                
                # Build filing URL
                filing_url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type={form_type}"
                
                # Create descriptive title
                title = f"{company_name} ({symbol}) files {form_type}"
                summary = self._get_filing_description(form_type, company_name)
                
                article = NewsArticle(
                    title=title,
                    summary=summary,
                    url=filing_url,
                    source=self.source,
                    source_name="SEC EDGAR",
                    published_at=published_at,
                    symbols=[symbol],
                    categories=[category, NewsCategory.REGULATORY],
                    metadata={
                        "filing_type": form_type,
                        "accession_number": accession,
                        "cik": cik,
                        "company_name": company_name,
                    },
                )
                articles.append(article)
            
            return articles
            
        except Exception as e:
            logger.error(f"Failed to fetch SEC submissions for {symbol}: {e}")
            return []
    
    async def _fetch_recent_filings(self, limit: int) -> List[NewsArticle]:
        """Fetch recent filings across all companies."""
        # Use SEC's RSS feed endpoint for recent filings
        url = "https://www.sec.gov/cgi-bin/browse-edgar"
        params = {
            "action": "getcurrent",
            "type": "",
            "company": "",
            "dateb": "",
            "owner": "include",
            "count": min(limit, 100),
            "output": "atom",
        }
        
        # Note: This returns Atom/RSS - would need to parse XML
        # For simplicity, return empty list - use company-specific fetching
        logger.info("Recent filings across all companies not implemented yet")
        return []
    
    async def _get_cik(self, symbol: str) -> Optional[str]:
        """Get CIK (Central Index Key) for a stock symbol."""
        # Check cache first
        if symbol in self.SYMBOL_TO_CIK:
            return self.SYMBOL_TO_CIK[symbol]
        
        # Fetch from SEC tickers endpoint
        try:
            url = "https://www.sec.gov/files/company_tickers.json"
            data = await self._make_request(url)
            
            for entry in data.values():
                if entry.get("ticker", "").upper() == symbol.upper():
                    cik = str(entry.get("cik_str", "")).zfill(10)
                    self.SYMBOL_TO_CIK[symbol] = cik
                    return cik
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get CIK for {symbol}: {e}")
            return None
    
    def _get_filing_description(self, form_type: str, company: str) -> str:
        """Get human-readable description for a filing type."""
        descriptions = {
            "10-K": f"Annual report filed by {company}. Contains audited financial statements, MD&A, and business overview.",
            "10-Q": f"Quarterly report filed by {company}. Contains unaudited financial statements and updates.",
            "8-K": f"Current report filed by {company}. Discloses material events or corporate changes.",
            "4": f"Insider trading report. A director, officer, or 10% owner of {company} reported a transaction.",
            "13F": f"Quarterly institutional holdings report showing positions in {company}.",
            "SC 13D": f"Beneficial ownership report. An entity acquired more than 5% of {company} with intent to influence.",
            "SC 13G": f"Passive beneficial ownership report for {company}.",
            "DEF 14A": f"Proxy statement filed by {company} for upcoming shareholder meeting.",
            "S-1": f"Registration statement for securities offering by {company}.",
        }
        return descriptions.get(form_type, f"{form_type} filing by {company}")
    
    async def fetch_filings(
        self,
        symbol: str,
        form_types: Optional[List[str]] = None,
        since: Optional[datetime] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Fetch specific filing types for a symbol.
        
        Args:
            symbol: Stock symbol
            form_types: List of form types to filter (e.g., ["10-K", "10-Q", "8-K"])
            since: Only return filings after this date
            limit: Maximum filings to return
            
        Returns:
            List of filing dictionaries with metadata
        """
        cik = await self._get_cik(symbol)
        if not cik:
            return []
        
        url = f"{self.base_url}/submissions/CIK{cik}.json"
        
        try:
            data = await self._make_request(url)
            recent = data.get("filings", {}).get("recent", {})
            
            forms = recent.get("form", [])
            dates = recent.get("filingDate", [])
            accessions = recent.get("accessionNumber", [])
            docs = recent.get("primaryDocument", [])
            descriptions = recent.get("primaryDocDescription", [])
            
            filings = []
            for i in range(len(forms)):
                form = forms[i]
                
                # Filter by form type
                if form_types and form not in form_types:
                    continue
                
                # Parse date
                try:
                    filing_date = datetime.strptime(dates[i], "%Y-%m-%d")
                except ValueError:
                    continue
                
                # Filter by date
                if since and filing_date < since:
                    continue
                
                accession = accessions[i].replace("-", "")
                doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/{accession}/{docs[i]}"
                
                filings.append({
                    "symbol": symbol,
                    "cik": cik,
                    "form_type": form,
                    "filing_date": filing_date.isoformat(),
                    "accession_number": accessions[i],
                    "document_url": doc_url,
                    "description": descriptions[i] if i < len(descriptions) else "",
                })
                
                if len(filings) >= limit:
                    break
            
            return filings
            
        except Exception as e:
            logger.error(f"Failed to fetch SEC filings: {e}")
            return []
    
    async def fetch_insider_trading(
        self,
        symbol: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Fetch Form 4 insider trading reports.
        
        Args:
            symbol: Stock symbol
            limit: Maximum reports to return
            
        Returns:
            List of insider trading reports
        """
        return await self.fetch_filings(
            symbol=symbol,
            form_types=["4", "3", "5"],  # Form 3, 4, 5 are insider reports
            limit=limit,
        )

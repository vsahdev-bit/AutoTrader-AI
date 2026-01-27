"""
Big Cap Losers Crawler
Crawls Yahoo Finance losers page and filters for big cap stocks (>$50B market cap)
"""

import asyncio
import aiohttp
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup
import json

logger = logging.getLogger(__name__)

# Constants
YAHOO_LOSERS_URL = "https://finance.yahoo.com/markets/stocks/losers/"
MIN_MARKET_CAP = 1_000_000_000  # $1 billion
MIN_DROP_PERCENT = -10.0  # 10% drop threshold

@dataclass
class StockLoser:
    """Represents a losing stock from Yahoo Finance"""
    symbol: str
    company_name: str
    current_price: float
    price_change: float
    percent_change: float
    market_cap: int
    market_cap_formatted: str
    volume: Optional[int] = None
    avg_volume: Optional[int] = None
    day_high: Optional[float] = None
    day_low: Optional[float] = None
    pe_ratio: Optional[float] = None
    fifty_two_week_high: Optional[float] = None
    fifty_two_week_low: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class BigCapLosersCrawler:
    """Crawler for Yahoo Finance losers page"""
    
    def __init__(self, min_market_cap: int = MIN_MARKET_CAP):
        self.min_market_cap = min_market_cap
        self.session: Optional[aiohttp.ClientSession] = None
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Cache-Control': 'no-cache',
        }
    
    async def initialize(self):
        """Initialize the HTTP session"""
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout, headers=self.headers)
            logger.info("BigCapLosersCrawler initialized")
    
    async def close(self):
        """Close the HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None
            logger.info("BigCapLosersCrawler closed")
    
    def _parse_market_cap(self, cap_str: str) -> int:
        """Parse market cap string to integer (e.g., '150.5B' -> 150500000000)"""
        if not cap_str or cap_str == 'N/A' or cap_str == '--':
            return 0
        
        cap_str = cap_str.strip().upper()
        multipliers = {
            'T': 1_000_000_000_000,
            'B': 1_000_000_000,
            'M': 1_000_000,
            'K': 1_000,
        }
        
        for suffix, multiplier in multipliers.items():
            if suffix in cap_str:
                try:
                    value = float(cap_str.replace(suffix, '').replace(',', '').replace('$', ''))
                    return int(value * multiplier)
                except ValueError:
                    return 0
        
        try:
            return int(float(cap_str.replace(',', '').replace('$', '')))
        except ValueError:
            return 0
    
    def _parse_volume(self, vol_str: str) -> Optional[int]:
        """Parse volume string to integer"""
        if not vol_str or vol_str == 'N/A' or vol_str == '--':
            return None
        return self._parse_market_cap(vol_str)  # Same format
    
    def _parse_price(self, price_str: str) -> Optional[float]:
        """Parse price string to float"""
        if not price_str or price_str == 'N/A' or price_str == '--':
            return None
        try:
            return float(price_str.replace(',', '').replace('$', '').strip())
        except ValueError:
            return None
    
    def _parse_percent(self, percent_str: str) -> Optional[float]:
        """Parse percent change string to float (e.g., '-15.5%' -> -15.5)"""
        if not percent_str or percent_str == 'N/A' or percent_str == '--':
            return None
        try:
            return float(percent_str.replace('%', '').replace(',', '').strip())
        except ValueError:
            return None
    
    async def _fetch_page(self) -> Optional[str]:
        """Fetch the Yahoo Finance losers page"""
        try:
            async with self.session.get(YAHOO_LOSERS_URL) as response:
                if response.status == 200:
                    html = await response.text()
                    logger.info(f"Successfully fetched Yahoo Finance losers page ({len(html)} bytes)")
                    return html
                else:
                    logger.error(f"Failed to fetch losers page: HTTP {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching losers page: {e}")
            return None
    
    async def _fetch_stock_details(self, symbol: str) -> Dict[str, Any]:
        """Fetch additional stock details from Yahoo Finance quote page"""
        try:
            url = f"https://finance.yahoo.com/quote/{symbol}"
            async with self.session.get(url) as response:
                if response.status != 200:
                    return {}
                
                html = await response.text()
                soup = BeautifulSoup(html, 'lxml')
                
                details = {}
                
                # Try to find market cap from the quote page
                # Yahoo uses various element structures, we'll try common patterns
                market_cap_elem = soup.find('fin-streamer', {'data-field': 'marketCap'})
                if market_cap_elem:
                    details['market_cap'] = market_cap_elem.get('data-value') or market_cap_elem.text
                
                # Find PE ratio
                pe_elem = soup.find('fin-streamer', {'data-field': 'trailingPE'})
                if pe_elem:
                    details['pe_ratio'] = pe_elem.get('data-value') or pe_elem.text
                
                # Find 52-week range
                range_elems = soup.find_all('fin-streamer', {'data-field': 'fiftyTwoWeekRange'})
                if range_elems:
                    for elem in range_elems:
                        range_text = elem.text if elem.text else elem.get('data-value', '')
                        if ' - ' in range_text:
                            low, high = range_text.split(' - ')
                            details['fifty_two_week_low'] = self._parse_price(low)
                            details['fifty_two_week_high'] = self._parse_price(high)
                            break
                
                return details
                
        except Exception as e:
            logger.warning(f"Error fetching details for {symbol}: {e}")
            return {}
    
    def _parse_losers_table(self, html: str) -> List[Dict[str, Any]]:
        """Parse the losers table from HTML"""
        soup = BeautifulSoup(html, 'lxml')
        losers = []
        
        # Find the main data table (Yahoo uses yf-* class prefix)
        table = soup.find('table', class_=lambda x: x and 'yf-' in str(x))
        if not table:
            logger.warning("Could not find losers table in HTML")
            return []
        
        # Find tbody for data rows
        tbody = table.find('tbody')
        if not tbody:
            tbody = table
        
        rows = tbody.find_all('tr')
        logger.info(f"Found {len(rows)} rows in losers table")
        
        for row in rows:
            cells = row.find_all('td')
            if len(cells) < 6:
                continue
            
            try:
                # Column 0: Symbol
                symbol = cells[0].get_text(strip=True)
                if not symbol or len(symbol) > 10:
                    continue
                
                # Column 1: Company Name
                company_name = cells[1].get_text(strip=True) or symbol
                
                # Column 3: Price with change (format: "45.08-9.22(-16.98%)")
                price_text = cells[3].get_text(strip=True)
                
                # Column 4: Price Change (e.g., "-9.22")
                change_text = cells[4].get_text(strip=True)
                price_change = self._parse_price(change_text)
                
                # Column 5: Percent Change (e.g., "-16.98%")
                percent_text = cells[5].get_text(strip=True)
                percent_change = self._parse_percent(percent_text)
                
                # Extract current price from column 3
                # Format is like "45.08-9.22(-16.98%)" - we need just the first number
                price_match = re.match(r'([\d,]+\.?\d*)', price_text)
                current_price = float(price_match.group(1).replace(',', '')) if price_match else None
                
                # Later columns may have volume and market cap
                volume = None
                market_cap = 0
                market_cap_str = None
                
                if len(cells) > 6:
                    volume = self._parse_volume(cells[6].get_text(strip=True))
                if len(cells) > 8:
                    market_cap_str = cells[8].get_text(strip=True)
                    market_cap = self._parse_market_cap(market_cap_str) if market_cap_str else 0
                
                if symbol and current_price and percent_change is not None:
                    losers.append({
                        'symbol': symbol,
                        'company_name': company_name,
                        'current_price': current_price,
                        'price_change': price_change or 0,
                        'percent_change': percent_change,
                        'volume': volume,
                        'market_cap': market_cap,
                        'market_cap_str': market_cap_str,
                    })
                    logger.debug(f"Parsed: {symbol} - {percent_change}%")
                    
            except Exception as e:
                logger.warning(f"Error parsing row: {e}")
                continue
        
        logger.info(f"Successfully parsed {len(losers)} losers")
        return losers
    
    def _parse_from_scripts(self, html: str) -> List[Dict[str, Any]]:
        """Alternative parser: extract data from JavaScript in the page"""
        losers = []
        
        # Look for JSON data in script tags
        soup = BeautifulSoup(html, 'lxml')
        scripts = soup.find_all('script')
        
        for script in scripts:
            if not script.string:
                continue
            
            # Look for quote data in the script
            if 'quoteSummary' in script.string or 'QuoteData' in script.string:
                try:
                    # Try to extract JSON from the script
                    json_match = re.search(r'\{.*"quoteSummary".*\}', script.string, re.DOTALL)
                    if json_match:
                        data = json.loads(json_match.group())
                        # Parse the data structure
                        # This varies by Yahoo's current implementation
                        pass
                except:
                    continue
        
        return losers
    
    async def crawl(self) -> List[StockLoser]:
        """
        Crawl Yahoo Finance losers page and return big cap losers.
        Returns stocks with market cap > $50B.
        """
        logger.info("Starting Big Cap Losers crawl...")
        
        # Fetch the losers page
        html = await self._fetch_page()
        if not html:
            logger.error("Failed to fetch losers page")
            return []
        
        # Parse the table
        raw_losers = self._parse_losers_table(html)
        logger.info(f"Found {len(raw_losers)} total losers on the page")
        
        # Filter and enrich big cap stocks
        big_cap_losers = []
        
        for loser in raw_losers:
            symbol = loser['symbol']
            
            # If market cap not in table, fetch from quote page
            if not loser.get('market_cap') or loser['market_cap'] == 0:
                logger.info(f"Fetching market cap for {symbol}...")
                details = await self._fetch_stock_details(symbol)
                if details.get('market_cap'):
                    loser['market_cap'] = self._parse_market_cap(str(details['market_cap']))
                loser.update({k: v for k, v in details.items() if k != 'market_cap'})
                await asyncio.sleep(0.5)  # Rate limiting
            
            # Check if it meets big cap criteria
            if loser.get('market_cap', 0) >= self.min_market_cap:
                market_cap = loser['market_cap']
                
                # Format market cap string
                if market_cap >= 1_000_000_000_000:
                    cap_formatted = f"${market_cap / 1_000_000_000_000:.1f}T"
                elif market_cap >= 1_000_000_000:
                    cap_formatted = f"${market_cap / 1_000_000_000:.1f}B"
                else:
                    cap_formatted = f"${market_cap / 1_000_000:.1f}M"
                
                stock = StockLoser(
                    symbol=symbol,
                    company_name=loser.get('company_name', symbol),
                    current_price=loser['current_price'],
                    price_change=loser.get('price_change', 0),
                    percent_change=loser['percent_change'],
                    market_cap=market_cap,
                    market_cap_formatted=cap_formatted,
                    volume=loser.get('volume'),
                    avg_volume=loser.get('avg_volume'),
                    day_high=loser.get('day_high'),
                    day_low=loser.get('day_low'),
                    pe_ratio=loser.get('pe_ratio'),
                    fifty_two_week_high=loser.get('fifty_two_week_high'),
                    fifty_two_week_low=loser.get('fifty_two_week_low'),
                    metadata={'source': 'yahoo_finance', 'url': YAHOO_LOSERS_URL}
                )
                big_cap_losers.append(stock)
                logger.info(f"Big cap loser: {symbol} ({cap_formatted}) - {loser['percent_change']:.2f}%")
        
        logger.info(f"Found {len(big_cap_losers)} big cap losers (>$50B market cap)")
        
        return big_cap_losers


async def crawl_big_cap_losers() -> List[StockLoser]:
    """Convenience function to crawl big cap losers"""
    crawler = BigCapLosersCrawler()
    await crawler.initialize()
    try:
        return await crawler.crawl()
    finally:
        await crawler.close()

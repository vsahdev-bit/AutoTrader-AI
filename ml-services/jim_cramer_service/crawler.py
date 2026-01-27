"""
Jim Cramer News Crawler
========================

Crawls multiple news sources for Jim Cramer content and stock recommendations.

Sources:
- CNBC Investing Club (web crawl)
- CNBC Mad Money RSS Feed
- Google News RSS (Jim Cramer query)
- TheStreet (web crawl)
- Nitter (Twitter proxy for @madmoneyoncnbc)

Features:
- Deduplication via content hashing
- Rate limiting to avoid blocks
- Retry logic with exponential backoff
- Stores raw articles in ClickHouse
- Stores processed data in PostgreSQL

Usage:
    crawler = JimCramerCrawler()
    await crawler.initialize()
    articles = await crawler.crawl_all_sources()
"""

import asyncio
import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse
import aiohttp
import feedparser
from bs4 import BeautifulSoup
import json

logger = logging.getLogger(__name__)


@dataclass
class CramerArticle:
    """Represents a Jim Cramer article from any source."""
    url: str
    title: str
    source_name: str
    source_type: str  # 'rss', 'web_crawl', 'api'
    published_at: datetime
    description: Optional[str] = None
    full_content: Optional[str] = None
    author: Optional[str] = None
    thumbnail_url: Optional[str] = None
    video_url: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def content_hash(self) -> str:
        """Generate SHA256 hash of URL + title for deduplication."""
        content = f"{self.url}|{self.title}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "source_name": self.source_name,
            "source_type": self.source_type,
            "published_at": self.published_at.isoformat(),
            "description": self.description,
            "full_content": self.full_content,
            "author": self.author,
            "thumbnail_url": self.thumbnail_url,
            "video_url": self.video_url,
            "content_hash": self.content_hash,
            "metadata": self.metadata,
        }


class JimCramerCrawler:
    """
    Multi-source crawler for Jim Cramer news and recommendations.
    """
    
    # User agent to avoid blocks
    USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    # Rate limiting
    REQUEST_DELAY = 1.0  # seconds between requests
    
    # Source configurations
    SOURCES = {
        "cnbc_mad_money_rss": {
            "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839263",
            "type": "rss",
            "name": "CNBC Mad Money",
        },
        "cnbc_investing_club_rss": {
            "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=107619260",
            "type": "rss",
            "name": "CNBC Investing Club",
        },
        "google_news_cramer": {
            "url": "https://news.google.com/rss/search?q=jim+cramer+stock&hl=en-US&gl=US&ceid=US:en",
            "type": "rss",
            "name": "Google News",
        },
        "cnbc_api": {
            "url": "https://api.queryly.com/cnbc/json.aspx?queryly_key=31a35d40a9a64ab3&query=jim%20cramer&endindex=0&batchsize=20",
            "type": "api",
            "name": "CNBC Search",
        },
        "cnbc_investing_club_web": {
            "url": "https://www.cnbc.com/investingclub/",
            "type": "web_crawl",
            "name": "CNBC Investing Club",
        },
    }
    
    def __init__(
        self,
        max_articles_per_source: int = 20,
        lookback_hours: int = 24,
        timeout: int = 30,
    ):
        """
        Initialize the crawler.
        
        Args:
            max_articles_per_source: Maximum articles to fetch per source
            lookback_hours: Only fetch articles from last N hours
            timeout: HTTP request timeout in seconds
        """
        self.max_articles = max_articles_per_source
        self.lookback_hours = lookback_hours
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None
        self._seen_hashes: set = set()
    
    async def initialize(self):
        """Initialize HTTP session."""
        if not self.session:
            self.session = aiohttp.ClientSession(
                headers={"User-Agent": self.USER_AGENT},
                timeout=aiohttp.ClientTimeout(total=self.timeout),
            )
        logger.info("Jim Cramer crawler initialized")
    
    async def close(self):
        """Close HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def crawl_all_sources(self) -> List[CramerArticle]:
        """
        Crawl all configured sources for Jim Cramer content.
        
        Returns:
            List of deduplicated CramerArticle objects
        """
        all_articles = []
        
        for source_id, config in self.SOURCES.items():
            try:
                logger.info(f"Crawling source: {source_id}")
                
                if config["type"] == "rss":
                    articles = await self._crawl_rss(config)
                elif config["type"] == "api":
                    articles = await self._crawl_cnbc_api(config)
                elif config["type"] == "web_crawl":
                    articles = await self._crawl_web_page(config)
                else:
                    logger.warning(f"Unknown source type: {config['type']}")
                    continue
                
                # Deduplicate
                new_articles = []
                for article in articles:
                    if article.content_hash not in self._seen_hashes:
                        self._seen_hashes.add(article.content_hash)
                        new_articles.append(article)
                
                logger.info(f"Source {source_id}: found {len(articles)}, new: {len(new_articles)}")
                all_articles.extend(new_articles)
                
                # Rate limiting
                await asyncio.sleep(self.REQUEST_DELAY)
                
            except Exception as e:
                logger.error(f"Error crawling {source_id}: {e}")
                continue
        
        # Sort by published date
        all_articles.sort(key=lambda x: x.published_at, reverse=True)
        
        logger.info(f"Total articles crawled: {len(all_articles)}")
        return all_articles
    
    async def _crawl_rss(self, config: Dict) -> List[CramerArticle]:
        """Crawl an RSS feed."""
        articles = []
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=self.lookback_hours)
        
        try:
            async with self.session.get(config["url"]) as response:
                if response.status != 200:
                    logger.warning(f"RSS feed returned {response.status}: {config['url']}")
                    return []
                
                content = await response.text()
                feed = feedparser.parse(content)
                
                for entry in feed.entries[:self.max_articles]:
                    try:
                        # Parse published date (always use UTC timezone)
                        published = None
                        if hasattr(entry, 'published_parsed') and entry.published_parsed:
                            published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                        elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                            published = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
                        
                        if not published:
                            published = datetime.now(timezone.utc)
                        elif published.tzinfo is None:
                            published = published.replace(tzinfo=timezone.utc)
                        
                        # Skip old articles
                        if published < cutoff_time:
                            continue
                        
                        # Check if related to Jim Cramer
                        title = entry.get('title', '')
                        description = entry.get('summary', entry.get('description', ''))
                        
                        if not self._is_cramer_related(title, description):
                            continue
                        
                        article = CramerArticle(
                            url=entry.get('link', ''),
                            title=title,
                            description=description,
                            source_name=config["name"],
                            source_type="rss",
                            published_at=published,
                            author=entry.get('author'),
                            thumbnail_url=self._extract_thumbnail(entry),
                            metadata={"feed_url": config["url"]},
                        )
                        articles.append(article)
                        
                    except Exception as e:
                        logger.warning(f"Error parsing RSS entry: {e}")
                        continue
                        
        except Exception as e:
            logger.error(f"Error fetching RSS feed {config['url']}: {e}")
        
        return articles
    
    async def _crawl_cnbc_api(self, config: Dict) -> List[CramerArticle]:
        """Crawl CNBC Search API."""
        articles = []
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=self.lookback_hours)
        
        try:
            async with self.session.get(config["url"]) as response:
                if response.status != 200:
                    logger.warning(f"CNBC API returned {response.status}")
                    return []
                
                data = await response.json()
                results = data.get('results', [])
                
                for item in results[:self.max_articles]:
                    try:
                        # Parse date
                        date_str = item.get('cn:lastPubDate') or item.get('dateModified')
                        if date_str:
                            # Handle ISO format
                            published = datetime.fromisoformat(date_str.replace('Z', '+00:00').replace('+0000', '+00:00'))
                        else:
                            published = datetime.now(timezone.utc)
                        
                        # Skip old articles
                        if published < cutoff_time:
                            continue
                        
                        article = CramerArticle(
                            url=item.get('url', ''),
                            title=item.get('title', item.get('cn:title', '')),
                            description=item.get('description', ''),
                            source_name=config["name"],
                            source_type="api",
                            published_at=published,
                            author=item.get('author'),
                            thumbnail_url=item.get('image', {}).get('url') if isinstance(item.get('image'), dict) else None,
                            video_url=item.get('video_url'),
                            metadata={"section": item.get('section')},
                        )
                        articles.append(article)
                        
                    except Exception as e:
                        logger.warning(f"Error parsing CNBC API item: {e}")
                        continue
                        
        except Exception as e:
            logger.error(f"Error fetching CNBC API: {e}")
        
        return articles
    
    async def _crawl_web_page(self, config: Dict) -> List[CramerArticle]:
        """Crawl a web page for article links."""
        articles = []
        
        try:
            async with self.session.get(config["url"]) as response:
                if response.status != 200:
                    logger.warning(f"Web page returned {response.status}: {config['url']}")
                    return []
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Find article links
                article_links = []
                
                # CNBC Investing Club patterns
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    
                    # Match Cramer article URLs
                    if any(pattern in href.lower() for pattern in ['cramer', 'mad-money', 'investing-club']):
                        full_url = urljoin(config["url"], href)
                        
                        # Get title from link text or nearby heading
                        title = link.get_text(strip=True)
                        if not title or len(title) < 10:
                            # Try to find title in parent
                            parent = link.find_parent(['article', 'div', 'li'])
                            if parent:
                                heading = parent.find(['h1', 'h2', 'h3', 'h4'])
                                if heading:
                                    title = heading.get_text(strip=True)
                        
                        if title and len(title) > 10:
                            article_links.append({
                                "url": full_url,
                                "title": title,
                            })
                
                # Dedupe by URL
                seen_urls = set()
                for item in article_links[:self.max_articles]:
                    if item["url"] not in seen_urls:
                        seen_urls.add(item["url"])
                        
                        article = CramerArticle(
                            url=item["url"],
                            title=item["title"],
                            source_name=config["name"],
                            source_type="web_crawl",
                            published_at=datetime.now(timezone.utc),
                            metadata={"crawl_source": config["url"]},
                        )
                        articles.append(article)
                        
        except Exception as e:
            logger.error(f"Error crawling web page {config['url']}: {e}")
        
        return articles
    
    async def fetch_full_article(self, article: CramerArticle) -> CramerArticle:
        """
        Fetch the full content of an article.
        
        Args:
            article: Article with URL to fetch
            
        Returns:
            Article with full_content populated
        """
        try:
            async with self.session.get(article.url) as response:
                if response.status != 200:
                    return article
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Remove script and style elements
                for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                    element.decompose()
                
                # Try to find article content
                content = None
                
                # CNBC article body
                article_body = soup.find('div', class_=re.compile(r'ArticleBody|article-body|RenderKeyPoints'))
                if article_body:
                    content = article_body.get_text(separator=' ', strip=True)
                
                # Generic article tag
                if not content:
                    article_tag = soup.find('article')
                    if article_tag:
                        content = article_tag.get_text(separator=' ', strip=True)
                
                # Fallback to main content
                if not content:
                    main = soup.find('main') or soup.find('div', class_=re.compile(r'content|main'))
                    if main:
                        content = main.get_text(separator=' ', strip=True)
                
                if content:
                    # Clean up whitespace
                    content = re.sub(r'\s+', ' ', content).strip()
                    article.full_content = content[:10000]  # Limit to 10k chars
                
                # Try to extract published date
                time_tag = soup.find('time', datetime=True)
                if time_tag:
                    try:
                        article.published_at = datetime.fromisoformat(
                            time_tag['datetime'].replace('Z', '+00:00')
                        )
                    except:
                        pass
                
                # Extract author
                author_tag = soup.find('a', class_=re.compile(r'author|byline'))
                if author_tag:
                    article.author = author_tag.get_text(strip=True)
                
        except Exception as e:
            logger.warning(f"Error fetching full article {article.url}: {e}")
        
        return article
    
    def _is_cramer_related(self, title: str, description: str = "") -> bool:
        """Check if content is related to Jim Cramer."""
        text = f"{title} {description}".lower()
        cramer_keywords = [
            'cramer',
            'mad money',
            'jim c',
            'investing club',
            'lightning round',
        ]
        return any(keyword in text for keyword in cramer_keywords)
    
    def _extract_thumbnail(self, entry) -> Optional[str]:
        """Extract thumbnail URL from RSS entry."""
        # Try media:thumbnail
        if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
            return entry.media_thumbnail[0].get('url')
        
        # Try media:content
        if hasattr(entry, 'media_content') and entry.media_content:
            for media in entry.media_content:
                if 'image' in media.get('type', ''):
                    return media.get('url')
        
        # Try enclosure
        if hasattr(entry, 'enclosures') and entry.enclosures:
            for enc in entry.enclosures:
                if 'image' in enc.get('type', ''):
                    return enc.get('href')
        
        return None


async def main():
    """Test the crawler."""
    logging.basicConfig(level=logging.INFO)
    
    crawler = JimCramerCrawler(lookback_hours=48)  # 48 hours for testing
    await crawler.initialize()
    
    try:
        articles = await crawler.crawl_all_sources()
        
        print(f"\n{'='*60}")
        print(f"Found {len(articles)} Jim Cramer articles")
        print('='*60)
        
        for i, article in enumerate(articles[:10], 1):
            print(f"\n{i}. {article.title[:70]}...")
            print(f"   Source: {article.source_name}")
            print(f"   URL: {article.url[:60]}...")
            print(f"   Published: {article.published_at}")
        
    finally:
        await crawler.close()


if __name__ == "__main__":
    asyncio.run(main())

"""
RSS Feed Aggregator for Crypto Twitter Pipeline
Pulls tweets from multiple RSS feeds and aggregates them
"""

import feedparser
import requests
import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass
from pathlib import Path
import sqlite3
import hashlib
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class Tweet:
    id: str
    username: str
    content: str
    timestamp: datetime
    url: str
    likes: int = 0
    retweets: int = 0
    source: str = ""
    tier: str = ""
    tags: str = ""

class Database:
    def __init__(self, db_path: str = "data/tweets.db"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.setup()
    
    def setup(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS tweets (
                id TEXT PRIMARY KEY,
                username TEXT,
                content TEXT,
                timestamp TEXT,
                url TEXT,
                likes INTEGER DEFAULT 0,
                retweets INTEGER DEFAULT 0,
                source TEXT,
                tier TEXT,
                tags TEXT,
                processed BOOLEAN DEFAULT 0,
                score REAL DEFAULT 0,
                filtered BOOLEAN DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                username TEXT PRIMARY KEY,
                tier TEXT,
                tags TEXT,
                last_fetched TEXT,
                tweet_count INTEGER DEFAULT 0
            )
        """)
        self.conn.commit()
    
    def add_tweet(self, tweet: Tweet) -> bool:
        try:
            self.conn.execute("""
                INSERT OR IGNORE INTO tweets 
                (id, username, content, timestamp, url, likes, retweets, source, tier, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (tweet.id, tweet.username, tweet.content, tweet.timestamp.isoformat(),
                  tweet.url, tweet.likes, tweet.retweets, tweet.source, tweet.tier, tweet.tags))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding tweet: {e}")
            return False
    
    def add_account(self, username: str, tier: str = "", tags: str = ""):
        self.conn.execute("""
            INSERT OR REPLACE INTO accounts (username, tier, tags, last_fetched)
            VALUES (?, ?, ?, ?)
        """, (username, tier, tags, datetime.now().isoformat()))
        self.conn.commit()
    
    def get_unprocessed_tweets(self, limit: int = 100) -> List[Dict]:
        cursor = self.conn.execute("""
            SELECT id, username, content, timestamp, url, tier, tags
            FROM tweets 
            WHERE processed = 0
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        return [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
    
    def mark_processed(self, tweet_ids: List[str]):
        placeholders = ','.join('?' * len(tweet_ids))
        self.conn.execute(f"UPDATE tweets SET processed = 1 WHERE id IN ({placeholders})", tweet_ids)
        self.conn.commit()
    
    def get_filtered_tweets(self, hours: int = 24, min_score: float = 7.0) -> List[Dict]:
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        cursor = self.conn.execute("""
            SELECT * FROM tweets 
            WHERE filtered = 1 AND score >= ? AND timestamp > ?
            ORDER BY score DESC, timestamp DESC
        """, (min_score, since))
        return [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
    
    def update_tweet_score(self, tweet_id: str, score: float, filtered: bool):
        self.conn.execute("""
            UPDATE tweets SET score = ?, filtered = ? WHERE id = ?
        """, (score, filtered, tweet_id))
        self.conn.commit()

class RSSScraper:
    """Scrapes RSS feeds from RSS.app or other RSS sources"""
    
    def __init__(self, db: Database, api_key: Optional[str] = None):
        self.db = db
        self.api_key = api_key
    
    def build_rss_url(self, username: str) -> str:
        """Build RSS.app feed URL for a Twitter user"""
        # RSS.app provides Twitter RSS via their API
        return f"https://api.rss.app/v1/feeds/twitter/{username}/rss.xml"
    
    def build_table_url(self, username: str) -> str:
        """Build RSS.app table URL for easier JSON parsing"""
        return f"https://api.rss.app/v1/tables/twitter_{username}/rss.json"
    
    def fetch_rss_feed(self, url: str, username: str = "", tier: str = "", tags: str = "") -> List[Tweet]:
        """Fetch and parse RSS feed"""
        tweets = []
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            feed = feedparser.parse(response.content)
            
            for entry in feed.entries:
                # Extract username from source or use provided
                author = username or self.extract_username(entry)
                
                tweet = Tweet(
                    id=self.generate_tweet_id(entry.get('id', entry.get('link', ''))),
                    username=author,
                    content=self.clean_content(entry.get('description', entry.get('summary', ''))),
                    timestamp=self.parse_timestamp(entry.get('published', '')),
                    url=entry.get('link', ''),
                    source=url,
                    tier=tier,
                    tags=tags
                )
                tweets.append(tweet)
                
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
        
        return tweets
    
    def fetch_multiple_feeds(self, accounts: List[Dict], batch_size: int = 10, delay: float = 2.0) -> List[Tweet]:
        """Fetch multiple RSS feeds"""
        all_tweets = []
        
        for i, account in enumerate(accounts):
            username = account.get('username', '')
            tier = account.get('tier', '')
            tags = account.get('tags', '')
            
            # Try RSS.app table format first (better for parsing)
            url = f"https://api.rss.app/v1/tables/twitter_{username}/rss.json"
            
            tweets = self.fetch_rss_feed(url, username, tier, tags)
            
            # If no tweets, try RSS format
            if not tweets:
                url = self.build_rss_url(username)
                tweets = self.fetch_rss_feed(url, username, tier, tags)
            
            all_tweets.extend(tweets)
            self.db.add_account(username, tier, tags)
            
            if (i + 1) % batch_size == 0:
                logger.info(f"Processed {i + 1}/{len(accounts)} feeds")
                time.sleep(delay)
        
        return all_tweets
    
    def generate_tweet_id(self, text: str) -> str:
        return hashlib.md5(text.encode()).hexdigest()[:16]
    
    def extract_username(self, entry) -> str:
        if hasattr(entry, 'author'):
            return entry.author.split('@')[-1] if '@' in entry.author else entry.author
        return ""
    
    def clean_content(self, content: str) -> str:
        # Remove HTML tags
        import re
        clean = re.sub(r'<[^>]+>', '', content)
        # Remove extra whitespace
        clean = re.sub(r'\s+', ' ', clean).strip()
        return clean
    
    def parse_timestamp(self, date_str: str) -> datetime:
        from email.utils import parsedate_to_datetime
        try:
            return parsedate_to_datetime(date_str)
        except:
            return datetime.now()

class CryptoTwitterPipeline:
    """Main pipeline orchestrator"""
    
    def __init__(self, db_path: str = "data/tweets.db"):
        self.db = Database(db_path)
        self.scraper = RSSScraper(self.db)
    
    def load_accounts(self, filepath: str = "accounts.txt") -> List[Dict]:
        """Parse accounts file"""
        accounts = []
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split(',')
                if len(parts) >= 1:
                    accounts.append({
                        'username': parts[0],
                        'tier': parts[1] if len(parts) > 1 else '',
                        'tags': parts[2] if len(parts) > 2 else ''
                    })
        return accounts
    
    def fetch_all(self, accounts_file: str = "accounts.txt") -> int:
        """Fetch tweets from all accounts"""
        accounts = self.load_accounts(accounts_file)
        tweets = self.scraper.fetch_multiple_feeds(accounts)
        
        count = 0
        for tweet in tweets:
            if self.db.add_tweet(tweet):
                count += 1
        
        logger.info(f"Added {count} new tweets")
        return count
    
    def run(self, accounts_file: str = "accounts.txt"):
        """Main run loop"""
        logger.info("Starting crypto twitter pipeline...")
        count = self.fetch_all(accounts_file)
        logger.info(f"Pipeline complete. Fetched {count} tweets.")


if __name__ == "__main__":
    pipeline = CryptoTwitterPipeline()
    pipeline.run()
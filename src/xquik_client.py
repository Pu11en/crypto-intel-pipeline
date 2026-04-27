"""
Crypto Twitter Pipeline - Xquik + Fresh Data Only
Only includes tweets from last 48 hours
"""

import requests
import time
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass
from pathlib import Path
import sqlite3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load .env
def load_env():
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

load_env()

# Config
XQUIK_API_KEY = os.getenv('XQUIK_API_KEY', '')
BASE_URL = 'https://xquik.com/api/v1'
HEADERS = {'x-api-key': XQUIK_API_KEY, 'Content-Type': 'application/json'}

MAX_TWEET_AGE_HOURS = 48

@dataclass
class Tweet:
    id: str
    username: str
    text: str
    created_at: str
    likes: int
    retweets: int
    views: int
    url: str
    source: str = 'xquik'

def parse_twitter_date(date_str: str) -> Optional[datetime]:
    """Parse Twitter date format: 'Mon Apr 27 16:56:16 +0000 2026'"""
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(date_str)
    except:
        return None

def is_recent(tweet_created_at: str) -> bool:
    """Check if tweet is within MAX_TWEET_AGE_HOURS"""
    dt = parse_twitter_date(tweet_created_at)
    if dt is None:
        return False
    
    now = datetime.now(dt.tzinfo)
    age = now - dt
    return age.total_seconds() < (MAX_TWEET_AGE_HOURS * 3600)

class Database:
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent / 'data' / 'tweets.db'
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.setup()
    
    def setup(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS tweets (
                id TEXT PRIMARY KEY,
                username TEXT,
                text TEXT,
                created_at TEXT,
                likes INTEGER DEFAULT 0,
                retweets INTEGER DEFAULT 0,
                views INTEGER DEFAULT 0,
                url TEXT,
                source TEXT DEFAULT 'xquik',
                fetched_at TEXT DEFAULT CURRENT_TIMESTAMP,
                ai_score REAL DEFAULT 0,
                ai_category TEXT DEFAULT '',
                ai_hook TEXT DEFAULT ''
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                username TEXT PRIMARY KEY,
                user_id TEXT,
                tier TEXT,
                tags TEXT,
                followers INTEGER DEFAULT 0
            )
        """)
        # Index for time-based queries
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_tweets_created ON tweets(created_at)")
        self.conn.commit()
    
    def add_tweet(self, tweet: Tweet) -> bool:
        try:
            self.conn.execute("""
                INSERT OR IGNORE INTO tweets 
                (id, username, text, created_at, likes, retweets, views, url, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (tweet.id, tweet.username, tweet.text, tweet.created_at,
                  tweet.likes, tweet.retweets, tweet.views, tweet.url, tweet.source))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding tweet: {e}")
            return False
    
    def add_account(self, username: str, user_id: str = None, tier: str = "", 
                    tags: str = "", followers: int = 0):
        self.conn.execute("""
            INSERT OR REPLACE INTO accounts (username, user_id, tier, tags, followers)
            VALUES (?, ?, ?, ?, ?)
        """, (username, user_id, tier, tags, followers))
        self.conn.commit()
    
    def get_recent_tweets(self, hours: int = 48) -> List[Dict]:
        """Get tweets from last N hours, sorted by created_at"""
        cursor = self.conn.execute("""
            SELECT * FROM tweets 
            ORDER BY created_at DESC
        """)
        tweets = []
        for row in cursor.fetchall():
            tweet_dict = dict(zip([col[0] for col in cursor.description], row))
            if is_recent(tweet_dict['created_at']):
                tweets.append(tweet_dict)
        return tweets[:100]
    
    def get_top_tweets(self, min_score: float = 6.5) -> List[Dict]:
        """Get top scored tweets from last 48 hours"""
        tweets = self.get_recent_tweets(48)
        # Filter by score and sort
        scored = [t for t in tweets if t.get('ai_score', 0) >= min_score]
        return sorted(scored, key=lambda x: x.get('ai_score', 0), reverse=True)

class XquikClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base = BASE_URL
        self.headers = HEADERS
    
    def _get(self, path: str, params: dict = None, retries: int = 3) -> dict:
        for attempt in range(retries):
            resp = requests.get(f"{self.base}{path}", headers=self.headers, params=params)
            if resp.ok:
                return resp.json()
            if resp.status_code == 429 or resp.status_code >= 500:
                delay = 2 ** attempt
                logger.warning(f"Retry {attempt+1} after {delay}s...")
                time.sleep(delay)
            else:
                raise Exception(f"API error {resp.status_code}: {resp.text[:100]}")
        raise Exception("Max retries exceeded")
    
    def get_user_info(self, username: str) -> Optional[dict]:
        try:
            return self._get(f"/x/users/{username}")
        except Exception as e:
            logger.error(f"Error getting user {username}: {e}")
            return None
    
    def get_user_tweets(self, username: str, user_id: str = None, limit: int = 20) -> List[Tweet]:
        tweets = []
        
        if not user_id:
            user_info = self.get_user_info(username)
            if not user_info:
                return tweets
            user_id = user_info.get('id')
        
        try:
            params = {'max_results': min(limit, 100)}
            data = self._get(f"/x/users/{user_id}/tweets", params)
            
            for t in data.get('tweets', []):
                author = t.get('author', {})
                created_at = t.get('createdAt', '')
                
                # Only include recent tweets
                if not is_recent(created_at):
                    continue
                
                tweets.append(Tweet(
                    id=t.get('id', ''),
                    username=author.get('username', username),
                    text=t.get('text', ''),
                    created_at=created_at,
                    likes=t.get('likeCount', 0),
                    retweets=t.get('retweetCount', 0),
                    views=t.get('viewCount', 0),
                    url=f"https://x.com/{author.get('username', username)}/status/{t.get('id', '')}"
                ))
        except Exception as e:
            logger.error(f"Error fetching tweets for {username}: {e}")
        
        return tweets
    
    def get_balance(self) -> dict:
        try:
            data = self._get("/account")
            credits = data.get('creditInfo', {})
            return {
                'balance': int(float(credits.get('balance', 0))),
                'lifetime': float(credits.get('lifetimePurchased', 0))
            }
        except:
            return {'balance': 0, 'lifetime': 0}

class CryptoPipeline:
    def __init__(self):
        self.db = Database()
        self.xquik = XquikClient(XQUIK_API_KEY)
    
    def load_accounts(self, filepath: str = None) -> List[Dict]:
        if filepath is None:
            filepath = Path(__file__).parent.parent / 'accounts.txt'
        
        accounts = []
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split(',')
                accounts.append({
                    'username': parts[0],
                    'tier': parts[1] if len(parts) > 1 else '',
                    'tags': parts[2] if len(parts) > 2 else ''
                })
        return accounts
    
    def fetch_accounts(self, accounts_file: str = None, tweets_per_account: int = 20) -> Dict:
        accounts = self.load_accounts(accounts_file)
        
        stats = {
            'total_accounts': len(accounts),
            'fetched_accounts': 0,
            'total_tweets': 0,
            'recent_tweets': 0,
            'errors': []
        }
        
        logger.info(f"Fetching tweets from {len(accounts)} accounts...")
        
        for i, account in enumerate(accounts):
            username = account['username']
            
            user_info = self.xquik.get_user_info(username)
            if user_info:
                self.db.add_account(
                    username=username,
                    user_id=user_info.get('id'),
                    tier=account.get('tier', ''),
                    tags=account.get('tags', ''),
                    followers=user_info.get('followers', 0)
                )
                
                tweets = self.xquik.get_user_tweets(username, user_id=user_info.get('id'), limit=tweets_per_account)
                for tweet in tweets:
                    if self.db.add_tweet(tweet):
                        stats['total_tweets'] += 1
                        stats['recent_tweets'] += 1
                
                stats['fetched_accounts'] += 1
            else:
                stats['errors'].append(username)
            
            if (i + 1) % 20 == 0:
                logger.info(f"Progress: {i + 1}/{len(accounts)} accounts")
            
            time.sleep(0.3)
        
        logger.info(f"Done! {stats['recent_tweets']} recent tweets from {stats['fetched_accounts']} accounts")
        return stats

def run_pipeline():
    """Run the full pipeline"""
    print("="*60)
    print("CRYPTO PIPELINE - Fresh Data Only (48h)")
    print("="*60)
    
    pipeline = CryptoPipeline()
    
    balance = pipeline.xquik.get_balance()
    print(f"\n💰 Credits: {balance['balance']:,}")
    
    print("\n📡 Fetching recent tweets...")
    stats = pipeline.fetch_accounts()
    
    print(f"\n✅ {stats['recent_tweets']} tweets from last 48h")
    print(f"   {stats['fetched_accounts']}/{stats['total_accounts']} accounts")
    
    if stats['errors']:
        print(f"❌ Failed: {', '.join(stats['errors'][:5])}")
    
    return stats

if __name__ == "__main__":
    run_pipeline()
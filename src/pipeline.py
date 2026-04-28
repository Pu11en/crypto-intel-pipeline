"""
Crypto Twitter Intelligence Pipeline
Using Xquik API for Twitter data + DeepSeek for AI filtering

Setup:
1. Sign up at https://xquik.com
2. Get API key from dashboard
3. Add to .env: XQUIK_API_KEY=your_key
4. pip install requests python-dotenv

Cost estimate:
- $20/month subscription
- ~$0.00015 per tweet read
- 200 accounts x 20 tweets each = 4000 tweets
- Total: $20 + ~$0.60 = ~$20.60/month
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
import hashlib
import logging

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Xquik API config
XQUIK_API_KEY = os.getenv("XQUIK_API_KEY")
XQUIK_BASE = "https://xquik.com/api/v1"
XQUIK_HEADERS = {"x-api-key": XQUIK_API_KEY, "Content-Type": "application/json"}

# DeepSeek config
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE = "https://api.deepseek.com/v1"

@dataclass
class Tweet:
    id: str
    username: str
    text: str
    created_at: str
    likes: int = 0
    retweets: int = 0
    replies: int = 0
    views: int = 0
    url: str = ""
    source: str = "xquik"

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
                text TEXT,
                created_at TEXT,
                likes INTEGER DEFAULT 0,
                retweets INTEGER DEFAULT 0,
                replies INTEGER DEFAULT 0,
                views INTEGER DEFAULT 0,
                url TEXT,
                source TEXT,
                fetched_at TEXT,
                processed BOOLEAN DEFAULT 0,
                ai_score REAL DEFAULT 0,
                ai_category TEXT,
                filtered BOOLEAN DEFAULT 0,
                summary TEXT
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
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_digests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                summary TEXT,
                top_tweets TEXT,
                categories TEXT,
                created_at TEXT
            )
        """)
        self.conn.commit()
    
    def add_tweet(self, tweet: Tweet) -> bool:
        try:
            self.conn.execute("""
                INSERT OR IGNORE INTO tweets 
                (id, username, text, created_at, likes, retweets, replies, views, url, source, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (tweet.id, tweet.username, tweet.text, tweet.created_at,
                  tweet.likes, tweet.retweets, tweet.replies, tweet.views, tweet.url, tweet.source,
                  datetime.now().isoformat()))
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
    
    def get_unprocessed_tweets(self, hours: int = 6, limit: int = 100) -> List[Dict]:
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        cursor = self.conn.execute("""
            SELECT id, username, text, created_at, likes, retweets, views, url
            FROM tweets 
            WHERE processed = 0 AND fetched_at > ?
            ORDER BY fetched_at DESC
            LIMIT ?
        """, (since, limit))
        return [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
    
    def mark_processed(self, tweet_ids: List[str]):
        if not tweet_ids:
            return
        placeholders = ','.join('?' * len(tweet_ids))
        self.conn.execute(f"UPDATE tweets SET processed = 1 WHERE id IN ({placeholders})", tweet_ids)
        self.conn.commit()
    
    def update_tweet_ai(self, tweet_id: str, score: float, category: str, summary: str = ""):
        self.conn.execute("""
            UPDATE tweets SET ai_score = ?, ai_category = ?, summary = ?, filtered = 1 
            WHERE id = ?
        """, (score, category, summary, tweet_id))
        self.conn.commit()
    
    def get_filtered_tweets(self, hours: int = 24, min_score: float = 7.0) -> List[Dict]:
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        cursor = self.conn.execute("""
            SELECT * FROM tweets 
            WHERE filtered = 1 AND ai_score >= ? AND fetched_at > ?
            ORDER BY ai_score DESC, created_at DESC
            LIMIT 50
        """, (min_score, since))
        return [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
    
    def save_daily_digest(self, date: str, summary: str, top_tweets: List, categories: Dict):
        self.conn.execute("""
            INSERT INTO daily_digests (date, summary, top_tweets, categories, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (date, summary, json.dumps(top_tweets), json.dumps(categories), datetime.now().isoformat()))
        self.conn.commit()

class XquikClient:
    """Xquik API client for Twitter data"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base = XQUIK_BASE
        self.headers = {"x-api-key": api_key, "Content-Type": "application/json"}
    
    def _request(self, method: str, path: str, json_body: dict = None, max_retries: int = 3) -> dict:
        """Make request with retry logic"""
        base_delay = 1.0
        
        for attempt in range(max_retries + 1):
            response = requests.request(
                method,
                f"{self.base}{path}",
                headers=self.headers,
                json=json_body,
            )
            
            if response.ok:
                return response.json()
            
            retryable = response.status_code == 429 or response.status_code >= 500
            if not retryable or attempt == max_retries:
                error = response.json() if response.content else {}
                raise Exception(f"Xquik API {response.status_code}: {error.get('error', 'Unknown error')}")
            
            retry_after = response.headers.get("Retry-After")
            delay = int(retry_after) if retry_after else base_delay * (2 ** attempt) + 0.5
            logger.info(f"Retry {attempt + 1} after {delay}s...")
            time.sleep(delay)
    
    def get_user_tweets(self, username: str, limit: int = 20) -> List[Tweet]:
        """Get recent tweets from a user"""
        try:
            data = self._request("GET", f"/lookup/tweets?usernames={username}&maxResults={limit}")
            tweets = []
            
            for t in data.get("tweets", []):
                tweets.append(Tweet(
                    id=t.get("id", ""),
                    username=t.get("author", {}).get("username", username),
                    text=t.get("text", ""),
                    created_at=t.get("createdAt", ""),
                    likes=t.get("likeCount", 0),
                    retweets=t.get("retweetCount", 0),
                    replies=t.get("replyCount", 0),
                    views=t.get("viewCount", 0),
                    url=f"https://x.com/{t.get('author', {}).get('username', username)}/status/{t.get('id', '')}"
                ))
            return tweets
        except Exception as e:
            logger.error(f"Error fetching @{username}: {e}")
            return []
    
    def get_account_info(self) -> dict:
        """Get account status and credits"""
        return self._request("GET", "/account")
    
    def get_balance(self) -> dict:
        """Get credit balance"""
        return self._request("GET", "/credits")

class DeepSeekFilter:
    """AI filtering using DeepSeek"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base = DEEPSEEK_BASE
    
    def filter_tweets(self, tweets: List[Dict]) -> List[Dict]:
        """Filter and score tweets using AI"""
        if not tweets:
            return []
        
        # Format tweets for the prompt
        tweet_list = "\n".join([
            f"[{i+1}] @{t['username']}: {t['text'][:200]}... (likes:{t['likes']}, RTs:{t['retweets']})"
            for i, t in enumerate(tweets[:30])  # Process max 30 at once
        ])
        
        prompt = f"""You are a crypto content curator analyzing tweets for a shortform video creator.

Analyze these crypto/tech tweets and filter for news-worthy content. Score each 1-10 based on:
- NEWS VALUE: Is this actual news, not just commentary?
- SHORTFORM APPEAL: Would viewers care about this in 30-60 seconds?
- UNIQUENESS: Is this unique info or covered everywhere?
- IMPACT: Does it mention specific events, numbers, launches, hacks?

Return JSON array with: index, score (1-10), category (hack|launch|price|macro|alpha|defi| meme|tech|other), one_line_summary

Tweets to analyze:
{tweet_list}

Return ONLY valid JSON array, no markdown, no explanation."""

        try:
            response = requests.post(
                f"{self.base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3
                },
                timeout=60
            )
            
            if response.ok:
                content = response.json()["choices"][0]["message"]["content"]
                # Parse JSON response
                import re
                json_match = re.search(r'\[.*\]', content, re.DOTALL)
                if json_match:
                    results = json.loads(json_match.group())
                    # Map back to tweets
                    for r in results:
                        if r['score'] >= 7:
                            tweets[r['index'] - 1]['ai_score'] = r['score']
                            tweets[r['index'] - 1]['ai_category'] = r['category']
                            tweets[r['index'] - 1]['ai_summary'] = r['one_line_summary']
                    return [t for t in tweets if t.get('ai_score', 0) >= 7]
            
        except Exception as e:
            logger.error(f"DeepSeek error: {e}")
        
        return []
    
    def generate_digest(self, filtered_tweets: List[Dict]) -> str:
        """Generate a daily digest summary"""
        if not filtered_tweets:
            return "No significant news today."
        
        tweets_text = "\n".join([
            f"- {t.get('ai_category', 'news').upper()}: {t.get('ai_summary', t['text'][:100])} (via @{t['username']})"
            for t in filtered_tweets[:20]
        ])
        
        prompt = f"""Create a concise daily crypto briefing for a shortform content creator.

Group these into categories and write 2-3 sentence summaries for each major story.

Tweets:
{tweets_text}

Format as:
## 🔥 BIG NEWS
[summary of most impactful]

## 💎 DEFI & PROTOCOLS
[defi-related updates]

## 🎯 ALPHA & TRADES
[trading signals, memecoins, launches]

## ⚠️ SCAMS & ALERTS
[hacks, rug pulls, warnings]

Keep it conversational and punchy for a TikTok/shortform video intro."""

        try:
            response = requests.post(
                f"{self.base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7
                },
                timeout=90
            )
            
            if response.ok:
                return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"DeepSeek digest error: {e}")
        
        return "Error generating digest"

class CryptoTwitterPipeline:
    """Main pipeline orchestrator"""
    
    def __init__(self):
        self.db = Database()
        self.xquik = XquikClient(XQUIK_API_KEY)
        self.ai_filter = DeepSeekFilter(DEEPSEEK_API_KEY)
    
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
    
    def fetch_accounts(self, accounts_file: str = "accounts.txt", tweets_per_account: int = 20) -> int:
        """Fetch tweets from all accounts"""
        accounts = self.load_accounts(accounts_file)
        total_tweets = 0
        
        logger.info(f"Fetching tweets from {len(accounts)} accounts...")
        
        for i, account in enumerate(accounts):
            username = account['username']
            tier = account.get('tier', '')
            tags = account.get('tags', '')
            
            tweets = self.xquik.get_user_tweets(username, tweets_per_account)
            
            for tweet in tweets:
                self.db.add_tweet(tweet)
                total_tweets += 1
            
            self.db.add_account(username, tier, tags)
            
            # Progress every 10 accounts
            if (i + 1) % 10 == 0:
                logger.info(f"Progress: {i + 1}/{len(accounts)} accounts, {total_tweets} tweets")
            
            # Rate limit to avoid hitting limits
            time.sleep(0.5)
        
        logger.info(f"Total: {total_tweets} tweets from {len(accounts)} accounts")
        return total_tweets
    
    def process_tweets(self, batch_size: int = 30) -> int:
        """Run AI filtering on unprocessed tweets"""
        filtered_count = 0
        
        while True:
            tweets = self.db.get_unprocessed_tweets(hours=6, limit=batch_size)
            if not tweets:
                break
            
            results = self.ai_filter.filter_tweets(tweets)
            
            for tweet in results:
                self.db.update_tweet_ai(
                    tweet['id'],
                    tweet.get('ai_score', 0),
                    tweet.get('ai_category', 'other'),
                    tweet.get('ai_summary', '')
                )
                filtered_count += 1
            
            self.db.mark_processed([t['id'] for t in tweets])
            logger.info(f"Processed batch, filtered {len(results)} tweets")
            
            time.sleep(1)  # Rate limit between batches
        
        return filtered_count
    
    def generate_digest(self, hours: int = 24) -> str:
        """Generate daily digest from filtered tweets"""
        tweets = self.db.get_filtered_tweets(hours=hours, min_score=7.0)
        
        digest = self.ai_filter.generate_digest(tweets)
        
        # Save to database
        date_str = datetime.now().strftime("%Y-%m-%d")
        self.db.save_daily_digest(date_str, digest, tweets[:20], {})
        
        return digest
    
    def run_full_pipeline(self, accounts_file: str = "accounts.txt"):
        """Run the complete pipeline"""
        logger.info("=== Starting Crypto Twitter Pipeline ===")
        
        # Step 1: Fetch tweets
        logger.info("[1/3] Fetching tweets from accounts...")
        tweet_count = self.fetch_accounts(accounts_file)
        
        # Step 2: AI filtering
        logger.info("[2/3] Running AI filtering...")
        filtered = self.process_tweets()
        
        # Step 3: Generate digest
        logger.info("[3/3] Generating daily digest...")
        digest = self.generate_digest()
        
        logger.info("=== Pipeline Complete ===")
        logger.info(f"Fetched: {tweet_count} tweets, Filtered: {filtered} high-value")
        
        return digest


if __name__ == "__main__":
    pipeline = CryptoTwitterPipeline()
    digest = pipeline.run_full_pipeline()
    print("\n" + "="*50)
    print("DAILY DIGEST")
    print("="*50)
    print(digest)
"""
Crypto Intel Tools for Hermes Agent
These tools provide the agent with access to the crypto pipeline data.
"""

import json
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# Database path - update this to match your setup
DB_PATH = Path(__file__).parent.parent.parent.parent / "data" / "tweets.db"

def get_daily_digest(hours: int = 24, min_score: float = 7.0) -> Dict:
    """
    Get the latest AI-filtered crypto news digest.
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        cursor = conn.execute("""
            SELECT id, username, text, created_at, likes, retweets, views, 
                   ai_score, ai_category, summary
            FROM tweets 
            WHERE filtered = 1 AND ai_score >= ? AND fetched_at > ?
            ORDER BY ai_score DESC, created_at DESC
            LIMIT 50
        """, (min_score, since))
        
        results = [dict(zip([col[0] for col in cursor.description], row)) 
                   for row in cursor.fetchall()]
        conn.close()
        
        if not results:
            return {
                "status": "empty",
                "message": "No filtered tweets found. Run the pipeline first."
            }
        
        # Group by category
        categories = {}
        for tweet in results:
            cat = tweet.get('ai_category', 'news')
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(tweet)
        
        # Format response
        return {
            "status": "success",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "total_tweets": len(results),
            "categories": {
                cat: [
                    {
                        "username": t['username'],
                        "summary": t.get('summary', t['text'][:100]),
                        "score": t['ai_score'],
                        "engagement": f"{t['likes']} likes, {t['retweets']} RTs",
                        "url": f"https://x.com/{t['username']}/status/{t['id']}"
                    }
                    for t in tweets[:5]  # Top 5 per category
                ]
                for cat, tweets in categories.items()
            }
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}


def search_news(category: str = None, hours: int = 24) -> Dict:
    """
    Search filtered tweets by category/topic.
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        if category:
            cursor = conn.execute("""
                SELECT id, username, text, created_at, likes, retweets,
                       ai_score, ai_category, summary
                FROM tweets 
                WHERE filtered = 1 AND ai_category = ? AND fetched_at > ?
                ORDER BY ai_score DESC
                LIMIT 20
            """, (category, since))
        else:
            cursor = conn.execute("""
                SELECT id, username, text, created_at, likes, retweets,
                       ai_score, ai_category, summary
                FROM tweets 
                WHERE filtered = 1 AND fetched_at > ?
                ORDER BY ai_score DESC
                LIMIT 20
            """, (since,))
        
        results = [dict(zip([col[0] for col in cursor.description], row)) 
                   for row in cursor.fetchall()]
        conn.close()
        
        formatted = [
            {
                "category": t.get('ai_category', 'news'),
                "username": t['username'],
                "text": t['text'][:200],
                "score": t['ai_score'],
                "summary": t.get('summary', ''),
                "url": f"https://x.com/{t['username']}/status/{t['id']}"
            }
            for t in results
        ]
        
        return {
            "status": "success",
            "category": category or "all",
            "count": len(formatted),
            "results": formatted
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_trending(platform: str = "all") -> Dict:
    """
    Get trending crypto topics and alerts.
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        since = (datetime.now() - timedelta(hours=6)).isoformat()
        
        # Get top tweets by engagement
        cursor = conn.execute("""
            SELECT username, text, likes, retweets, views, ai_score, ai_category
            FROM tweets 
            WHERE filtered = 1 AND fetched_at > ?
            ORDER BY (likes + retweets * 2 + views * 0.1) DESC
            LIMIT 20
        """, (since,))
        
        results = [dict(zip([col[0] for col in cursor.description], row)) 
                   for row in cursor.fetchall()]
        conn.close()
        
        # Analyze for trends
        trends = {
            "whale_alerts": [],
            "hacks": [],
            "launches": [],
            " memecoins": []
        }
        
        for tweet in results:
            text_lower = tweet['text'].lower()
            if 'whale' in text_lower or 'transfer' in text_lower:
                trends["whale_alerts"].append(tweet)
            elif 'hack' in text_lower or 'rug' in text_lower or 'scam' in text_lower:
                trends["hacks"].append(tweet)
            elif 'launch' in text_lower or 'new' in text_lower:
                trends["launches"].append(tweet)
            elif any(m in text_lower for m in ['sol', 'meme', 'pepe', 'dog']):
                trends["memecoins"].append(tweet)
        
        return {
            "status": "success",
            "platform": platform,
            "trending": trends
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_content_ideas(count: int = 5, style: str = "informative") -> Dict:
    """
    Generate shortform video topics from today's news.
    """
    try:
        conn = sqlite3.connect(str(DB_PATH))
        since = (datetime.now() - timedelta(hours=24)).isoformat()
        
        cursor = conn.execute("""
            SELECT username, text, ai_score, ai_category, summary, likes, views
            FROM tweets 
            WHERE filtered = 1 AND ai_score >= 8.0 AND fetched_at > ?
            ORDER BY ai_score DESC
            LIMIT 10
        """, (since,))
        
        results = [dict(zip([col[0] for col in cursor.description], row)) 
                   for row in cursor.fetchall()]
        conn.close()
        
        ideas = []
        for i, tweet in enumerate(results[:count]):
            category = tweet.get('ai_category', 'news')
            
            if style == "alert":
                ideas.append({
                    "hook": f"🚨 {category.upper()} ALERT: {tweet.get('summary', tweet['text'][:50])}",
                    "angle": f"Breaking down what happened and why it matters",
                    "key_facts": [tweet['text'][:150], f"Source: @{tweet['username']}"],
                    "duration": "20-30 seconds"
                })
            elif style == "alpha":
                ideas.append({
                    "hook": f"📈 Alpha Drop: {tweet.get('summary', tweet['text'][:50])}",
                    "angle": "Sharing the trade setup before it pumps",
                    "key_facts": [f"@{tweet['username']} flagged this", f"{tweet['likes']} engagements"],
                    "duration": "30-45 seconds"
                })
            else:  # informative
                ideas.append({
                    "hook": f"☕ Crypto Briefing: {category.upper()}",
                    "angle": tweet.get('summary', tweet['text'][:80]),
                    "key_facts": [
                        f"via @{tweet['username']}",
                        f"{tweet['likes']} likes, {int(tweet['views'] or 0)} views"
                    ],
                    "duration": "45-60 seconds"
                })
        
        return {
            "status": "success",
            "style": style,
            "ideas": ideas
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    # Test the tools
    print("Testing get_daily_digest:")
    result = get_daily_digest()
    print(json.dumps(result, indent=2)[:500])
    
    print("\nTesting search_news:")
    result = search_news(category="hack")
    print(json.dumps(result, indent=2)[:500])
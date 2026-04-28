"""
Crypto Tweet Scorer - Simple formula-based scoring for MVP
Uses engagement metrics + keyword detection for content potential
"""

import sqlite3
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict

DB_PATH = Path(__file__).parent.parent / 'data' / 'tweets.db'

def get_db():
    return sqlite3.connect(str(DB_PATH))

# Keywords that indicate high video potential
CATEGORY_KEYWORDS = {
    'hack': ['hack', 'rug', 'scam', 'exploit', 'stolen', 'attacked', 'phishing', 'fake'],
    'whale': ['whale', '$50', '$100', '$1', 'million', 'billion', 'transfer', 'movement', 'accumulation', 'wallet'],
    'bitcoin': ['bitcoin', 'btc', 'etf', 'saylor', 'blackrock', 'institutional', 'sec', 'regulation'],
    'solana': ['solana', 'sol ', '$sol', 'jupiter', 'raydium', 'pump', 'birdeye'],
    'defi': ['defi', 'lending', 'yield', 'lp', 'liquidity', 'amm', 'dex', 'uniswap', 'aave'],
    'memecoin': ['meme', 'pepe', 'dog', 'shiba', 'woof', 'memecoin', 'ben', 'mooner'],
    'alpha': ['call', 'signal', 'alpha', 'buy', 'long', 'short', 'trade', 'position', 'flip'],
}

def score_tweet(text: str, likes: int, retweets: int, views: int) -> Dict:
    """Score a tweet for content potential"""
    
    text_lower = text.lower()
    score = 5.0  # Base score
    category = 'other'
    hook = ''
    
    # Engagement boost
    engagement = likes + (retweets * 2) + (views * 0.01)
    if engagement > 1000:
        score += 1.5
    elif engagement > 500:
        score += 1.0
    elif engagement > 100:
        score += 0.5
    
    # Keyword boosts
    for cat, keywords in CATEGORY_KEYWORDS.items():
        matches = sum(1 for kw in keywords if kw in text_lower)
        if matches >= 2:
            score += 1.5
            category = cat
            hook = f"{cat} signal"
            break
        elif matches == 1:
            score += 0.5
    
    # Time sensitivity (newer = better for content)
    # Check for time indicators
    time_indicators = ['just', 'now', 'breaking', 'new', 'announcement', 'update']
    if any(ind in text_lower for ind in time_indicators):
        score += 0.5
    
    # Specific high-value content patterns
    if any(x in text_lower for x in ['$', '000', '000,000']):
        score += 0.5  # Has dollar amounts = more specific = better
    
    # RT indicator
    if text.startswith('RT '):
        score -= 0.5  # RTs are less original
    
    # Cap score at 10
    score = min(10.0, max(1.0, score))
    
    return {
        'score': round(score, 1),
        'category': category,
        'hook': hook or generate_hook(text, category)
    }

def generate_hook(text: str, category: str) -> str:
    """Generate a simple hook based on content"""
    text_lower = text.lower()
    
    if 'hack' in text_lower or 'rug' in text_lower:
        return 'Security alert'
    elif 'whale' in text_lower:
        return 'Whale movement'
    elif '$' in text:
        return 'Price signal'
    elif 'bitcoin' in text_lower or 'btc' in text_lower:
        return 'Bitcoin update'
    elif 'solana' in text_lower:
        return 'Solana alpha'
    elif any(x in text_lower for x in ['launch', 'new', 'release']):
        return 'New launch'
    else:
        return f'{category} update'

def score_all_tweets():
    """Score all unprocessed tweets"""
    conn = get_db()
    
    cursor = conn.execute("""
        SELECT id, text, likes, retweets, views
        FROM tweets 
        WHERE ai_score IS NULL OR ai_score = 0
        ORDER BY fetched_at DESC
        LIMIT 100
    """)
    
    tweets = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
    conn.close()
    
    if not tweets:
        print("No tweets to score")
        return
    
    print(f"Scoring {len(tweets)} tweets...")
    
    scored = 0
    for tweet in tweets:
        result = score_tweet(
            tweet['text'],
            tweet['likes'] or 0,
            tweet['retweets'] or 0,
            tweet['views'] or 0
        )
        
        conn = get_db()
        conn.execute("""
            UPDATE tweets 
            SET ai_score = ?, ai_category = ?, ai_hook = ?
            WHERE id = ?
        """, (result['score'], result['category'], result['hook'], tweet['id']))
        conn.commit()
        conn.close()
        
        scored += 1
    
    print(f"✅ Scored {scored} tweets")

def show_top(n: int = 10):
    """Show top content opportunities"""
    conn = get_db()
    cursor = conn.execute("""
        SELECT * FROM tweets 
        WHERE ai_score > 0
        ORDER BY ai_score DESC
        LIMIT ?
    """, (n,))
    
    tweets = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
    conn.close()
    
    if not tweets:
        print("No scored tweets yet")
        return
    
    print("\n" + "="*60)
    print("🎬 TOP CONTENT OPPORTUNITIES")
    print("="*60)
    
    for i, tweet in enumerate(tweets, 1):
        score = tweet.get('ai_score', 0)
        category = tweet.get('ai_category', 'other')
        hook = tweet.get('ai_hook', '')
        
        print(f"\n{i}. [{score:.1f}/10] [{category.upper()}]")
        print(f"   📝 {tweet['text'][:100]}...")
        print(f"   🎯 {hook}")
        print(f"   🔗 https://x.com/{tweet['username']}/status/{tweet['id']}")

def run():
    """Run the scorer"""
    print("="*60)
    print("📊 CRYPTO TWEET SCORER")
    print("="*60)
    
    print("\n[1] Scoring tweets...")
    score_all_tweets()
    
    print("\n[2] Top content:")
    show_top(10)
    
    print("\n✅ Done!")

if __name__ == "__main__":
    run()
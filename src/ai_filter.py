"""
MiniMax AI Filter for Crypto Pipeline
Scores tweets for content potential and generates content ideas
"""

import requests
import json
import os
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict
from pathlib import Path
import re

# Load env
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

MINIMAX_API_KEY = os.getenv('MINIMAX_API_KEY', '')
MINIMAX_MODEL = os.getenv('MINIMAX_MODEL', 'MiniMax-M2.7')
MINIMAX_BASE = 'https://api.minimax.io/v1/chat/completions'

DB_PATH = Path(__file__).parent.parent / 'data' / 'tweets.db'

def get_db():
    return sqlite3.connect(str(DB_PATH))

def call_minimax(prompt: str, max_tokens: int = 500) -> str:
    """Call MiniMax API with prompt - uses system prompt to get clean JSON"""
    try:
        resp = requests.post(
            MINIMAX_BASE,
            headers={
                'Authorization': f'Bearer {MINIMAX_API_KEY}',
                'Content-Type': 'application/json'
            },
            json={
                'model': MINIMAX_MODEL,
                'messages': [
                    {'role': 'system', 'content': 'You are a helpful assistant. Always respond with ONLY valid JSON, no explanations, no thinking tags, no markdown formatting. Return only the JSON object.'},
                    {'role': 'user', 'content': prompt}
                ],
                'max_tokens': max_tokens,
                'temperature': 0.3
            },
            timeout=60
        )
        
        if resp.ok:
            return resp.json()['choices'][0]['message']['content']
        else:
            return f"Error: {resp.status_code}"
    except Exception as e:
        return f"Exception: {str(e)}"

def extract_json_from_response(content: str) -> list:
    """Extract JSON array from MiniMax response"""
    if not content:
        return []
    
    # Find start of JSON array
    start_idx = content.find('[{"index"')
    if start_idx == -1:
        start_idx = content.find('[{"index')
    
    if start_idx == -1:
        return []
    
    # Extract until balanced ]
    depth = 0
    end_idx = start_idx
    for i in range(start_idx, len(content)):
        c = content[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                end_idx = i + 1
                break
    
    json_str = content[start_idx:end_idx]
    
    try:
        return json.loads(json_str)
    except Exception as e:
        print(f"JSON parse error: {e}")
        return []

def score_tweets_batch(tweets: List[Dict]) -> List[Dict]:
    """Score a batch of tweets for content potential"""
    
    if not tweets:
        return []
    
    tweet_lines = []
    for i, t in enumerate(tweets[:20]):
        tweet_lines.append(f"[{i+1}] @{t['username']}: {t['text'][:150]}... (likes:{t['likes']}, RTs:{t['retweets']})")
    
    tweet_list = "\n".join(tweet_lines)
    
    prompt = (
        'Score these crypto tweets for "video potential" (1-10).\n'
        'Return ONLY this exact JSON format (no thinking, no explanation): '
        '[{"index":1,"score":8.5,"category":"whale","hook":"whale alert"},...]\n\n'
        f'Tweets:\n{tweet_list}'
    )
    
    result = call_minimax(prompt, max_tokens=800)
    
    try:
        scores = extract_json_from_response(result)
        
        for score_data in scores:
            idx = score_data.get('index', 0) - 1
            if idx < len(tweets):
                tweets[idx]['ai_score'] = score_data.get('score', 5)
                tweets[idx]['ai_category'] = score_data.get('category', 'other')
                tweets[idx]['ai_hook'] = score_data.get('hook', '')
        
        return tweets
    except Exception as e:
        print(f"Parse error: {e}")
    
    for tweet in tweets:
        tweet['ai_score'] = 5
        tweet['ai_category'] = 'other'
        tweet['ai_hook'] = ''
    
    return tweets

def generate_content_ideas(tweets: List[Dict], top_n: int = 5) -> List[Dict]:
    """Generate content ideas from top tweets"""
    
    top_tweets = sorted(tweets, key=lambda x: x.get('ai_score', 0), reverse=True)[:top_n]
    
    if not top_tweets:
        return []
    
    tweet_lines = []
    for i, t in enumerate(top_tweets):
        tweet_lines.append(f"{i+1}. @{t['username']}: {t['text'][:100]}...")
    
    tweet_text = "\n".join(tweet_lines)
    
    prompt = (
        'You are a content strategist for crypto shortform videos (30-60s).\n'
        'For each story provide: 3-5 word HOOK, one-sentence CONTEXT, presentation ANGLE.\n'
        'Return ONLY this exact JSON format: '
        '[{"hook":"...", "context":"...", "angle":"..."},...]\n\n'
        f'Stories:\n{tweet_text}'
    )
    
    result = call_minimax(prompt, max_tokens=1000)
    
    ideas = []
    try:
        ideas = extract_json_from_response(result)
    except:
        pass
    
    for i, idea in enumerate(ideas):
        if i < len(top_tweets):
            top_tweets[i]['content_idea'] = idea
    
    return top_tweets

def generate_daily_brief(tweets: List[Dict]) -> str:
    """Generate a daily crypto brief"""
    
    categories = {}
    for tweet in tweets:
        cat = tweet.get('ai_category', 'other')
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(tweet)
    
    category_summary = []
    for cat, cat_tweets in categories.items():
        top = sorted(cat_tweets, key=lambda x: x.get('ai_score', 0), reverse=True)[:3]
        if top:
            category_summary.append({'category': cat, 'top_tweets': top})
    
    cat_text = []
    for c in category_summary:
        cat_text.append(f"**{c['category'].upper()}**")
        for t in c['top_tweets'][:2]:
            cat_text.append(f"- {t['text'][:80]}...")
    
    cat_str = "\n".join(cat_text)
    date_str = datetime.now().strftime('%b %d')
    
    prompt = (
        f'Create a punchy daily crypto briefing for 30-60s videos.\n\n'
        f'Format:\n'
        f'📊 **DAILY BRIEF - {date_str}\n\n'
        f'🔥 **BIGGEST**\n[1-2 sentence summary]\n\n'
        f'💎 **DEFI/ALTCOINS**\n[1-2 sentences]\n\n'
        f'⚠️ **ALERTS**\n[1-2 sentences]\n\n'
        f'🎯 **ALPHA**\n[1-2 sentences]\n\n'
        f'---\nCategories:\n{cat_str}'
    )
    
    return call_minimax(prompt, max_tokens=600)

def process_all_tweets():
    """Process all unprocessed tweets with AI"""
    conn = get_db()
    cursor = conn.execute("""
        SELECT id, username, text, likes, retweets, views, url
        FROM tweets 
        WHERE ai_score IS NULL OR ai_score = 0
        ORDER BY fetched_at DESC
        LIMIT 100
    """)
    
    tweets = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
    conn.close()
    
    if not tweets:
        print("No tweets to process")
        return
    
    print(f"Processing {len(tweets)} tweets with MiniMax...")
    
    batch_size = 20
    total = len(tweets)
    
    for i in range(0, total, batch_size):
        batch = tweets[i:i+batch_size]
        scored = score_tweets_batch(batch)
        
        conn = get_db()
        for tweet in scored:
            conn.execute("""
                UPDATE tweets 
                SET ai_score = ?, ai_category = ?, ai_hook = ?
                WHERE id = ?
            """, (
                tweet.get('ai_score', 0),
                tweet.get('ai_category', 'other'),
                tweet.get('ai_hook', ''),
                tweet['id']
            ))
        conn.commit()
        conn.close()
        
        print(f"  Processed batch {i//batch_size + 1}/{(total-1)//batch_size + 1}")
    
    print(f"✅ Processed {total} tweets")

def show_top_content():
    """Show top content opportunities"""
    conn = get_db()
    cursor = conn.execute("""
        SELECT * FROM tweets 
        WHERE ai_score > 0
        ORDER BY ai_score DESC
        LIMIT 20
    """)
    
    tweets = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
    conn.close()
    
    if not tweets:
        print("No scored tweets yet.")
        return
    
    print("\n" + "="*60)
    print("🎬 TOP CONTENT OPPORTUNITIES")
    print("="*60)
    
    for i, tweet in enumerate(tweets[:10], 1):
        score = tweet.get('ai_score', 0)
        category = tweet.get('ai_category', 'other')
        hook = tweet.get('ai_hook', 'No hook')
        
        print(f"\n{i}. [{score:.1f}/10] [{category.upper()}]")
        print(f"   📝 {tweet['text'][:100]}...")
        print(f"   🎯 {hook}")
        print(f"   🔗 https://x.com/{tweet['username']}/status/{tweet['id']}")

def run_full_pipeline():
    """Run the complete AI pipeline"""
    print("="*60)
    print("🤖 CRYPTO AI PIPELINE - MiniMax Edition")
    print("="*60)
    
    print("\n[1] Scoring tweets with MiniMax...")
    process_all_tweets()
    
    print("\n[2] Top content opportunities:")
    show_top_content()
    
    print("\n[3] Generating daily brief...")
    conn = get_db()
    cursor = conn.execute("SELECT * FROM tweets WHERE ai_score > 5 ORDER BY ai_score DESC LIMIT 30")
    tweets = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
    conn.close()
    
    if tweets:
        brief = generate_daily_brief(tweets)
        print("\n" + brief)
    
    print("\n✅ Pipeline complete!")

if __name__ == "__main__":
    run_full_pipeline()
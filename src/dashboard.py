"""
Crypto Intel Dashboard - Web Frontend
"""

from flask import Flask, render_template, jsonify, request
import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta

app = Flask(__name__)

DB_PATH = Path(__file__).parent.parent / 'data' / 'tweets.db'

def get_db():
    return sqlite3.connect(str(DB_PATH))

def dict_from_row(cursor, row):
    return dict(zip([col[0] for col in cursor.description], row))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/stats')
def stats():
    conn = get_db()
    cursor = conn.execute("SELECT COUNT(*) FROM tweets")
    total_tweets = cursor.fetchone()[0]
    cursor = conn.execute("SELECT COUNT(*) FROM accounts")
    total_accounts = cursor.fetchone()[0]
    cursor = conn.execute("SELECT COUNT(*) FROM tweets WHERE fetched_at > ?", 
                          ((datetime.now() - timedelta(hours=24)).isoformat(),))
    tweets_24h = cursor.fetchone()[0]
    conn.close()
    return jsonify({
        'total_tweets': total_tweets,
        'total_accounts': total_accounts,
        'tweets_24h': tweets_24h
    })

@app.route('/api/content-pack')
def content_pack():
    """Get top content with hooks and scripts ready to record"""
    conn = get_db()
    
    # Get top scored tweets
    cursor = conn.execute("""
        SELECT * FROM tweets 
        WHERE ai_score >= 6.5
        ORDER BY ai_score DESC
        LIMIT 10
    """)
    
    tweets = [dict_from_row(cursor, row) for row in cursor.fetchall()]
    conn.close()
    
    # Generate content for each
    content_items = []
    for i, tweet in enumerate(tweets, 1):
        text = tweet['text']
        category = tweet.get('ai_category', 'other')
        username = tweet['username']
        
        # Generate hook based on category
        hook = generate_hook(category, text)
        context = generate_context(text, username)
        cta = generate_cta(category)
        
        # Clean tweet text (remove RT prefix, truncate)
        clean_text = text
        if clean_text.startswith('RT '):
            clean_text = clean_text.split(': ', 1)[-1] if ': ' in clean_text else clean_text[3:]
        if len(clean_text) > 300:
            clean_text = clean_text[:300] + '...'
        
        content_items.append({
            'rank': i,
            'score': tweet.get('ai_score', 0),
            'category': category.upper(),
            'username': username,
            'tweet_id': tweet['id'],
            'url': f"https://x.com/{username}/status/{tweet['id']}",
            'text': clean_text,
            'hook': hook,
            'context': context,
            'cta': cta
        })
    
    return jsonify({
        'status': 'success',
        'generated_at': datetime.now().strftime('%Y-%m-%d %I:%M %p'),
        'count': len(content_items),
        'content': content_items
    })

def generate_hook(category, text):
    """Generate hook based on category and content"""
    text_lower = text.lower()
    
    if category == 'hack':
        return "🚨 Here's a scam you need to watch out for..."
    elif category == 'whale':
        if any(x in text for x in ['$50', '$100', '$1', 'million']):
            return "⚠️ Whales just moved millions. Here's what it means..."
        return "🐋 Big money is making a move..."
    elif category == 'bitcoin':
        if 'etf' in text_lower:
            return "📈 ETF just broke a record. This is huge for Bitcoin..."
        return "₿ Bitcoin is making headlines again..."
    elif category == 'solana':
        return "◎ Something big is happening on Solana..."
    elif category == 'defi':
        return "💎 DeFi update you need to know about..."
    elif category == 'alpha':
        return "🎯 Alpha drop - pay attention to this..."
    elif category == 'memecoin':
        return "🤑 Something weird is happening with memecoins..."
    else:
        return "📊 This crypto story is flying under the radar..."

def generate_context(text, username):
    """Generate context from tweet"""
    text_lower = text.lower()
    
    # Detect amounts
    import re
    amounts = re.findall(r'\$[\d,]+[KMB]?', text)[:2]
    
    if amounts:
        return f"@{username} reporting: {' '.join(amounts)} involved"
    
    # Detect percentages
    pct = re.findall(r'[\d.]+%', text)
    if pct:
        return f"@{username}: {pct[0]} move detected"
    
    # Check for new/launch/announcement
    if any(x in text_lower for x in ['new', 'launch', 'announcement', 'just']):
        return f"@{username} with breaking news"
    
    return f"@{username} reporting something important"

def generate_cta(category):
    """Generate CTA based on category"""
    ctas = {
        'hack': "Follow for more scam alerts 🔔",
        'whale': "Follow to track whale moves 🐋",
        'bitcoin': "Follow for Bitcoin updates ₿",
        'solana': "Follow for Solana alpha ◎",
        'defi': "Follow for DeFi updates 💎",
        'alpha': "Follow for real alpha 🎯",
        'memecoin': "Follow for memecoin action 🤑",
        'other': "Follow for daily updates 📊"
    }
    return ctas.get(category, ctas['other'])

@app.route('/api/digest')
def digest():
    hours = request.args.get('hours', 24, type=int)
    min_score = request.args.get('min_score', 0, type=float)
    
    conn = get_db()
    since = (datetime.now() - timedelta(hours=hours)).isoformat()
    
    cursor = conn.execute("""
        SELECT * FROM tweets 
        WHERE fetched_at > ?
        ORDER BY fetched_at DESC
        LIMIT 100
    """, (since,))
    
    tweets = [dict_from_row(cursor, row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify({
        'status': 'success',
        'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'total': len(tweets),
        'tweets': tweets[:50]
    })

@app.route('/api/category/<category>')
def category(category):
    conn = get_db()
    since = (datetime.now() - timedelta(hours=24)).isoformat()
    
    keywords = {
        'whale': ['whale', 'transfer', '$50', '$100', 'million'],
        'hack': ['hack', 'rug', 'scam', 'exploit'],
        'defi': ['defi', 'lending', 'dex', 'yield'],
        'solana': ['solana', 'sol ', '$sol'],
        'bitcoin': ['bitcoin', 'btc', 'etf'],
        'alpha': ['alpha', 'signal', 'call', 'buy']
    }
    
    kw = keywords.get(category, [])
    if not kw:
        return jsonify({'error': 'Unknown category'})
    
    cursor = conn.execute("""
        SELECT * FROM tweets 
        WHERE fetched_at > ? AND (
            text LIKE ? OR text LIKE ? OR text LIKE ? OR 
            text LIKE ? OR text LIKE ?
        )
        ORDER BY fetched_at DESC
        LIMIT 50
    """, (since, *[f'%{w}%' for w in kw]))
    
    tweets = [dict_from_row(cursor, row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify({'category': category, 'count': len(tweets), 'tweets': tweets})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
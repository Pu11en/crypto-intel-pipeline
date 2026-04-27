"""
Content Generator - Turns scored tweets into video scripts
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent.parent / 'data' / 'tweets.db'

def get_db():
    return sqlite3.connect(str(DB_PATH))

def get_top_content(min_score: float = 7.0, limit: int = 10):
    """Get top scored tweets for content"""
    conn = get_db()
    cursor = conn.execute("""
        SELECT * FROM tweets 
        WHERE ai_score >= ?
        ORDER BY ai_score DESC
        LIMIT ?
    """, (min_score, limit))
    
    tweets = [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]
    conn.close()
    return tweets

def generate_content_pack(tweets):
    """Generate content pack from tweets"""
    
    print("="*70)
    print("🎬 CONTENT PACK - READY TO RECORD")
    print("="*70)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %I:%M %p')}")
    print("="*70)
    
    for i, tweet in enumerate(tweets, 1):
        score = tweet.get('ai_score', 0)
        category = tweet.get('ai_category', 'other').upper()
        username = tweet['username']
        text = tweet['text']
        url = f"https://x.com/{username}/status/{tweet['id']}"
        
        print(f"\n{'─'*70}")
        print(f"📹 VIDEO #{i} | SCORE: {score}/10 | CATEGORY: {category}")
        print(f"{'─'*70}")
        
        # Hook line
        hook = generate_hook(category, text)
        print(f"\n🎤 HOOK (say this first):")
        print(f"   \"{hook}\"")
        
        # Context
        print(f"\n📝 CONTEXT (what to say):")
        context = generate_context(category, text, username)
        print(f"   {context}")
        
        # Key points
        print(f"\n🔑 KEY POINTS:")
        points = extract_key_points(text, category)
        for p in points:
            print(f"   • {p}")
        
        # CTA
        print(f"\n📣 ENDING CTA:")
        cta = generate_cta(category)
        print(f"   \"{cta}\"")
        
        # Source
        print(f"\n🔗 SOURCE: @{username}")
        print(f"   {url}")
        
        print(f"\n{'='*70}")

def generate_hook(category, text):
    """Generate attention-grabbing hook"""
    
    text_lower = text.lower()
    
    if category == 'hack':
        return "Here's another scam you need to watch out for..."
    
    elif category == 'whale':
        # Check for specific amounts
        if '50' in text or '100' in text:
            return "Whales are moving millions right now. Here's what it means..."
        elif 'billion' in text_lower:
            return "Billion-dollar move just happened. This changes everything..."
        return "Big money is making a move. Let me explain..."
    
    elif category == 'bitcoin':
        if 'etf' in text_lower:
            return "ETF just broke a record. This is huge for Bitcoin..."
        return "Bitcoin is making headlines again. Here's the story..."
    
    elif category == 'solana':
        return "Something big is happening on Solana right now..."
    
    elif category == 'alpha':
        return "Alpha drop - pay attention to this..."
    
    elif category == 'defi':
        return "DeFi update you need to know about..."
    
    else:
        return "This crypto story is flying under the radar..."

def generate_context(category, text, username):
    """Generate the main context/narrative"""
    
    text_lower = text.lower()
    
    # Detect dollar amounts
    amounts = []
    import re
    dollar_matches = re.findall(r'\$[\d,]+[KMB]?', text)
    if dollar_matches:
        amounts = dollar_matches
    
    # Detect percentages
    pct_matches = re.findall(r'[\d.]+%', text)
    
    context_parts = []
    
    if amounts:
        context_parts.append(f"Someone just {'moved' if category == 'whale' else 'invested'} {', '.join(amounts[:2])}")
    else:
        context_parts.append(f"@{username} is reporting on something important")
    
    if pct_matches:
        context_parts.append(f"involving a {pct_matches[0]} move")
    
    if category == 'hack':
        context_parts.append("and it's a scam you should know about")
    elif category == 'whale':
        context_parts.append("which could signal a market move")
    
    return " ".join(context_parts) + "."

def extract_key_points(text, category):
    """Extract 3-4 key talking points from the tweet"""
    
    points = []
    text_lower = text.lower()
    
    # Remove RT prefix
    if text.startswith('RT '):
        text = text.split(': ', 1)[-1] if ': ' in text else text[3:]
    
    # Truncate for readability
    if len(text) > 200:
        display_text = text[:200] + "..."
    else:
        display_text = text
    
    points.append(f"\"{display_text}\"")
    
    # Add category-specific points
    if category == 'hack':
        points.append("Check if you're affected")
        points.append("Don't trust unknown tokens")
    
    elif category == 'whale':
        points.append("Whale moves often signal market direction")
        points.append("Watch for follow-up actions")
    
    elif category == 'bitcoin':
        points.append("Institutional adoption continues")
        points.append("ETF flows matter")
    
    return points[:4]

def generate_cta(category):
    """Generate call-to-action ending"""
    
    ctas = {
        'hack': "Follow me for more scam alerts so you don't get rekt.",
        'whale': "Follow me - I track whale moves so you can stay ahead.",
        'bitcoin': "Drop a 🔥 if you think Bitcoin is going to $100k",
        'solana': "Follow for more Solana alpha drops",
        'defi': "Follow for DeFi updates and yield opportunities",
        'alpha': "Follow for real alpha before it pumps",
        'other': "Follow for daily crypto updates"
    }
    
    return ctas.get(category, ctas['other'])

def run():
    """Generate content pack from top tweets"""
    
    print("\n📊 Fetching top content...")
    
    tweets = get_top_content(min_score=6.5, limit=5)
    
    if not tweets:
        print("No scored tweets found. Run scorer first.")
        return
    
    print(f"Found {len(tweets)} top content opportunities\n")
    
    generate_content_pack(tweets)

if __name__ == "__main__":
    run()
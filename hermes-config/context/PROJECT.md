# Crypto Twitter Intelligence Pipeline - Project Context

## Overview

This project creates an automated system for content creators to stay on top of crypto news without doomscrolling Twitter all day.

**Goal**: Wake up to a clean daily digest of what's actually important in crypto, ready for content creation.

---

## Architecture

```
HERMES AGENT (Telegram) ←→ USER
         ↓
    Crypto Intel Skill
         ↓
    Pipeline Tools
         ↓
    ┌─────┴─────┐
    ↓           ↓
XQUIK API    DEEPSEEK
(Fetch)     (Filter)
    ↓           ↓
    └─────┬─────┘
          ↓
      DATABASE
      (SQLite)
```

---

## Components

### 1. Pipeline (`src/pipeline.py`)
- Fetches tweets from 80+ accounts via Xquik API
- Runs AI filtering via DeepSeek v3
- Scores tweets 1-10 based on news value
- Stores in SQLite database
- Runs on cron every 4 hours

### 2. Hermes Skill (`hermes-config/skills/crypto-intel/`)
- Custom skill giving Hermes access to crypto data
- Tools: get_daily_digest, search_news, get_trending, get_content_ideas
- Loaded into Hermes agent

### 3. Telegram Gateway
- User talks to Hermes via Telegram
- Hermes responds with filtered news
- Can trigger manual pipeline runs

---

## Data Flow

1. **4-hour cycle**: Pipeline fetches tweets → AI filters → DB stores
2. **User request**: Hermes queries DB → formats response → sends Telegram
3. **Daily digest**: Cron triggers Hermes → sends morning brief

---

## Account Categories

- **Critical** (must include): lookonchain, zachxbt, whale_alert, saylor, BitcoinETFFlow
- **High**: Solana ecosystem (SolanaScribe, Birdeye360, Jump), KOLs (rektcapital, jconorgauder)
- **Medium**: Trading signals, general news
- **Low**: Memecoins, entertainment

---

## AI Categories

| Category | Description | Accounts |
|----------|-------------|-----------|
| hack | Rug pulls, scams, security | zachxbt, MistTrack, CertiKAlert |
| launch | New protocols, tokens | Pumpdotfun, Birdeye360 |
| price | Market movements | CoinGlass, Alternative.me |
| macro | Big picture, ETFs, regulation | Saylor, APompliano |
| alpha | Trading opportunities | 0xMert_, SolanaScribe |
| defi | DeFi updates | DeFiLlama, Aave |
| memecoin | Meme activity | SolanaScribe, memecoin_mix |
| tech | Technical updates | Vitalik, HeliusLab |

---

## Key Files

```
crypto-twitter-pipeline/
├── accounts.txt           # Monitored Twitter accounts
├── src/
│   ├── pipeline.py        # Main pipeline runner
│   ├── xquik_client.py    # Xquik API wrapper
│   ├── ai_filter.py       # DeepSeek integration
│   └── database.py        # SQLite operations
├── hermes-config/
│   ├── SOUL.md            # Agent personality
│   ├── skills/
│   │   └── crypto-intel/  # Custom skill
│   └── context/
│       └── PROJECT.md     # This file
├── data/
│   └── tweets.db          # SQLite database
└── .env                   # API keys (not in git)
```

---

## Configuration

### Required Environment Variables
```
XQUIK_API_KEY=       # $20/month - Twitter data access
DEEPSEEK_API_KEY=    # AI filtering
TELEGRAM_BOT_TOKEN=  # Telegram bot for Hermes
```

### Cron Schedule
```
0 */4 * * *  # Every 4 hours
0 8 * * *    # Daily digest at 8 AM
```

---

## Pipeline Output Format

```json
{
  "status": "success",
  "date": "2026-04-27",
  "categories": {
    "hack": [
      {"username": "zachxbt", "score": 9.5, "summary": "..."}
    ],
    "launch": [...],
    "alpha": [...]
  }
}
```

---

## Hermes Tools

| Tool | Purpose |
|------|---------|
| get_daily_digest | Latest filtered news |
| search_news | Filter by category |
| get_trending | Hot topics right now |
| get_content_ideas | Video topics from news |
| run_pipeline | Trigger manual fetch |

---

## Usage with Hermes

1. Install Hermes: `curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash`
2. Copy skill: `cp -r crypto-twitter-pipeline/hermes-config/skills/crypto-intel ~/.hermes/skills/`
3. Configure .env with API keys
4. Set up Telegram: `hermes gateway setup`
5. Start: `hermes`

User then talks to bot on Telegram, gets daily briefings and can query news.
# Hermes Crypto Intelligence Agent - Architecture Plan

## The Vision
A Telegram-powered AI agent that serves as your **crypto news co-pilot**. 
Wake up → Daily digest in Telegram → Ask follow-up questions → Done in 5 min.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         TELEGRAM                                 │
│              (Your interface to everything)                      │
└─────────────────────┬─────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                   HERMES AGENT                                   │
│   • Personality: "Crypto News Analyst"                          │
│   • Memory: Remembers your preferences                          │
│   • Skills: crypto-intel, pipeline-commands, content-ideas      │
│   • Tools: Runs pipeline, queries DB, generates summaries       │
└─────────────────────┬─────────────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│   XQUIK      │ │  DEEPSEEK    │ │  POSTGRESQL   │
│  (Twitter)   │ │  (AI Brain)  │ │  (Data)       │
└──────────────┘ └──────────────┘ └──────────────┘
        │             │             │
        └─────────────┴─────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│              CRYPTO PIPELINE (Background)                        │
│   • Runs every 4-6 hours via cron                               │
│   • Fetches tweets via Xquik                                     │
│   • Filters via DeepSeek                                         │
│   • Stores in DB                                                 │
│   • Generates digest                                             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Components

### 1. Hermes Agent
- **Interface**: Telegram (talk from anywhere)
- **Personality**: Crypto analyst who knows what's hot
- **Memory**: Remembers you prefer Solana > Ethereum, hate memecoins, etc.
- **Skills**: Loaded from `./skills/crypto-intel/`

### 2. Crypto Pipeline (Python backend)
- **Xquik Integration**: Fetch tweets from 80+ accounts
- **AI Filtering**: DeepSeek v3 scores tweets 1-10
- **DB Storage**: SQLite/Postgres with processed data
- **Scheduler**: Cron every 4 hours

### 3. Hermes Skill (`crypto-intel`)
- **Tools**: Access pipeline, query digests, get top tweets
- **Commands**: `/digest`, `/trending`, `/hack`, `/alpha`
- **Memory**: Remembers preferences, past discussions

### 4. Cron Jobs (Scheduled Automation)
- **Daily (8 AM)**: "Morning briefing" delivered to Telegram
- **Every 4 hours**: Pipeline runs, updates DB
- **Weekly**: "This week's biggest stories" summary

---

## Hermes Configuration

### Files to Create:
```
crypto-twitter-pipeline/
├── hermes-config/
│   ├── .env                    # API keys
│   ├── SOUL.md                 # Personality
│   ├── skills/
│   │   └── crypto-intel/       # Custom skill
│   │       ├── SKILL.md
│   │       ├── metadata.json
│   │       └── tools/
│   │           ├── get_digest.py
│   │           ├── run_pipeline.py
│   │           └── query_tweets.py
│   └── context/
│       └── CONTEXT.md          # Project context
```

### Setup Steps:

```bash
# 1. Install Hermes
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash

# 2. Clone this repo
git clone https://your-repo/crypto-twitter-pipeline.git

# 3. Configure Telegram
hermes gateway setup  # Choose Telegram, enter bot token

# 4. Install crypto-intel skill
cp -r crypto-twitter-pipeline/hermes-config/skills/crypto-intel ~/.hermes/skills/

# 5. Configure API keys
cp crypto-twitter-pipeline/hermes-config/.env.example ~/.hermes/.env
# Edit with your XQUIK_API_KEY, DEEPSEEK_API_KEY, etc.

# 6. Set personality
cp crypto-twitter-pipeline/hermes-config/SOUL.md ~/.hermes/SOUL.md

# 7. Start!
hermes
```

---

## Skill Commands (Natural Language)

| You say | Hermes does |
|---------|-------------|
| "What's the daily digest?" | Shows latest AI-filtered news |
| "Any big hacks today?" | Searches for hack/rug alerts |
| "What's trending in Solana?" | Shows Solana-specific alpha |
| "Run the pipeline now" | Triggers manual fetch |
| "Give me content ideas" | Suggests video topics from today's news |
| "Compare to yesterday" | Shows what changed |
| "Show me whale activity" | Filters for smart money moves |

---

## Daily Workflow

```
Morning (8 AM) ──────────────────────────────────────────────────
│
├── Hermes sends to Telegram:
│   ├── "☕ Morning Brief - April 27, 2026"
│   ├── 🔥 BIG: "Michael Saylor just announced..."
│   ├── 💎 DEFI: "New protocol launch on Solana..."
│   ├── ⚠️ ALERTS: "Rug pull on pump.fun..."
│   └── 🎯 ALPHA: "Whales are buying SOL..."
│
├── You reply: "Give me more on the Saylor news"
│   └── Hermes expands, shows tweets, context
│
└── Done in 2 minutes, head to recording
```

---

## Cost Estimate (Monthly)

| Service | Cost |
|---------|------|
| Xquik Basic | $20/month |
| DeepSeek v3 | ~$5-10/month |
| Railway (hosting) | $5-10/month (if needed) |
| Telegram Bot | Free |
| **Total** | **~$30-40/month** |

---

## Content Format for Shortform

The pipeline generates output in this format:

```
🔥 BIG NEWS
Bitcoin ETF had record $2.1B inflows yesterday. BlackRock now 
holds 500k BTC. Michael Saylor said "we're still early."

💎 DEFI
Jupiter just launched perpetual trading. 10x leverage, 0 fees 
for first week. Everyone's calling it the "Uniswap killer."

⚠️ SCAM ALERT
@zachxbt found another rugged token. $500k liquidity removed 
by the dev. Avoid: "FreeMemeCoin"

🎯 MEMECOIN ALPHA
SolanaScribe flagged $PEPE clone doing 100x in 2 hours. 
Whale alert shows 100 SOL position.
```

---

## Next Steps

1. ✅ **Xquik found** - $20/month, works great
2. ⬜ **Create Hermes skill** - crypto-intel skill
3. ⬜ **Build pipeline** - fetch + filter + store
4. ⬜ **Configure Telegram** - setup gateway
5. ⬜ **Set cron jobs** - daily digests
6. ⬜ **Test everything** - full integration test

---

## Files to Create

1. `hermes-config/SOUL.md` - Agent personality
2. `hermes-config/skills/crypto-intel/SKILL.md` - Skill definition
3. `hermes-config/skills/crypto-intel/tools/get_digest.py` - Tool to fetch digest
4. `hermes-config/skills/crypto-intel/tools/run_pipeline.py` - Tool to trigger pipeline
5. `hermes-config/skills/crypto-intel/tools/query_tweets.py` - Query tweets
6. `hermes-config/context/CONTEXT.md` - Project context
7. `src/pipeline.py` - Already created ✅
8. `src/xquik_client.py` - Xquik wrapper
9. `src/ai_filter.py` - DeepSeek integration
10. `src/telegram_bot.py` - Optional standalone bot

---

Want me to continue building out these components?
# Crypto Intel Pipeline

Automated crypto news intelligence for content creators. Scrapes Twitter accounts, filters for news value, and generates content hooks for shortform videos.

## Features

- **Xquik Integration** - Scrapes 78+ crypto Twitter accounts via Xquik API
- **48-Hour Fresh Data** - Only shows tweets from the last 48 hours
- **AI Scoring** - Scores tweets 1-10 based on content/video potential
- **Content Generator** - Creates ready-to-record video scripts with hooks
- **Web Dashboard** - Visual interface for browsing content

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Configure API keys
cp .env.example .env
# Add your XQUIK_API_KEY and MINIMAX_API_KEY

# Run the pipeline
python src/xquik_client.py    # Fetch tweets
python src/scorer.py          # Score tweets
python src/content_generator.py  # Generate content pack

# Start dashboard
python src/dashboard.py
# Open http://localhost:5000
```

## Project Structure

```
crypto-twitter-pipeline/
├── accounts.txt          # Twitter accounts to scrape
├── requirements.txt      # Python dependencies
├── .env.example        # API key template
├── src/
│   ├── xquik_client.py    # Xquik API integration
│   ├── scorer.py          # Tweet scoring
│   ├── content_generator.py  # Content pack generator
│   └── dashboard.py       # Web dashboard (Flask)
├── data/               # SQLite database (gitignored)
└── hermes-config/     # Hermes agent config (optional)
```

## API Keys Required

1. **Xquik** - https://xquik.com (~$20/month or pay-per-use)
2. **MiniMax** - https://platform.minimax.io (for AI filtering)

## Dashboard

Run `python src/dashboard.py` and open http://localhost:5000 to see:
- Content Pack with hooks ready to record
- Category filters (Whale, Hack, Bitcoin, DeFi, Solana, Alpha)
- Tweet details and source links

## Commands

```bash
# Full pipeline
python src/xquik_client.py && python src/scorer.py

# Content only
python src/content_generator.py

# Dashboard
python src/dashboard.py
```

## Tech Stack

- Python 3.11+
- Flask (web dashboard)
- SQLite (data storage)
- Xquik API (Twitter data)
- MiniMax AI (scoring)

## License

MIT
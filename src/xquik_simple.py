"""
Xquik MCP Server - Direct Integration
Uses x-twitter-scraper Python SDK

pip install x-twitter-scraper
"""

import os
from x_twitter_scraper import XTwitterScraper

# Initialize with API key
xquik = XTwitterScraper(api_key=os.getenv("XQUIK_API_KEY"))

# Check account balance
account = xquik.account.get()
print(f"Plan: {account['plan']}")
print(f"Monitors: {account['monitorsAllowed']} allowed, {account['monitorsUsed']} used")

# Get balance
balance = xquik.credits.get_balance()
print(f"Credits: {balance['credits']}")

# Fetch user tweets
result = xquik.lookup.tweets(usernames=["lookonchain", "saylor", "zachxbt"], maxResults=10)
print(f"Fetched {len(result['tweets'])} tweets")
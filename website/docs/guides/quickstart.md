---
sidebar_position: 2
title: Quick Start (5 Minutes)
slug: /guides/quickstart
---

# Quick Start Guide

Get TrashAlert running in 5 minutes!

## Step 1: Clone & Setup (1 minute)

```bash
git clone https://github.com/TombStoneDash/TrashAlert.git
cd TrashAlert

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or: venv\Scripts\activate (Windows)

# Install dependencies
pip install -r requirements.txt
```

## Step 2: Initialize Database (1 minute)

```bash
# Copy environment file
cp .env.example .env

# Initialize database with sample data
python scripts/init_db.py
```

## Step 3: Start API Server (1 minute)

```bash
uvicorn app.main:app --reload
```

You'll see:
```
Uvicorn running on http://127.0.0.1:8000
```

## Step 4: Test the API (2 minutes)

Open a new terminal and try these commands:

### Health Check
```bash
curl http://localhost:8000/
```

Response:
```json
{
  "status": "healthy",
  "service": "TrashAlert API",
  "version": "1.0.0"
}
```

### Lookup Address
```bash
curl "http://localhost:8000/lookup?address=1122%20Palmview%20Ave,%20El%20Centro,%20CA"
```

Response:
```json
{
  "matched_address": "1122 Palmview Ave, El Centro, CA",
  "city_name": "El Centro",
  "trash_day_of_week": "Wednesday",
  "recycling_day_of_week": "Friday",
  "data_source": "CROWD_VERIFIED",
  "consensus_reports_count": 12,
  "consensus_agreement_ratio": 0.92
}
```

### Submit a Report
```bash
curl -X POST http://localhost:8000/report \
  -H "Content-Type: application/json" \
  -d '{
    "address": "1122 Palmview Ave, El Centro, CA",
    "trash_day": "WED"
  }'
```

### Get Statistics
```bash
curl http://localhost:8000/stats | jq .
```

## That's It!

You now have TrashAlert running locally. Here are some next steps:

### Try the Web Interface

Open http://localhost:8000/docs in your browser to see the interactive API documentation.

### Use the JavaScript Client

```javascript
// In your browser console
const api = new TrashAlertAPI('http://localhost:8000');

// Try a lookup
api.lookup('1122 Palmview Ave, El Centro, CA')
  .then(result => console.log(result));

// Submit a report
api.submitReport('1122 Palmview Ave, El Centro, CA', 'WED')
  .then(result => console.log(result));
```

### Test with Different Cities

```bash
# Imperial
curl "http://localhost:8000/lookup?address=Main%20St,%20Imperial,%20CA"

# Brawley
curl "http://localhost:8000/lookup?address=Main%20St,%20Brawley,%20CA"

# San Diego
curl "http://localhost:8000/lookup?address=Broadway,%20San%20Diego,%20CA"
```

## Troubleshooting

**Port already in use?**
```bash
uvicorn app.main:app --reload --port 8001
```

**Database error?**
```bash
python -m alembic upgrade head
```

**Module not found?**
```bash
# Make sure virtual environment is activated
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

## Next Steps

1. **[Read the API Overview](/docs/api/overview)** - Understand authentication and rate limits
2. **[Explore Endpoints](/docs/api/endpoints/lookup)** - Learn all available endpoints
3. **[Set Up Properly](/docs/guides/setup)** - Complete local development setup
4. **[Deploy to Production](/docs/guides/deployment)** - Host TrashAlert online
5. **[Contribute](/docs/guides/contributing)** - Help improve TrashAlert

## Common Tasks

### Change the API Port

```bash
uvicorn app.main:app --reload --port 3000
```

### Use PostgreSQL Instead of SQLite

```bash
# In .env file:
DATABASE_URL=postgresql://user:password@localhost/trashalert

# Then run migrations
python -m alembic upgrade head
```

### Reset Database

```bash
# Delete SQLite database
rm data/trashalert.db

# Reinitialize
python scripts/init_db.py
```

### Enable Debug Mode

```bash
# In .env
DEBUG=true

# Restart server
uvicorn app.main:app --reload
```

## Need Help?

- Check the [Full Setup Guide](/docs/guides/setup)
- Read the [API Documentation](/docs/api/overview)
- Visit [GitHub Issues](https://github.com/TombStoneDash/TrashAlert/issues)

Enjoy! 🎉


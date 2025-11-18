# AI-Powered Schedule Classifier

## Overview

The AI Schedule Classifier is a natural language processing feature that converts messy, human-written text descriptions of trash pickup schedules into structured, normalized schedule objects.

This feature uses OpenAI's GPT models to understand various ways people describe their trash pickup schedules and extracts key information like:
- **Pickup day** (MON, TUE, WED, etc.)
- **Frequency** (weekly, biweekly, monthly)
- **Collection type** (trash, recycling, green_waste, bulk)
- **Exceptions** (holidays, special dates, rescheduled pickups)

## Architecture

The system consists of three main components:

1. **AI Classifier** (`app/ai_classifier.py`) - Uses OpenAI API to classify text
2. **Cache System** (`app/ai_cache.py`) - Two-tier caching (memory + database)
3. **REST API Endpoint** (`/ai-classify`) - Exposes classification functionality

### Flow Diagram

```
User Input (Natural Language)
        ↓
   /ai-classify endpoint
        ↓
   Check Cache (Memory → DB)
        ↓
   [Cache Hit] → Return cached result
        ↓
   [Cache Miss] → Call OpenAI API
        ↓
   Parse & Normalize Response
        ↓
   Store in Cache
        ↓
   Return Structured Schedule
```

## API Endpoints

### POST /ai-classify

Classifies natural language schedule descriptions into structured format.

**Request Body:**
```json
{
  "text": "Trash pickup is every Monday. Recycling on Wednesdays every other week.",
  "context": {
    "city": "San Diego",
    "year": 2025
  }
}
```

**Response:**
```json
{
  "schedules": [
    {
      "collection_type": "trash",
      "pickup_day": "MON",
      "frequency": "weekly",
      "exceptions": [],
      "confidence": 0.95,
      "raw_text": "Trash pickup is every Monday. Recycling on Wednesdays every other week."
    },
    {
      "collection_type": "recycling",
      "pickup_day": "WED",
      "frequency": "biweekly",
      "exceptions": [],
      "confidence": 0.92,
      "raw_text": "Trash pickup is every Monday. Recycling on Wednesdays every other week."
    }
  ],
  "success": true,
  "cached": false
}
```

**With Exceptions:**
```json
{
  "text": "Garbage collection Thursday mornings, no pickup on Christmas, moved to Friday"
}
```

Response:
```json
{
  "schedules": [
    {
      "collection_type": "trash",
      "pickup_day": "THU",
      "frequency": "weekly",
      "exceptions": [
        {
          "exception_date": "2025-12-25",
          "rescheduled_date": "2025-12-26",
          "is_cancelled": false,
          "reason": "Christmas",
          "notes": "Moved to Friday"
        }
      ],
      "confidence": 0.88,
      "raw_text": "Garbage collection Thursday mornings, no pickup on Christmas, moved to Friday"
    }
  ],
  "success": true,
  "cached": false
}
```

### GET /ai-classify/popular

Returns the most popular (frequently classified) phrases.

**Query Parameters:**
- `limit` (optional, default: 10) - Maximum number of phrases to return

**Response:**
```json
{
  "popular_phrases": [
    {
      "text": "Trash pickup is every Monday",
      "hit_count": 156,
      "confidence_avg": 0.95,
      "created_at": "2025-01-15T10:30:00",
      "last_accessed_at": "2025-01-18T14:20:00"
    },
    {
      "text": "Recycling every other Wednesday",
      "hit_count": 89,
      "confidence_avg": 0.92,
      "created_at": "2025-01-16T11:15:00",
      "last_accessed_at": "2025-01-18T13:45:00"
    }
  ],
  "total_returned": 2
}
```

### POST /ai-classify/cache/clear

Clears the AI classification cache.

**Query Parameters:**
- `cache_type` (optional, default: "memory") - Type of cache to clear: "memory", "db", or "all"

**Response:**
```json
{
  "success": true,
  "message": "Cache cleared: memory"
}
```

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure OpenAI API Key

Set your OpenAI API key as an environment variable:

```bash
export OPENAI_API_KEY="sk-..."
```

Or add it to your `.env` file:

```
OPENAI_API_KEY=sk-...
```

### 3. Run Database Migrations

The cache table will be automatically created when you start the application:

```bash
python -m uvicorn app.main:app --reload
```

## Usage Examples

### Python Client Example

```python
import requests

url = "http://localhost:8000/ai-classify"

# Simple weekly trash
response = requests.post(url, json={
    "text": "Trash pickup is every Monday"
})

result = response.json()
print(result["schedules"])
# [{"collection_type": "trash", "pickup_day": "MON", "frequency": "weekly", ...}]

# Multiple collection types
response = requests.post(url, json={
    "text": "Garbage on Tuesdays, recycling every other Friday, yard waste on Wednesdays",
    "context": {"city": "San Diego"}
})

schedules = response.json()["schedules"]
print(f"Found {len(schedules)} schedules")

# With holiday exceptions
response = requests.post(url, json={
    "text": "Trash is Thursday, no pickup on Thanksgiving, moved to Friday that week"
})

schedule = response.json()["schedules"][0]
exceptions = schedule["exceptions"]
print(f"Found {len(exceptions)} exception(s)")
```

### cURL Examples

```bash
# Simple classification
curl -X POST http://localhost:8000/ai-classify \
  -H "Content-Type: application/json" \
  -d '{"text": "Trash pickup is every Monday"}'

# With context
curl -X POST http://localhost:8000/ai-classify \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Recycling on Wednesdays every other week",
    "context": {"city": "El Centro", "year": 2025}
  }'

# Get popular phrases
curl http://localhost:8000/ai-classify/popular?limit=5

# Clear cache
curl -X POST "http://localhost:8000/ai-classify/cache/clear?cache_type=memory"
```

## Supported Input Patterns

The classifier understands many natural language patterns:

### Day Variations
- "Monday", "mon", "Mondays", "every Monday"
- "Tuesday morning", "Wed afternoon", "Thursday evenings"

### Frequency Variations
- "every week", "weekly", "each week"
- "every other week", "bi-weekly", "biweekly", "every two weeks"
- "once a month", "monthly", "first Monday of the month"

### Collection Type Variations
- **Trash**: "trash", "garbage", "waste", "refuse"
- **Recycling**: "recycling", "recyclables", "blue bin"
- **Green Waste**: "yard waste", "green waste", "lawn clippings", "garden waste"
- **Bulk**: "bulk pickup", "large items", "furniture pickup"

### Exception Patterns
- "no pickup on Christmas"
- "closed on Thanksgiving, moved to Friday"
- "holiday schedule: no service July 4th"
- "pickup delayed one day for New Year's"

## Confidence Scores

Each classified schedule includes a confidence score (0.0 to 1.0):

- **0.9 - 1.0**: Very clear, unambiguous input
- **0.7 - 0.9**: Clear input with minor ambiguity
- **0.5 - 0.7**: Moderate ambiguity
- **0.3 - 0.5**: Significant uncertainty
- **0.0 - 0.3**: Very uncertain classification

**Example confidence levels:**

| Input | Confidence |
|-------|-----------|
| "Trash pickup every Monday" | 0.95 |
| "I think it's Monday or Tuesday" | 0.40 |
| "Garbage collection on weekdays" | 0.30 |

## Caching

The system uses a two-tier caching strategy:

### 1. In-Memory Cache (L1)
- Fast lookup (< 1ms)
- LRU eviction policy
- Default size: 1000 entries
- TTL: 1 hour

### 2. Database Cache (L2)
- Persistent storage
- Tracks hit counts and statistics
- No size limit
- Automatic cleanup of old entries

### Cache Benefits
- **Cost Savings**: Reduces OpenAI API calls
- **Speed**: Instant responses for cached phrases
- **Analytics**: Track popular user inputs

### Cache Statistics

View cache performance in the `/stats` endpoint:

```bash
curl http://localhost:8000/stats
```

Response includes:
```json
{
  "ai_cache_stats": {
    "memory_hits": 245,
    "db_hits": 67,
    "misses": 89,
    "total_requests": 401,
    "hit_rate": 0.778,
    "memory_cache_size": 156
  }
}
```

## Integration with Existing System

The AI classifier integrates seamlessly with TrashAlert's existing schedule system:

### Data Format Compatibility

The classifier outputs match the existing schedule format:

```python
# Existing schedule format (from parsers)
from scripts.data_collection.schedule_parsers.base_parser import ScheduleData

schedule = ScheduleData(
    address="123 Main St",
    day_of_week="MON",
    collection_type="trash",
    recurrence="weekly",
    confidence=1.0
)

# AI classifier output (same fields)
classified = ClassifiedSchedule(
    pickup_day="MON",           # Maps to day_of_week
    collection_type="trash",
    frequency="weekly",         # Maps to recurrence
    confidence=0.95
)
```

### Use Cases

1. **Crowdsourced Data Enhancement**
   - Users submit natural language reports
   - AI extracts structured data
   - Integrates with consensus system

2. **Municipal Data Parser Fallback**
   - When structured parsers fail
   - AI can extract from text descriptions
   - Provides confidence scores for validation

3. **User-Friendly Input**
   - Mobile app text input
   - Voice-to-text descriptions
   - SMS submissions

## Error Handling

The system handles various error conditions gracefully:

### No API Key Configured
```json
{
  "schedules": [],
  "success": false,
  "error": "Classification failed: OpenAI API key not configured",
  "cached": false
}
```

### Invalid Input
```json
{
  "detail": [
    {
      "loc": ["body", "text"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### Rate Limiting
```json
{
  "detail": "Too many requests. Please try again later."
}
```

## Testing

### Run Unit Tests

```bash
# Run all AI classifier tests
pytest tests/test_ai_classifier.py -v

# Run cache tests
pytest tests/test_ai_cache.py -v

# Run with coverage
pytest tests/test_ai_classifier.py tests/test_ai_cache.py --cov=app.ai_classifier --cov=app.ai_cache
```

### Test Coverage

The test suite covers:
- ✓ Simple weekly schedules
- ✓ Biweekly schedules
- ✓ Multiple collection types
- ✓ Holiday exceptions
- ✓ Cancelled pickups
- ✓ Uncertain classifications
- ✓ Various input patterns
- ✓ Cache operations (memory and DB)
- ✓ Error handling

## Performance

### Response Times

- **Cache Hit (Memory)**: < 5ms
- **Cache Hit (Database)**: 10-20ms
- **Cache Miss (OpenAI API)**: 500-2000ms

### Cost Optimization

Using `gpt-4o-mini` model:
- Cost per classification: ~$0.0001 - $0.0003
- 1000 classifications: ~$0.10 - $0.30

With 80% cache hit rate:
- Effective cost: ~$0.02 - $0.06 per 1000 requests

## Monitoring

### Key Metrics to Track

1. **Cache Hit Rate**: Target > 70%
2. **API Response Time**: Target < 1000ms (p95)
3. **Classification Confidence**: Average > 0.80
4. **Error Rate**: Target < 1%

### Logs

The system logs all classification attempts:

```
INFO: AI classify request: 'Trash pickup is every Monday...'
INFO: AI classify success: 'Trash pickup is every Monday...' -> 1 schedule(s) (850.23ms)
INFO: AI classify cache hit: 'Trash pickup is every Monday...' (2.45ms)
```

## Future Enhancements

Potential improvements:

1. **Multi-language Support**: Support Spanish, Chinese, etc.
2. **Custom Models**: Fine-tune models on TrashAlert data
3. **Batch Processing**: Classify multiple texts in one request
4. **Smart Suggestions**: Suggest corrections for low-confidence results
5. **Learning from Corrections**: Track user feedback to improve accuracy

## Troubleshooting

### Common Issues

**Issue**: 503 error "AI classification service not configured"
- **Solution**: Set `OPENAI_API_KEY` environment variable

**Issue**: Low confidence scores on clear inputs
- **Solution**: Add context to the request (city, year)

**Issue**: High API costs
- **Solution**: Check cache hit rate, increase cache size

**Issue**: Slow response times
- **Solution**: Monitor OpenAI API status, check network latency

## Support

For issues or questions:
- Check logs: `tail -f logs/app.log`
- View stats: `GET /stats`
- Clear cache: `POST /ai-classify/cache/clear`
- Run tests: `pytest tests/test_ai_classifier.py -v`

## License

Part of the TrashAlert project. See main README for license information.

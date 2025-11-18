# Multi-City Bulk OSM Import Pipeline

## Overview

The bulk import pipeline is a robust, production-ready system for importing OpenStreetMap (OSM) address data across multiple cities automatically. It features:

- **Automated multi-city processing** - Import all cities from cities.yaml without manual intervention
- **Rate limiting** - Respects Overpass API usage policies (3-second delay between cities)
- **Error recovery** - Automatic retries with exponential backoff
- **Resumable checkpoints** - Resume failed runs from the last successful city
- **Progress tracking** - Database-backed status tracking for each city
- **Live dashboard** - Real-time monitoring via web interface
- **Comprehensive logging** - Detailed logs for debugging and monitoring

## Architecture

### Components

1. **Bulk Import Script** (`scripts/bulk_import_pipeline.py`)
   - Orchestrates the entire import process
   - Manages database state and checkpoints
   - Handles error recovery and retries

2. **Database Models** (`app/models.py`)
   - `PipelineRun` - Tracks overall pipeline execution
   - `PipelineCityStatus` - Tracks per-city progress and status

3. **API Endpoints** (`app/main.py`)
   - `GET /pipeline/status` - Current pipeline status
   - `GET /pipeline/runs` - List all pipeline runs
   - `GET /pipeline/runs/{id}` - Detailed run information

4. **Dashboard** (`frontend/pipeline-status.html`)
   - Real-time status visualization
   - Progress tracking per city
   - Error display and debugging

### Data Flow

```
cities.yaml
    ↓
BulkImportPipeline
    ↓
┌─────────────────────────┐
│  For each city:         │
│  1. Fetch boundaries    │ (optional)
│  2. Build subdivisions  │ (optional)
│  3. Fetch OSM addresses │ (required)
│  4. Save to raw CSV     │
│  5. Update status       │
│  6. Save checkpoint     │
└─────────────────────────┘
    ↓
data/raw/addresses_osm_raw.csv
    ↓
Database status tracking
    ↓
Dashboard visualization
```

## Usage

### Basic Usage

Import all cities:
```bash
python scripts/bulk_import_pipeline.py --all
```

Import specific state:
```bash
python scripts/bulk_import_pipeline.py --state CA
```

Import specific city:
```bash
python scripts/bulk_import_pipeline.py --city-id ca_san_diego
```

### Resume Failed Run

If a pipeline run fails or is interrupted, you can resume it:

```bash
python scripts/bulk_import_pipeline.py --resume <run_id>
```

The run ID is displayed when the pipeline starts and can also be found in the dashboard or via the API.

### Skip Optional Steps

To speed up imports, you can skip boundaries and subdivisions:

```bash
python scripts/bulk_import_pipeline.py --all --skip-boundaries --skip-subdivisions
```

## Configuration

Pipeline settings are configured in `config/config.yaml`:

```yaml
overpass_api:
  url: "https://overpass-api.de/api/interpreter"
  timeout_seconds: 120
  rate_limit_delay_seconds: 3  # Between cities
  retry:
    max_attempts: 4
    initial_delay_seconds: 2
    backoff_multiplier: 2.0
    max_delay_seconds: 30
```

### Rate Limiting

The pipeline includes two levels of rate limiting:

1. **Between cities**: 3-second delay (configurable)
2. **API retries**: Exponential backoff (2s, 4s, 8s, 16s)

This ensures compliance with Overpass API fair use policies.

## Database Schema

### PipelineRun Table

Tracks overall pipeline execution:

| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| run_type | String | full, incremental, repair |
| status | String | pending, running, completed, failed, paused |
| city_filter | String | Filter used (e.g., "all", "state:CA") |
| total_cities | Integer | Number of cities to process |
| completed_cities | Integer | Cities successfully processed |
| failed_cities | Integer | Cities that failed |
| total_addresses_fetched | Integer | Total addresses imported |
| error_count | Integer | Number of errors encountered |
| last_error | Text | Most recent error message |
| last_processed_city_id | String | Last successfully processed city |
| checkpoint_data | JSON | Checkpoint state for resumability |
| started_at | DateTime | Run start time |
| completed_at | DateTime | Run completion time |

### PipelineCityStatus Table

Tracks per-city progress:

| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| pipeline_run_id | Integer | Foreign key to PipelineRun |
| city_id | String | City identifier from cities.yaml |
| city_name | String | Human-readable city name |
| status | String | pending, running, completed, failed, skipped |
| current_step | String | boundaries, subdivisions, addresses, etc. |
| steps_completed | JSON | List of completed step names |
| addresses_fetched | Integer | Number of addresses fetched |
| error_message | Text | Error message if failed |
| retry_count | Integer | Number of retry attempts |
| started_at | DateTime | City processing start time |
| completed_at | DateTime | City processing completion time |

## Error Handling

### Automatic Retries

The pipeline automatically retries failed operations:

1. **Overpass API timeouts**: 4 attempts with exponential backoff
2. **HTTP 429 (rate limit)**: Extended backoff, then retry
3. **Network errors**: Automatic retry with backoff
4. **City-level failures**: Logged, marked as failed, pipeline continues

### Recovery Strategies

**Scenario 1: Pipeline Interrupted (Ctrl+C)**
```bash
# Pipeline saves checkpoint before exiting
# Resume with:
python scripts/bulk_import_pipeline.py --resume <run_id>
```

**Scenario 2: Individual City Fails**
```bash
# Pipeline continues to next city
# Failed city is marked in database
# After pipeline completes, re-run failed cities:
python scripts/bulk_import_pipeline.py --city-id ca_failed_city
```

**Scenario 3: Complete Pipeline Failure**
```bash
# Check the error in dashboard or database
# Fix underlying issue (e.g., network, API key)
# Resume from checkpoint:
python scripts/bulk_import_pipeline.py --resume <run_id>
```

## Monitoring

### Dashboard

Access the live dashboard at:
```
http://localhost:8000/pipeline-status.html
```

Features:
- Real-time progress tracking
- Per-city status visualization
- Error messages and debugging info
- Auto-refresh every 10 seconds
- Historical run data

### API Endpoints

**Get Current Status**
```bash
curl http://localhost:8000/pipeline/status
```

Response:
```json
{
  "has_active_run": true,
  "active_run": {
    "id": 5,
    "status": "running",
    "progress_percent": 45.0,
    "completed_cities": 9,
    "total_cities": 20,
    "total_addresses_fetched": 12543
  }
}
```

**Get Run Details**
```bash
curl http://localhost:8000/pipeline/runs/5
```

**List All Runs**
```bash
curl http://localhost:8000/pipeline/runs?status=completed&limit=10
```

### Logging

Logs are written to stdout with structured format:

```
2025-11-18 10:30:45 - bulk_import_pipeline - INFO - Pipeline run #5: 20 cities to process
2025-11-18 10:30:45 - bulk_import_pipeline - INFO - Processing: San Diego, CA (ID: ca_san_diego)
2025-11-18 10:31:12 - bulk_import_pipeline - INFO - ✓ Successfully processed San Diego: 2547 addresses
2025-11-18 10:31:15 - bulk_import_pipeline - INFO - Rate limiting: waiting 3s...
```

## Performance

### Benchmarks

Typical performance (based on testing):

- **Small city** (< 5,000 addresses): 15-30 seconds
- **Medium city** (5,000-50,000 addresses): 30-90 seconds
- **Large city** (> 50,000 addresses): 90-300 seconds

**Full California import** (10 cities):
- **Total time**: ~15-20 minutes
- **Total addresses**: ~50,000-100,000
- **Average per city**: 1.5-2 minutes

### Optimization Tips

1. **Skip optional steps** for faster imports:
   ```bash
   --skip-boundaries --skip-subdivisions
   ```

2. **Process in batches** by state:
   ```bash
   # Instead of --all, do:
   python scripts/bulk_import_pipeline.py --state CA
   python scripts/bulk_import_pipeline.py --state TX
   ```

3. **Run during off-peak hours** to reduce Overpass API congestion

4. **Monitor API status**: https://overpass-api.de/api/status

## Troubleshooting

### Common Issues

**Issue: "No addresses fetched for <city>"**
- **Cause**: City name mismatch in OSM database
- **Solution**: Check city name spelling in cities.yaml, try alternative names
- **Debug**: Use http://overpass-turbo.eu to test queries manually

**Issue: "HTTP 429 Too Many Requests"**
- **Cause**: Overpass API rate limiting
- **Solution**: Pipeline automatically retries with backoff
- **Prevention**: Increase `rate_limit_delay_seconds` in config

**Issue: "Request timed out"**
- **Cause**: Large city or slow API response
- **Solution**: Pipeline automatically retries
- **Workaround**: Increase `timeout_seconds` in config

**Issue: "Pipeline run X not found" when resuming**
- **Cause**: Invalid run ID
- **Solution**: Check run ID in dashboard or database
- **Command**: `python scripts/bulk_import_pipeline.py --all` (start new run)

### Debugging

Enable debug logging:
```python
# In config/config.yaml
logging:
  level: "DEBUG"
```

Check database directly:
```bash
sqlite3 data/trashalert.db
sqlite> SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT 5;
sqlite> SELECT * FROM pipeline_city_status WHERE pipeline_run_id = 5;
```

## Best Practices

1. **Always test with small subset first**
   ```bash
   python scripts/bulk_import_pipeline.py --city-id ca_imperial
   ```

2. **Monitor the dashboard during large imports**
   - Catch issues early
   - Verify data quality

3. **Run post-import validation**
   ```bash
   python scripts/sample_addresses_per_city.py --all
   python scripts/normalize_addresses.py
   ```

4. **Schedule regular imports** for data freshness
   - Weekly for active cities
   - Monthly for stable cities

5. **Backup database before major imports**
   ```bash
   cp data/trashalert.db data/trashalert.db.backup
   ```

## Integration with Existing Pipeline

The bulk importer produces the same output format as the existing single-city pipeline:

```
data/raw/addresses_osm_raw.csv
```

After bulk import, continue with existing scripts:

```bash
# Sample addresses
python scripts/sample_addresses_per_city.py --all

# Normalize and deduplicate
python scripts/normalize_addresses.py

# Build subdivisions (if needed)
python scripts/build_subdivisions.py --all
```

Or use the full pipeline orchestrator:

```bash
# Run complete pipeline (fetch + sample + normalize)
python scripts/run_full_pipeline.py --all
```

## Future Enhancements

Potential improvements for future versions:

1. **Incremental updates** - Only fetch new/changed addresses
2. **Parallel city processing** - Process multiple cities concurrently
3. **Email notifications** - Alert on completion or failures
4. **Metrics collection** - Track import performance over time
5. **Data validation** - Automated quality checks
6. **API integration** - Trigger imports via REST API
7. **Scheduling** - Built-in cron-like scheduling

## See Also

- [OSM Pipeline Documentation](OSM_PIPELINE.md)
- [City Configuration Guide](../config/cities.yaml)
- [API Documentation](API.md)
- [Database Schema](data_model.md)

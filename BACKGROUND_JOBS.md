# TrashAlert Background Jobs

This document describes the background job system for TrashAlert, which automates data processing tasks using APScheduler.

## Overview

The background job system runs scheduled tasks for:
1. **OSM Pipeline** - Fetches address data from OpenStreetMap (nightly)
2. **Crowd Consensus Refresh** - Recalculates consensus data from crowd reports (daily)
3. **Zone/Address Linkage** - Links addresses to pickup zones using GIS operations (weekly)

All jobs log execution metrics to `logs/cron.log`.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Compose                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐              ┌──────────────────────┐     │
│  │   API       │              │   Worker Service     │     │
│  │  (FastAPI)  │              │  (APScheduler)       │     │
│  │             │              │                      │     │
│  │  Port 8000  │              │  - OSM Pipeline      │     │
│  │             │              │  - Consensus Refresh │     │
│  │             │              │  - Zone Linkage      │     │
│  └──────┬──────┘              └──────────┬───────────┘     │
│         │                                │                 │
│         │         Shared Volumes         │                 │
│         │    ┌──────────────────────┐   │                 │
│         └────┤  ./data (SQLite DB)  ├───┘                 │
│              │  ./logs (Log files)  │                     │
│              └──────────────────────┘                     │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. Scheduler (`app/scheduler.py`)

The main scheduler module using APScheduler with:
- **BackgroundScheduler**: Non-blocking scheduler that runs in a separate thread
- **Job defaults**:
  - `coalesce=True`: Combine missed runs
  - `max_instances=1`: One instance per job at a time
  - `misfire_grace_time=300`: 5-minute grace period for delayed starts
- **Event listeners**: Log job execution success/failure

### 2. Worker Service (`worker.py`)

Standalone service that:
- Initializes and starts the scheduler
- Handles graceful shutdown (SIGINT, SIGTERM)
- Keeps the process running continuously
- Logs all scheduler activity

### 3. Logging (`logs/cron.log`)

All background jobs log to a dedicated cron log file:
- **Format**: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
- **Rotation**: 10MB max file size, 5 backup files
- **Metrics logged**:
  - Job start time
  - Job completion time
  - Duration (seconds)
  - Success/failure status
  - Error messages (if failed)

## Scheduled Jobs

### Job 1: OSM Pipeline (Nightly)

**Schedule**: Every day at 2:00 AM
**ID**: `osm_pipeline`
**Script**: `scripts/fetch_addresses_osm.py`

**What it does**:
- Fetches address data from OpenStreetMap Overpass API
- Processes all enabled cities in `config/cities.yaml`
- Extracts house numbers, streets, and coordinates
- Saves results to CSV files in `data/addresses/`

**Configuration**:
- Retry logic: Exponential backoff on API failures
- Rate limiting: Respects Overpass API rate limits
- Timeout: 300 seconds per request

**Example log output**:
```
2025-11-18 02:00:00 - cron - INFO - === Starting OSM Pipeline Job ===
2025-11-18 02:00:00 - cron - INFO - Fetching addresses from OpenStreetMap for all cities
2025-11-18 02:05:23 - cron - INFO - OSM Pipeline completed successfully. Duration: 323.45s
```

### Job 2: Crowd Consensus Refresh (Daily)

**Schedule**: Every day at 3:00 AM
**ID**: `crowd_consensus_refresh`
**Script**: `scripts/processing/update_crowd_consensus.py`

**What it does**:
- Recalculates consensus data for all addresses with crowd reports
- Aggregates trash/recycling/green waste day votes
- Calculates agreement ratios (most common value / total reports)
- Verifies consensus (requires ≥3 reports AND ≥75% agreement)
- Updates `crowd_consensus` table

**Consensus Logic**:
```python
# Verification criteria:
is_verified = (total_reports >= 3) AND (avg_agreement_ratio >= 0.75)

# Agreement ratio calculation:
agreement_ratio = count(most_common_value) / total_reports
```

**Example log output**:
```
2025-11-18 03:00:00 - cron - INFO - === Starting Crowd Consensus Refresh Job ===
2025-11-18 03:00:00 - cron - INFO - Recalculating crowd consensus for all addresses
2025-11-18 03:00:12 - cron - INFO - Crowd Consensus Refresh completed successfully. Duration: 12.34s
```

### Job 3: Zone/Address Linkage (Weekly)

**Schedule**: Every Sunday at 4:00 AM
**ID**: `zone_linkage_recalculation`
**Script**: `scripts/link_addresses_to_pickup_zones.py`

**What it does**:
- Links addresses to pickup zones using GIS point-in-polygon operations
- Loads pickup zone GeoJSON files from `data/gis/`
- Tests each address coordinate against zone geometries
- Updates `address_pickup_info` table with zone assignments
- Extracts official trash/recycling/green waste schedules from zones

**GIS Operations**:
- Uses GeoPandas and Shapely for spatial operations
- Optimized with `.prepare()` for faster point-in-polygon tests
- Handles multi-polygon zones

**Example log output**:
```
2025-11-18 04:00:00 - cron - INFO - === Starting Zone/Address Linkage Job ===
2025-11-18 04:00:00 - cron - INFO - Linking addresses to pickup zones
2025-11-18 04:01:45 - cron - INFO - Zone/Address Linkage completed successfully. Duration: 105.67s
```

## Running the Background Jobs

### In Docker (Production)

Background jobs run automatically in the `worker` container:

```bash
# Start all services (API + Worker)
docker-compose up -d

# Check worker logs
docker-compose logs -f worker

# Check cron job logs
docker-compose exec worker cat /app/logs/cron.log

# Restart worker service
docker-compose restart worker

# Stop worker service
docker-compose stop worker
```

### Locally (Development)

Run the worker service directly on your machine:

```bash
# Install dependencies
pip install -r requirements.txt

# Run worker service
python worker.py

# The worker will start and log to logs/cron.log
```

**Output**:
```
2025-11-18 10:00:00 - cron - INFO - ============================================================
2025-11-18 10:00:00 - cron - INFO - TrashAlert Background Worker Service Starting
2025-11-18 10:00:00 - cron - INFO - ============================================================
2025-11-18 10:00:00 - cron - INFO - Background job scheduler started
2025-11-18 10:00:00 - cron - INFO - Added job: OSM Pipeline (runs nightly at 2:00 AM)
2025-11-18 10:00:00 - cron - INFO - Added job: Crowd Consensus Refresh (runs daily at 3:00 AM)
2025-11-18 10:00:00 - cron - INFO - Added job: Zone/Address Linkage (runs weekly on Sunday at 4:00 AM)
2025-11-18 10:00:00 - cron - INFO - Scheduled jobs:
2025-11-18 10:00:00 - cron - INFO -   - OSM Address Pipeline (Nightly) (ID: osm_pipeline)
2025-11-18 10:00:00 - cron - INFO -     Next run: 2025-11-19T02:00:00
2025-11-18 10:00:00 - cron - INFO -     Trigger: cron[hour='2', minute='0']
2025-11-18 10:00:00 - cron - INFO - ============================================================
2025-11-18 10:00:00 - cron - INFO - Worker service is running. Press Ctrl+C to stop.
2025-11-18 10:00:00 - cron - INFO - ============================================================
```

### Manual Job Execution

You can also run individual jobs manually:

```bash
# OSM Pipeline
python scripts/fetch_addresses_osm.py --all

# Crowd Consensus Refresh
python scripts/processing/update_crowd_consensus.py

# Zone/Address Linkage
python scripts/link_addresses_to_pickup_zones.py
```

## Monitoring

### Check Job Status

Monitor background jobs using the logs:

```bash
# Tail cron logs in real-time
tail -f logs/cron.log

# View recent job executions
tail -n 100 logs/cron.log

# Search for failed jobs
grep "ERROR" logs/cron.log

# Count successful jobs today
grep "$(date +%Y-%m-%d)" logs/cron.log | grep "completed successfully" | wc -l
```

### Health Checks

The worker service has a health check that verifies:
- Cron log file exists (`/app/logs/cron.log`)
- Worker container is running

```bash
# Check worker health status
docker-compose ps worker

# Expected output:
# NAME                  STATUS
# trashalert-worker     Up (healthy)
```

### Job Metrics

Each job logs the following metrics:

```python
{
    "job": "job_name",
    "success": true/false,
    "duration_seconds": 123.45,
    "timestamp": "2025-11-18T02:00:00",
    "error": "error message (if failed)"
}
```

## Customizing Job Schedules

Edit `app/scheduler.py` to modify job schedules:

```python
# Change OSM Pipeline to run every 6 hours
self.scheduler.add_job(
    func=self.run_osm_pipeline,
    trigger=CronTrigger(hour='*/6'),  # Every 6 hours
    id='osm_pipeline',
    name='OSM Address Pipeline (Every 6 Hours)',
    replace_existing=True
)

# Change Consensus Refresh to run every hour
self.scheduler.add_job(
    func=self.run_crowd_consensus_refresh,
    trigger=CronTrigger(minute=0),  # Every hour at minute 0
    id='crowd_consensus_refresh',
    name='Crowd Consensus Refresh (Hourly)',
    replace_existing=True
)

# Change Zone Linkage to run monthly (first day at 4:00 AM)
self.scheduler.add_job(
    func=self.run_zone_linkage_recalculation,
    trigger=CronTrigger(day=1, hour=4, minute=0),  # First day of month
    id='zone_linkage_recalculation',
    name='Zone/Address Linkage (Monthly)',
    replace_existing=True
)
```

### Cron Trigger Syntax

APScheduler uses cron-style triggers:

| Expression | Meaning |
|------------|---------|
| `hour=2, minute=0` | Every day at 2:00 AM |
| `hour='*/6'` | Every 6 hours |
| `day_of_week='mon'` | Every Monday |
| `day_of_week='sun', hour=4` | Every Sunday at 4:00 AM |
| `day=1, hour=0` | First day of every month at midnight |
| `minute='*/15'` | Every 15 minutes |

## Troubleshooting

### Worker Not Starting

```bash
# Check worker container logs
docker-compose logs worker

# Common issues:
# 1. Missing APScheduler dependency
docker-compose exec worker pip install apscheduler

# 2. Permission issues with logs directory
chmod -R 777 logs/

# 3. Database lock (SQLite)
# Stop all services and restart
docker-compose down
docker-compose up -d
```

### Jobs Not Running

```bash
# Check if scheduler is active
docker-compose exec worker ps aux | grep python

# Verify job schedule
docker-compose logs worker | grep "Next run"

# Manual job execution to test
docker-compose exec worker python -c "from app.scheduler import BackgroundJobScheduler; s = BackgroundJobScheduler(); s.run_osm_pipeline()"
```

### Job Failures

```bash
# Check error logs
grep "ERROR" logs/cron.log

# Common issues:
# 1. Database locked - increase SQLite timeout
# 2. Overpass API rate limit - adjust retry delays
# 3. Missing GeoJSON files - ensure data/gis/ has zone files
# 4. Network issues - check firewall/proxy settings
```

### High Memory Usage

```bash
# Monitor container memory
docker stats trashalert-worker

# If memory usage is high:
# 1. Reduce number of cities processed at once
# 2. Add pagination to database queries
# 3. Clear pandas DataFrame memory after processing
# 4. Increase Docker memory limits in docker-compose.yml
```

## Environment Variables

Configure behavior with environment variables in `docker-compose.yml`:

```yaml
environment:
  - ENVIRONMENT=production  # production, development, test
  - LOG_LEVEL=info          # debug, info, warning, error
  - DB_PATH=/app/data/trashalert.db  # Custom database path
```

## Adding New Jobs

To add a new background job:

1. **Create job function** in `app/scheduler.py`:
```python
def run_my_new_job(self):
    """My new background job."""
    start_time = datetime.now()
    cron_logger.info("=== Starting My New Job ===")

    try:
        # Your job logic here
        # ...

        success = True
        duration = (datetime.now() - start_time).total_seconds()
        cron_logger.info(f"My New Job completed. Duration: {duration:.2f}s")

        return {
            "job": "my_new_job",
            "success": success,
            "duration_seconds": duration,
            "timestamp": start_time.isoformat()
        }
    except Exception as e:
        cron_logger.error(f"My New Job failed: {e}", exc_info=True)
        return {
            "job": "my_new_job",
            "success": False,
            "error": str(e)
        }
```

2. **Add job to scheduler** in `add_jobs()` method:
```python
self.scheduler.add_job(
    func=self.run_my_new_job,
    trigger=CronTrigger(hour=5, minute=0),  # Daily at 5:00 AM
    id='my_new_job',
    name='My New Job (Daily)',
    replace_existing=True
)
```

3. **Restart worker service**:
```bash
docker-compose restart worker
```

## Best Practices

1. **Keep jobs idempotent**: Jobs should produce the same result if run multiple times
2. **Handle failures gracefully**: Use try-except blocks and log errors
3. **Avoid long-running jobs**: Break large tasks into smaller chunks
4. **Use database transactions**: Ensure data consistency with ACID operations
5. **Monitor job execution**: Regularly check logs for failures
6. **Test jobs manually**: Run jobs manually before scheduling
7. **Set appropriate timeouts**: Prevent jobs from hanging indefinitely
8. **Use locking for shared resources**: Prevent concurrent modifications to SQLite

## Performance Optimization

- **OSM Pipeline**: Process cities in batches, use connection pooling
- **Consensus Refresh**: Use bulk updates instead of row-by-row
- **Zone Linkage**: Cache prepared geometries, use spatial indexes
- **Logging**: Use log rotation to prevent disk space issues
- **Database**: Add indexes on frequently queried columns

## Security Considerations

- Worker runs with same permissions as API (non-root user `trashalert`)
- Logs may contain IP addresses (ensure GDPR compliance)
- API keys (if added) should use environment variables, not hardcoded
- Database file permissions: 0644 (read/write for owner, read for group)
- Validate all external API responses (Overpass API)

## Future Enhancements

Potential improvements for the background job system:

1. **Distributed task queue**: Migrate to Celery + Redis for scalability
2. **Job result storage**: Store job results in database for historical analysis
3. **Email/Slack notifications**: Alert on job failures
4. **Dynamic scheduling**: Adjust schedules based on system load
5. **Job dependencies**: Chain jobs (e.g., OSM → Zone Linkage → Consensus)
6. **Job prioritization**: High-priority jobs run first
7. **Retry policies**: Automatic retry with exponential backoff
8. **Monitoring dashboard**: Web UI to view job status and metrics
9. **Job cancellation**: API to cancel running jobs
10. **Timezone-aware scheduling**: Handle daylight saving time correctly

## License

Same as TrashAlert project license.

---
sidebar_position: 1
title: System Architecture
slug: /architecture/overview
---

# TrashAlert System Architecture

High-level overview of TrashAlert's architecture, components, and data flow.

## System Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          TRASHALERT SYSTEM                               │
└─────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────┐
│   Client Applications     │
├──────────────────────────┤
│ - Web App (React)        │
│ - Mobile App (React Native)
│ - Admin Dashboard        │
│ - 3rd Party Integrations │
└──────────────────┬───────┘
                   │
                   ▼
        ┌──────────────────────┐
        │   API Gateway        │
        │   (Nginx)            │
        │ - SSL/TLS            │
        │ - Rate Limiting      │
        │ - Load Balancing     │
        └──────────┬───────────┘
                   │
        ┌──────────▼───────────┐
        │   FastAPI Service    │
        │ ┌────────────────┐   │
        │ │ Authentication │   │
        │ │ Rate Limiting  │   │
        │ │ Request Handler│   │
        │ └────────────────┘   │
        │        │             │
        │ ┌──────▼─────────┐   │
        │ │ Endpoints:     │   │
        │ │ - /lookup      │   │
        │ │ - /report      │   │
        │ │ - /interpret   │   │
        │ │ - /stats       │   │
        │ └────────────────┘   │
        └──────────┬────────────┘
                   │
        ┌──────────▼──────────────┐
        │   Business Logic        │
        │ ┌──────────────────┐    │
        │ │ - Address Lookup │    │
        │ │ - Consensus      │    │
        │ │ - Validation     │    │
        │ │ - AI Interpreter │    │
        │ └──────────────────┘    │
        └──────────┬──────────────┘
                   │
        ┌──────────▼──────────────┐
        │   Data Access Layer     │
        │ ┌──────────────────┐    │
        │ │ SQLAlchemy ORM   │    │
        │ │ - Models         │    │
        │ │ - Repositories   │    │
        │ │ - Cache Layer    │    │
        │ └──────────────────┘    │
        └──────────┬──────────────┘
                   │
        ┌──────────▼──────────────┐
        │   Persistence Layer     │
        │ ┌──────────────────┐    │
        │ │ - PostgreSQL DB  │    │
        │ │ - Redis Cache    │    │
        │ │ - File Storage   │    │
        │ └──────────────────┘    │
        └─────────────────────────┘
```

## Core Components

### 1. API Gateway

**Technology**: Nginx

**Responsibilities**:
- HTTPS/SSL termination
- Rate limiting
- Load balancing
- Reverse proxy to application servers

**Configuration**: `/config/nginx.conf`

### 2. Application Service

**Technology**: FastAPI (Python)

**Responsibilities**:
- Handle HTTP requests/responses
- Route to appropriate handlers
- Request validation
- Error handling
- Logging and monitoring

**Location**: `/app/main.py`

### 3. Business Logic

Organized by domain:

```
app/
├── database.py          # Database configuration
├── models.py            # SQLAlchemy models
├── schemas.py           # Pydantic request/response schemas
├── utils.py             # Utility functions
├── services.py          # Business logic services
├── ai_service.py        # AI-powered interpretation
├── rate_limiter.py      # Rate limiting logic
├── cache.py             # Caching layer
└── middleware.py        # HTTP middleware
```

### 4. Data Access Layer

**ORM**: SQLAlchemy

**Features**:
- Model definitions
- Query builders
- Transaction management
- Relationship management

### 5. Database Layer

**Primary**: PostgreSQL (production) / SQLite (development)

**Features**:
- Relational data storage
- Geospatial queries (PostGIS)
- Transactions
- Backups

## Data Models

### Core Entities

```
Cities
├── Addresses (many)
│   ├── CrowdReports (many)
│   ├── CrowdConsensus (one)
│   └── AddressPickupInfo (one)
├── PickupZones (many)
│   └── Schedules (many)
└── ScheduleExceptions (many)
```

See [Database Schema](/docs/architecture/database) for details.

## API Endpoints

### Public Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Health check |
| GET | `/lookup` | Address schedule lookup |
| POST | `/report` | Submit crowdsourced report |
| POST | `/interpret-address` | Parse freeform address |
| GET | `/stats` | System statistics |

### Documentation

- **Interactive Docs**: `/docs` (Swagger UI)
- **Alternative Docs**: `/redoc` (ReDoc)

## Request Flow

### Lookup Request Flow

```
1. Client Request
   GET /lookup?address=...
   │
2. Nginx (Reverse Proxy)
   - SSL/TLS decrypt
   - Rate limit check
   - Route to API
   │
3. FastAPI Handler
   - Parse request
   - Validate parameters
   - │
4. Business Logic
   - Normalize address
   - Search database
   - Calculate consensus
   - Apply source priority
   │
5. Database Query
   - Query addresses
   - Query reports
   - Join with consensus
   │
6. Response Assembly
   - Format response
   - Add headers
   - │
7. Client Response
   200 OK + JSON
```

### Report Submission Flow

```
1. Client Request
   POST /report
   JSON body with pickup days
   │
2. Validation
   - Validate address format
   - Validate day format
   - Check rate limits
   │
3. Database Operations
   - Find/create address
   - Insert report
   - Update consensus
   │
4. Consensus Calculation
   - Query all reports for address
   - Calculate mode
   - Compute agreement ratio
   - Determine verification status
   │
5. Response + Side Effects
   - Return updated consensus
   - Cache invalidation
   - Metrics recording
   │
6. Client Response
   200 OK + consensus data
```

## Key Features

### 1. Crowdsourcing Consensus

Multiple community observations are aggregated into a consensus schedule:

```
Reports: WED, WED, THU, WED, WED, WED
Consensus: Wednesday (5/6 = 83% agreement)
Verified: Yes (≥3 reports, ≥67% agreement)
```

### 2. Multi-Source Data

Intelligently combines official and community data:

```
Priority:
1. CROWD_VERIFIED (≥3 reports, ≥67% agreement)
2. OFFICIAL (municipal data)
3. CROWD_UNVERIFIED (insufficient reports)
4. UNKNOWN (no data)
```

### 3. AI Address Interpretation

Parse freeform text to normalized addresses:

```
Input: "my address is on main street in el centro"
Output: "1122 Main St, El Centro, CA"
Confidence: 0.85
Method: AI with geocoding fallback
```

### 4. Rate Limiting

Prevents abuse and ensures fair access:

```
- 60 requests/minute per IP (global)
- 10 reports/15min per IP (prevent spam)
- 3 reports/address per IP (prevent single-address spam)
```

### 5. Caching

Reduces database load:

```
- Address lookups: 24-hour cache
- Statistics: 5-minute cache
- City data: On-startup cache
- TTL configurable per query type
```

## Scalability Considerations

### Current Scale

- **Addresses**: ~250 per city
- **Cities**: 6 pilot cities
- **Reports**: Hundreds per week
- **Users**: Growing community

### Scaling Strategies

1. **Horizontal Scaling**
   - Multiple API servers
   - Load balancer (Nginx, HAProxy, etc.)
   - Shared database

2. **Vertical Scaling**
   - More CPU cores
   - More RAM
   - Faster storage (SSD)

3. **Database Optimization**
   - Query optimization
   - Indexing strategy
   - Connection pooling
   - Read replicas

4. **Caching Layer**
   - Redis for hot data
   - Client-side caching
   - CDN for static content

## Deployment Architecture

### Development

```
Local Machine
├── Python app
├── SQLite database
└── Nginx (optional)
```

### Production

```
Cloud Infrastructure
├── Load Balancer (AWS ELB, etc.)
├── API Servers (2-10 instances)
├── PostgreSQL (managed service)
├── Redis Cache (optional)
└── Monitoring & Logging
```

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Language** | Python 3.11+ | Backend development |
| **Framework** | FastAPI | Web framework |
| **ORM** | SQLAlchemy | Database abstraction |
| **Database** | PostgreSQL | Primary data store |
| **Cache** | Redis | Optional caching |
| **Validation** | Pydantic | Request/response validation |
| **Migration** | Alembic | Database migrations |
| **Server** | Uvicorn/Gunicorn | WSGI/ASGI server |
| **Reverse Proxy** | Nginx | Load balancing, SSL |
| **Containerization** | Docker | Deployment |
| **Monitoring** | Prometheus/Grafana | Metrics and visualization |

## Security Architecture

### Authentication & Authorization

- No authentication required for public endpoints (MVP)
- Optional API keys for future versions
- User rate limiting via IP + optional user_hash

### Data Protection

- HTTPS/TLS for all communications
- Password hashing for admin users
- SQL injection prevention via ORM
- Input validation and sanitization
- Rate limiting against abuse

### Infrastructure Security

- Firewalls
- DDoS protection
- Security group restrictions
- VPC isolation
- Regular security updates

See [Deployment Guide](/docs/guides/deployment) for security hardening.

## Monitoring & Observability

### Logging

```
- Structured JSON logs
- Request/response logging
- Error tracking (Sentry)
- Audit logging
```

### Metrics

```
- Request counts
- Response times
- Error rates
- Database performance
- Cache hit rates
```

### Alerting

```
- Uptime monitoring
- Error rate thresholds
- Performance degradation
- Database issues
```

## Integration Points

### External Services (Optional)

- **OpenAI/Anthropic**: AI address interpretation
- **Nominatim**: Reverse geocoding
- **Google Maps**: Optional geocoding
- **Sentry**: Error tracking
- **Prometheus**: Metrics collection

### Future Integrations

- Official city APIs
- Real-time tracking (GTFS, etc.)
- Mobile push notifications
- Email alerts
- Calendar integration

## Related Documentation

- **[Database Schema](/docs/architecture/database)** - Detailed data model
- **[Crowdsourcing Logic](/docs/architecture/crowdsourcing)** - Consensus algorithm
- **[API Reference](/docs/api/overview)** - Endpoint documentation
- **[Deployment](/docs/guides/deployment)** - Production deployment


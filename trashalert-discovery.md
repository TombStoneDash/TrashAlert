# TrashAlert Project Discovery
## Cross-Domain Strategy Analysis for TombStone Dash LLC

*Analysis Date: November 2025*
*Project: TrashAlert*
*Purpose: Extract insights for BluePlanet, CastAlert, and other TombStone Dash properties*

---

## Table of Contents

1. [Current Tech Stack](#1-current-tech-stack)
2. [Design System](#2-design-system)
3. [What's Working Well](#3-whats-working-well)
4. [Design DNA & Visual Elements](#4-design-dna--visual-elements)
5. [Technical Patterns](#5-technical-patterns)
6. [Recommendations for Sister Projects](#6-recommendations-for-sister-projects)
7. [Boundaries to Respect](#7-boundaries-to-respect)
8. [File Reference Guide](#8-file-reference-guide)

---

## 1. Current Tech Stack

### Backend

| Component | Technology | Version | Notes |
|-----------|------------|---------|-------|
| Framework | FastAPI | 0.109.0 | Modern async Python |
| Server | Uvicorn | 4 workers | Production ASGI |
| Database | PostgreSQL | 16 | Production (SQLite for dev) |
| ORM | SQLAlchemy | 2.0.25 | With Alembic migrations |
| Cache | Redis | 7-alpine | Sessions, queues, caching |
| Task Scheduling | APScheduler | 3.10.4+ | Background jobs |

### Frontend

| Component | Technology | Version | Notes |
|-----------|------------|---------|-------|
| Admin Dashboard | React | 19.2.0 | Modern React with hooks |
| Build Tool | Vite | 7.2.2 | Fast HMR, ESM-native |
| Routing | React Router | 7.9.6 | Client-side routing |
| Styling | Tailwind CSS | 3.4.18 | Utility-first CSS |
| Maps | Leaflet | 1.9.4 | With React-Leaflet 5.0 |
| Charts | Recharts | 3.4.1 | React charting |
| HTTP Client | Axios | 1.13.2 | With interceptors |
| Documentation | Docusaurus | 3.9.2 | Markdown/MDX docs |

### Authentication & Security

| Component | Technology | Details |
|-----------|------------|---------|
| Auth | JWT (PyJWT) | HS256 algorithm |
| Password Hashing | bcrypt (Passlib) | Industry standard |
| Access Tokens | 30 minutes | Short-lived for security |
| Refresh Tokens | 7 days | Longer session management |
| API Keys | SHA256 hashed | With scopes and rate limits |

### External Services

| Service | Provider | Purpose |
|---------|----------|---------|
| SMS | Twilio | Notification delivery |
| Email | SendGrid | Email notifications |
| AI/LLM | OpenAI, Anthropic | Address interpretation |
| Geocoding | GeoPy | Coordinate lookup |

### Data Processing & Geospatial

| Component | Technology | Purpose |
|-----------|------------|---------|
| Data Analysis | Pandas 2.0+ | Data manipulation |
| Geospatial | GeoPandas 0.14.0 | GIS operations |
| Geometry | Shapely 2.0+ | Zone detection |
| Route Optimization | OR-Tools 9.8+ | Fleet routing |
| Document Processing | PyPDF2, pdfplumber | Schedule parsing |
| Web Scraping | Beautiful Soup 4 | City website scraping |

### Deployment & CI/CD

| Component | Platform | Configuration |
|-----------|----------|---------------|
| Backend API | Railway | `railway.toml` |
| Admin Dashboard | Vercel | Vite build |
| Documentation | Vercel | Docusaurus SSG |
| Database | Railway PostgreSQL | Managed instance |
| Cache | Railway Redis | Managed instance |
| Reverse Proxy | Nginx | SSL, rate limiting |
| CI/CD | GitHub Actions | Test, lint, deploy |

---

## 2. Design System

### Color Palette

#### Primary Brand Colors
```css
/* TrashAlert Brand Gradient */
--primary-gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
--primary-purple: #667eea;
--primary-deep-purple: #764ba2;
```

#### Semantic Colors
```css
/* Success - Positive actions, confirmations */
--success-500: #10b981;    /* Primary */
--success-600: #059669;    /* Hover */
--success-100: #d1fae5;    /* Background */
--success-800: #065f46;    /* Text on light */

/* Warning - Attention, pending states */
--warning-500: #f59e0b;    /* Primary */
--warning-600: #d97706;    /* Hover */
--warning-100: #fef3c7;    /* Background */
--warning-800: #92400e;    /* Text on light */

/* Error - Danger, destructive actions */
--error-500: #ef4444;      /* Primary */
--error-600: #dc2626;      /* Hover */
--error-100: #fee2e2;      /* Background */
--error-800: #991b1b;      /* Text on light */

/* Info - Informational, links */
--info-500: #3b82f6;       /* Primary */
--info-600: #2563eb;       /* Hover */
--info-100: #dbeafe;       /* Background */
--info-800: #1e40af;       /* Text on light */
```

#### Neutral Colors
```css
--neutral-900: #111827;    /* Dark backgrounds, text */
--neutral-800: #1f2937;    /* Sidebar backgrounds */
--neutral-700: #374151;    /* Secondary text */
--neutral-600: #4b5563;    /* Muted text */
--neutral-500: #6b7280;    /* Placeholder text */
--neutral-400: #9ca3af;    /* Disabled text */
--neutral-300: #d1d5db;    /* Borders */
--neutral-200: #e5e7eb;    /* Light borders */
--neutral-100: #f3f4f6;    /* Light backgrounds */
--neutral-50: #f9fafb;     /* Page backgrounds */
```

#### Data Visualization Colors
```css
/* Chart colors - use in sequence */
--chart-blue: #3b82f6;     /* Primary metric */
--chart-green: #10b981;    /* Positive indicator */
--chart-amber: #f59e0b;    /* Warning indicator */
--chart-red: #ef4444;      /* Negative indicator */
--chart-violet: #8b5cf6;   /* Secondary metric */
--chart-pink: #ec4899;     /* Tertiary metric */
```

#### Domain-Specific Colors
```css
/* Collection Type Indicators */
--trash-color: #22c55e;      /* Green */
--recycling-color: #3b82f6;  /* Blue */
--green-waste-color: #84cc16; /* Lime */
```

### Typography

#### Font Stacks
```css
/* System font stack - fast loading, native feel */
--font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto',
             'Oxygen', 'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans',
             'Helvetica Neue', sans-serif;

/* Monospace for code */
--font-mono: source-code-pro, Menlo, Monaco, Consolas, 'Courier New', monospace;
```

#### Type Scale
```css
--text-xs: 0.75rem;      /* 12px - Badges, labels */
--text-sm: 0.875rem;     /* 14px - Body small */
--text-base: 1rem;       /* 16px - Body text */
--text-lg: 1.125rem;     /* 18px - Card titles */
--text-xl: 1.25rem;      /* 20px - Section headers */
--text-2xl: 1.5rem;      /* 24px - Page headers */
--text-3xl: 1.875rem;    /* 30px - Hero subheads */
--text-4xl: 2.5rem;      /* 40px - Hero headlines */
```

#### Font Weights
```css
--font-normal: 400;
--font-medium: 500;
--font-semibold: 600;
--font-bold: 700;
```

### Spacing Scale
```css
--space-1: 4px;
--space-2: 8px;
--space-3: 12px;
--space-4: 16px;
--space-5: 20px;
--space-6: 24px;
--space-8: 32px;
--space-10: 40px;
--space-12: 48px;
```

### Border Radius
```css
--radius-sm: 6px;
--radius-md: 8px;
--radius-lg: 12px;
--radius-full: 9999px;   /* Pills, avatars */
```

### Shadows
```css
--shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
--shadow-md: 0 4px 15px rgba(0, 0, 0, 0.1);
--shadow-lg: 0 10px 30px rgba(0, 0, 0, 0.2);
--shadow-hover: 0 6px 20px rgba(0, 0, 0, 0.15);
```

---

## 3. What's Working Well

### Architecture Patterns

| Pattern | Location | Benefit |
|---------|----------|---------|
| Repository Pattern | `app/repositories.py` | Clean data access, testable |
| Service Layer | `app/services.py` | Business logic isolation |
| Schema Validation | `app/schemas.py` | Type-safe API contracts |
| Middleware Stack | `app/middleware.py` | Cross-cutting concerns |

### Caching Strategy

| Layer | File | Purpose |
|-------|------|---------|
| In-Memory | `app/cache.py` | Hot data, fastest access |
| Redis | `app/redis_cache.py` | Distributed, persistent |
| AI Results | `app/ai_cache.py` | Expensive LLM calls |

### Security Implementation

- **18 malicious patterns** checked on every input
- **4 validation layers**: Pydantic → Security validators → Regex → Middleware
- **API key system** with scopes, expiration, per-key rate limits
- **Security headers** via Nginx (HSTS, X-Frame-Options, etc.)

### Mobile-First API Design

- Mobile endpoints return **<500 bytes**
- Dedicated rate limiters for mobile clients
- Optimized payload structures
- Separate `/mobile/lookup` and `/mobile/daily-schedule` endpoints

### Gamification System

| Feature | Value | Impact |
|---------|-------|--------|
| Report Points | 10 pts | Basic engagement |
| Verified Points | 50 pts | Quality incentive |
| Badges | Multiple tiers | Achievement system |
| Leaderboards | Public | Competition |

### Lessons Learned

| Lesson | What Happened | Recommendation |
|--------|---------------|----------------|
| Start with migrations | Avoided painful schema changes | Use Alembic from day 1 |
| GraphQL as secondary | REST is simpler for most cases | GraphQL only for complex queries |
| Mobile-specific endpoints | Huge performance gains | Design mobile-first always |
| Crowdsource validation | Community data needs verification | 75% consensus threshold |
| City-specific parsers | Each municipality is unique | Modular parser architecture |

---

## 4. Design DNA & Visual Elements

### The "Radness" Factor

What makes TrashAlert feel on-brand for TombStone Dash LLC:

1. **Gradient Energy**
   - Purple gradient (#667eea → #764ba2) creates immediate visual impact
   - Applied to hero sections, primary buttons, loading states

2. **Generous Whitespace**
   - Cards with 24px padding
   - 12px border-radius feels premium
   - Breathable layouts

3. **Hover Interactions**
   - Subtle transforms (-2px to -5px on Y-axis)
   - Shadow intensification on hover
   - No jarring movements

4. **Color-Coded Semantics**
   - Every color has meaning
   - Green = success, Amber = warning, Red = error, Blue = info
   - Users learn the language

5. **System Fonts**
   - Fast, native feel
   - No font-loading jank
   - Consistent across platforms

6. **Mobile-First Thinking**
   - Everything works on small screens
   - Touch-friendly targets
   - Responsive grids

### Component Patterns

#### Card Component
```css
.card {
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
  border: 1px solid #e5e7eb;
  transition: transform 0.2s, box-shadow 0.2s;
}

.card:hover {
  transform: translateY(-5px);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.15);
}
```

#### Primary Button
```css
.btn-primary {
  padding: 12px 24px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}

.btn-primary:hover {
  transform: translateY(-2px);
  box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
}
```

#### Input Fields
```css
.input {
  width: 100%;
  padding: 12px 16px;
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  font-size: 16px;
  transition: border-color 0.3s;
}

.input:focus {
  outline: none;
  border-color: #667eea;
}
```

#### Status Badges
```css
.badge {
  display: inline-flex;
  padding: 4px 12px;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 600;
}

.badge-official   { background: #dbeafe; color: #1e40af; }
.badge-verified   { background: #dcfce7; color: #166534; }
.badge-unverified { background: #fef3c7; color: #92400e; }
.badge-unknown    { background: #f3f4f6; color: #6b7280; }
```

---

## 5. Technical Patterns

### Project Structure
```
app/
├── main.py              # FastAPI app + core routes
├── routers/
│   ├── auth.py          # /auth/* endpoints
│   └── admin.py         # /admin/* endpoints
├── models.py            # SQLAlchemy ORM models
├── schemas.py           # Pydantic request/response schemas
├── database.py          # DB session management
├── repositories.py      # Data access layer
├── services.py          # Business logic layer
├── auth.py              # JWT auth utilities
├── security.py          # Input validation, security headers
├── middleware.py        # Request logging, API key auth
├── cache.py             # In-memory caching
├── redis_cache.py       # Redis caching
└── utils.py             # Shared helper functions
```

### Authentication Pattern

```python
# JWT Configuration
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7
ALGORITHM = "HS256"

# User Roles
class UserRole(str, enum.Enum):
    USER = "user"
    REPORTER = "reporter"
    ADMIN = "admin"
    CITY_PARTNER = "city_partner"
```

### Database Model Pattern

```python
class BaseModel(Base):
    __abstract__ = True
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### Error Response Pattern

```json
{
  "error": "ValidationError",
  "message": "Human-readable message",
  "path": "/endpoint/path",
  "details": [
    {"field": "email", "message": "Invalid email format"}
  ]
}
```

### API Endpoint Structure

| Category | Endpoints | Auth |
|----------|-----------|------|
| Public | `/lookup`, `/stats`, `/leaderboard` | None |
| User | `/report`, `/subscriptions` | JWT |
| Admin | `/admin/*`, `/analytics/*` | JWT + Admin role |
| Mobile | `/mobile/lookup`, `/mobile/daily-schedule` | Optional API key |
| GraphQL | `/graphql` | Optional |

### CI/CD Workflow Pattern

```yaml
# .github/workflows/ci.yml
jobs:
  test-api:      # pytest with PostgreSQL
  test-frontend: # npm test + build
  lint:          # black, flake8, isort, mypy
  security:      # Trivy vulnerability scan

# .github/workflows/deploy-api.yml
on:
  push:
    branches: [main]
    paths: ['app/**', 'requirements.txt', 'Dockerfile']
steps:
  - Deploy to Railway
  - Run migrations
  - Health check
```

---

## 6. Recommendations for Sister Projects

### Suggested Primary Colors

| Project | Primary | Dark | Gradient |
|---------|---------|------|----------|
| **TrashAlert** | `#667eea` | `#764ba2` | Purple energy |
| **BluePlanet** | `#0ea5e9` | `#0284c7` | Ocean blue |
| **CastAlert** | `#f97316` | `#ea580c` | Broadcast orange |

### Replicable Patterns

**Must Copy:**
- FastAPI + PostgreSQL + Redis stack
- JWT authentication pattern
- Repository/Service layer architecture
- Input validation (security.py)
- Alembic migrations from day 1
- CI/CD workflow structure

**Adapt (Don't Copy Exactly):**
- Gamification point values
- Consensus thresholds
- Domain-specific parsers

### Shareable Packages to Extract

| Package | Contents | Priority |
|---------|----------|----------|
| `@tombstone-dash/auth` | JWT utilities, password hashing, roles | High |
| `@tombstone-dash/security` | Input validation, XSS/SQL prevention | High |
| `@tombstone-dash/ui` | React components (Card, Button, Badge) | Medium |
| `@tombstone-dash/api-client` | Axios wrapper with interceptors | Medium |
| `@tombstone-dash/rate-limiter` | Redis-based rate limiting | Low |

### Mistakes to Avoid

| Mistake | Risk | Prevention |
|---------|------|------------|
| No rate limiting | DDoS, abuse | Implement from day 1 |
| Inline SQL | SQL injection | Always use ORM |
| Plaintext passwords | Data breach | Use bcrypt only |
| No input validation | XSS, injection | Copy security.py |
| Hardcoded secrets | Credential leak | Use env variables |
| No health checks | Silent failures | Add /health endpoint |
| Sync file I/O | Blocks event loop | Use async operations |
| No request logging | Can't debug prod | Add middleware logging |

### Cross-Project Integration Ideas

1. **Shared Auth Service** - SSO across TombStone Dash properties
2. **Analytics Dashboard** - Aggregate metrics from all properties
3. **Notification Service** - Shared Twilio/SendGrid infrastructure
4. **Status Page** - Unified uptime monitoring

---

## 7. Boundaries to Respect

### Unique to TrashAlert (Don't Replicate)

| Component | Location | Why It's Unique |
|-----------|----------|-----------------|
| Crowdsourcing Consensus | `app/services.py` | 75% threshold specific to trash verification |
| Schedule Parsers | `scripts/data_collection/schedule_parsers/` | City-specific implementations |
| Zone Geofencing | `app/zone_locator.py` | Trash collection zones only |
| Gamification Weights | `app/gamification.py` | Calibrated for trash reporting |

### Recent Work to Preserve

| Feature | PR | Status |
|---------|-----|--------|
| Notification System | #65 | Complete, production-ready |
| GPS Truck Tracking | #63 | Real-time fleet tracking |
| Gamification Module | #59 | Points, badges, leaderboards |
| ML Predictions | #61 | Schedule prediction models |
| Multi-Agent Validation | #62 | AI validation pipeline |
| Load Testing Suite | #64 | Performance benchmarks |

### TrashAlert's Distinct Identity

| Aspect | TrashAlert |
|--------|------------|
| Mission | Simplify trash day lookup for communities |
| Primary Users | Residents, municipal partners |
| Value Prop | Never miss trash day again |
| Visual Identity | Purple gradient, green success states |
| Domain Emoji | 🗑️ |
| Focus Area | Municipal services, civic data |

---

## 8. File Reference Guide

### Core Architecture
| File | Lines | Purpose |
|------|-------|---------|
| `app/main.py` | 2,993 | Core API routes, error handlers |
| `app/models.py` | 756 | SQLAlchemy database models |
| `app/schemas.py` | ~400 | Pydantic validation schemas |
| `app/auth.py` | 343 | JWT authentication |
| `app/security.py` | 411 | Input validation, security |
| `app/repositories.py` | 472 | Data access layer |
| `app/services.py` | 388 | Business logic |

### Design Sources
| File | Purpose |
|------|---------|
| `frontend/index.html` | Original frontend with all CSS |
| `frontend/admin-dashboard/src/index.css` | Admin global styles |
| `frontend/admin-dashboard/tailwind.config.js` | Tailwind configuration |
| `website/src/css/custom.css` | Docusaurus theme colors |

### Deployment Configs
| File | Platform |
|------|----------|
| `railway.toml` | Railway backend deployment |
| `docker-compose.yaml` | Full stack orchestration |
| `.github/workflows/ci.yml` | Test pipeline |
| `.github/workflows/deploy-api.yml` | Backend deployment |
| `.github/workflows/deploy-frontend.yml` | Frontend deployment |

### Key Component Files
| Component | File |
|-----------|------|
| Dashboard Layout | `frontend/admin-dashboard/src/components/Layout/DashboardLayout.jsx` |
| Auth Context | `frontend/admin-dashboard/src/context/AuthContext.jsx` |
| API Service | `frontend/admin-dashboard/src/services/api.js` |
| Dashboard Page | `frontend/admin-dashboard/src/pages/Dashboard.jsx` |
| Heatmap Page | `frontend/admin-dashboard/src/pages/Heatmap.jsx` |

---

## Summary

TrashAlert is a mature, production-ready application with:
- **Solid technical foundation** (FastAPI, PostgreSQL, Redis, React)
- **Consistent design language** (purple gradient, semantic colors, generous spacing)
- **Replicable patterns** (auth, security, caching, CI/CD)
- **Clear boundaries** (domain-specific logic stays unique)

Use this document as the foundation for building BluePlanet, CastAlert, and other TombStone Dash properties while maintaining each project's distinct identity.

---

*Document generated from TrashAlert codebase analysis*
*For TombStone Dash LLC internal use*

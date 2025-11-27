# TombStone Dash LLC - Cross-Domain Design Standards Guide
## Based on TrashAlert Analysis

*Generated: November 2025*
*Project Analyzed: TrashAlert*
*Purpose: Multi-domain strategy foundation for BluePlanet, CastAlert, and other TombStone Dash properties*

---

## Executive Summary

TrashAlert is a production-ready, full-stack application that demonstrates mature architectural patterns, security practices, and design consistency. This document extracts the "DNA" of TrashAlert to inform development of sister properties while maintaining each project's distinct identity.

---

## 1. Current State Assessment

### Tech Stack Overview

| Layer | Technology | Version | Notes |
|-------|------------|---------|-------|
| **Backend Framework** | FastAPI | 0.109.0 | Modern async Python, excellent for APIs |
| **Server** | Uvicorn | 4 workers | Production-ready ASGI server |
| **Database** | PostgreSQL | 16 | Production; SQLite for dev |
| **ORM** | SQLAlchemy | 2.0.25 | With Alembic migrations |
| **Cache** | Redis | 7-alpine | Sessions, queues, caching |
| **Frontend (Admin)** | React | 19.2.0 | With Vite 7.2.2 |
| **Frontend (Docs)** | Docusaurus | 3.9.2 | Documentation site |
| **Styling** | Tailwind CSS | 3.4.18 | Utility-first CSS |
| **Maps** | Leaflet | 1.9.4 | With React-Leaflet |
| **Charts** | Recharts | 3.4.1 | React charting library |
| **Authentication** | JWT | HS256 | 30-min access, 7-day refresh |
| **SMS/Email** | Twilio/SendGrid | Latest | Notification services |
| **AI/ML** | OpenAI, Claude | Latest | Address interpretation, classification |
| **Geospatial** | GeoPandas, Shapely | 0.14.0, 2.0.0+ | Zone detection, GIS operations |

### What's Working Well (Replicate Across Domains)

1. **Repository Pattern** (`app/repositories.py`)
   - Clean data access layer
   - Separation of concerns
   - Easy to test and maintain

2. **Service Layer Architecture** (`app/services.py`)
   - Business logic isolated from API routes
   - Reusable across different endpoints

3. **Multi-level Caching Strategy**
   - In-memory cache (`app/cache.py`)
   - Redis cache (`app/redis_cache.py`)
   - AI result caching (`app/ai_cache.py`)

4. **Comprehensive Security**
   - 18 malicious pattern checks
   - Input sanitization at 4 levels
   - API key with scopes and rate limiting
   - Security headers via Nginx

5. **Mobile-First API Design**
   - Compact payloads (<500 bytes)
   - Mobile-specific rate limiters
   - Optimized endpoints for low-bandwidth

6. **Gamification System** (`app/gamification.py`)
   - Points, badges, leaderboards
   - Engagement without complexity

### Lessons Learned

| Lesson | Impact | Recommendation |
|--------|--------|----------------|
| Start with migrations early | Avoided painful schema changes | Use Alembic from day 1 |
| GraphQL as secondary | REST is simpler for most use cases | GraphQL for complex queries only |
| Mobile-specific endpoints | Huge performance gains | Design mobile-first always |
| Crowdsourcing validation | Community data needs verification | 75% consensus threshold works well |
| City-specific parsers | Each municipality is unique | Modular parser architecture |

---

## 2. Design DNA

### Core Color Palette

#### Primary Brand Colors (TrashAlert)
```css
/* Hero Gradient - Defines the brand energy */
--primary-gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
--primary-purple: #667eea;
--primary-deep: #764ba2;
```

#### Semantic Colors (Universal Across All Domains)
```css
/* Success/Positive Actions */
--success-primary: #10b981;     /* Emerald */
--success-hover: #059669;
--success-light: #d1fae5;
--success-dark: #065f46;

/* Warning/Attention */
--warning-primary: #f59e0b;     /* Amber */
--warning-hover: #d97706;
--warning-light: #fef3c7;
--warning-dark: #92400e;

/* Error/Danger */
--error-primary: #ef4444;       /* Red */
--error-hover: #dc2626;
--error-light: #fee2e2;
--error-dark: #991b1b;

/* Info/Neutral */
--info-primary: #3b82f6;        /* Blue */
--info-hover: #2563eb;
--info-light: #dbeafe;
--info-dark: #1e40af;

/* Neutrals */
--neutral-900: #111827;         /* Dark backgrounds */
--neutral-800: #1f2937;         /* Sidebar hover */
--neutral-700: #374151;
--neutral-600: #4b5563;
--neutral-500: #6b7280;         /* Muted text */
--neutral-400: #9ca3af;
--neutral-300: #d1d5db;
--neutral-200: #e5e7eb;         /* Borders */
--neutral-100: #f3f4f6;         /* Light backgrounds */
--neutral-50: #f9fafb;          /* Page backgrounds */
```

#### Data Visualization Palette
```css
/* Chart/Graph Colors - Use in sequence */
--chart-1: #3b82f6;   /* Blue - Primary metric */
--chart-2: #10b981;   /* Green - Positive indicator */
--chart-3: #f59e0b;   /* Amber - Warning/Attention */
--chart-4: #ef4444;   /* Red - Negative indicator */
--chart-5: #8b5cf6;   /* Violet - Secondary metric */
--chart-6: #ec4899;   /* Pink - Tertiary metric */
```

### Typography System

```css
/* System Font Stack - Fast loading, native feel */
--font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto',
             'Oxygen', 'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans',
             'Helvetica Neue', sans-serif;

/* Code Font Stack */
--font-mono: source-code-pro, Menlo, Monaco, Consolas, 'Courier New', monospace;

/* Type Scale */
--text-xs: 0.75rem;     /* 12px - Badges, small labels */
--text-sm: 0.875rem;    /* 14px - Body small, captions */
--text-base: 1rem;      /* 16px - Body text */
--text-lg: 1.125rem;    /* 18px - Lead text, card titles */
--text-xl: 1.25rem;     /* 20px - Section headers */
--text-2xl: 1.5rem;     /* 24px - Page headers */
--text-3xl: 1.875rem;   /* 30px - Hero subheads */
--text-4xl: 2.5rem;     /* 40px - Hero headlines */

/* Font Weights */
--font-normal: 400;
--font-medium: 500;
--font-semibold: 600;
--font-bold: 700;
```

### Component Patterns

#### Card Component
```css
/* Standard Card */
.card {
  background: white;
  border-radius: 12px;          /* Consistent roundness */
  padding: 24px;                /* Comfortable spacing */
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
  border: 1px solid #e5e7eb;
  transition: transform 0.2s, box-shadow 0.2s;
}

.card:hover {
  transform: translateY(-5px);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.15);
}
```

#### Button Patterns
```css
/* Primary Button */
.btn-primary {
  padding: 12px 24px;
  background: var(--primary-gradient);
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

/* Success/Action Button */
.btn-success {
  background: #10b981;
}

.btn-success:hover {
  background: #059669;
}

/* Warning/Toggle Button */
.btn-warning {
  background: #f59e0b;
}

.btn-warning:hover {
  background: #d97706;
}
```

#### Input/Form Patterns
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
  border-color: var(--primary-purple);
}
```

#### Badge/Status Indicators
```css
/* Status Badges - Color-coded semantic meaning */
.badge {
  display: inline-flex;
  padding: 4px 12px;
  border-radius: 9999px;        /* Pill shape */
  font-size: 0.75rem;
  font-weight: 600;
}

.badge-official   { background: #dbeafe; color: #1e40af; }
.badge-verified   { background: #dcfce7; color: #166534; }
.badge-unverified { background: #fef3c7; color: #92400e; }
.badge-unknown    { background: #f3f4f6; color: #6b7280; }
```

### Layout Patterns

```css
/* Container Max Widths */
--container-sm: 640px;
--container-md: 768px;
--container-lg: 1024px;
--container-xl: 1280px;

/* Spacing Scale */
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

### The "Radness" Factor

What makes TrashAlert feel on-brand for TombStone Dash LLC:

1. **Gradient Energy** - The purple gradient (#667eea → #764ba2) creates immediate visual impact
2. **Generous Whitespace** - Cards with 24px padding, 12px border-radius feel premium
3. **Hover Interactions** - Subtle transforms (-2px to -5px) add life without distraction
4. **Color-Coded Semantics** - Every color has meaning (green=success, amber=warning, etc.)
5. **System Fonts** - Fast, native feel without font-loading jank
6. **Mobile-First Thinking** - Everything works on small screens

---

## 3. Technical Patterns

### API Structure (Replicate This)

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
└── utils.py             # Shared helper functions
```

### Authentication Pattern

```python
# JWT Configuration (from app/auth.py)
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
# Base model with common fields (from app/models.py)
class BaseModel(Base):
    __abstract__ = True
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### Error Response Pattern

```python
# Consistent error format (from app/main.py)
{
    "error": "ValidationError",
    "message": "Human-readable message",
    "path": "/endpoint/path",
    "details": [...]  # Field-level errors when applicable
}
```

### Deployment Pattern

| Service | Platform | Config File |
|---------|----------|-------------|
| Backend API | Railway | `railway.toml` |
| Admin Dashboard | Vercel | Vercel config |
| Documentation | Vercel | Docusaurus |
| Database | Railway PostgreSQL | Environment vars |
| Cache | Railway Redis | Environment vars |

### CI/CD Workflows

```yaml
# Standard workflow structure (.github/workflows/)
- ci.yml:         Test API + Frontend + Lint + Security scan
- deploy-api.yml: Deploy backend to Railway on main push
- deploy-frontend.yml: Deploy admin to Vercel on main push
- deploy-docs.yml: Deploy documentation site
```

### Shareable Packages (Extract These)

1. **@tombstone-dash/auth** - JWT utilities, password hashing, role management
2. **@tombstone-dash/security** - Input validation, XSS/SQL injection prevention
3. **@tombstone-dash/ui** - React components (Card, Button, Badge, Input, etc.)
4. **@tombstone-dash/api-client** - Axios wrapper with interceptors
5. **@tombstone-dash/rate-limiter** - Redis-based rate limiting utilities

---

## 4. Recommendations for Sister Projects

### For BluePlanet (Fresh Build)

**Do:**
- Use the same FastAPI + PostgreSQL + Redis stack
- Copy the authentication pattern exactly
- Use the shared color palette (but define a BluePlanet primary color)
- Start with Alembic migrations from day 1
- Implement the repository/service layer architecture
- Use Tailwind CSS for styling
- Set up CI/CD workflows immediately

**BluePlanet Suggested Primary Colors:**
```css
/* Ocean/Planet Theme */
--bp-primary-gradient: linear-gradient(135deg, #0ea5e9 0%, #0284c7 100%);
--bp-primary: #0ea5e9;       /* Sky blue */
--bp-primary-dark: #0284c7;  /* Ocean blue */
```

**Don't:**
- Skip input validation - copy TrashAlert's security.py wholesale
- Build custom auth - use the existing JWT pattern
- Use SQLite in production - PostgreSQL only
- Forget mobile endpoints - design for mobile first

### For CastAlert

**Suggested Primary Colors:**
```css
/* Alert/Broadcast Theme */
--ca-primary-gradient: linear-gradient(135deg, #f97316 0%, #ea580c 100%);
--ca-primary: #f97316;       /* Bright orange */
--ca-primary-dark: #ea580c;  /* Deep orange */
```

### Cross-Project Integrations (Without Consolidating)

1. **Shared Auth Service** (Optional Future)
   - Single sign-on across TombStone Dash properties
   - Each project maintains its own user data
   - Central identity, decentralized data

2. **Analytics Dashboard**
   - Aggregate metrics from all properties
   - Each project pushes to shared analytics
   - No data mixing, just aggregation

3. **Notification Service**
   - Shared Twilio/SendGrid credentials
   - Each project calls shared API
   - Templates unique to each domain

4. **Status Page**
   - Unified uptime monitoring
   - BetterStack or Uptime Kuma
   - Public status for all properties

### Mistakes to Avoid

| Mistake | Why It Hurts | Prevention |
|---------|--------------|------------|
| No rate limiting | DDoS vulnerability, abuse | Implement from day 1 |
| Inline SQL | SQL injection risk | Always use ORM |
| Storing plaintext passwords | Security breach | Use bcrypt, never custom hashing |
| No input validation | XSS, injection attacks | Copy security.py patterns |
| Hardcoded secrets | Leaked credentials | Use environment variables |
| No health checks | Silent failures | Add /health endpoint |
| Synchronous file I/O | Blocks async event loop | Use async file operations |
| No request logging | Can't debug production | Add middleware logging |

---

## 5. Boundaries to Respect

### Unique to TrashAlert (Don't Replicate)

1. **Crowdsourcing Consensus Algorithm**
   - 75% threshold is specific to trash schedule verification
   - Other projects may need different validation logic

2. **City-Specific Schedule Parsers**
   - `/scripts/data_collection/schedule_parsers/`
   - Highly domain-specific, not reusable

3. **Zone/Geofencing Logic**
   - Trash collection zones are unique use case
   - Shapefile processing specific to this domain

4. **Gamification Weights**
   - 10 points per report, 50 per verified
   - Calibrated for trash reporting engagement

### Recent Work to Preserve

Based on recent commits:
- **Notification System** (PR #65) - Complete, tested, production-ready
- **GPS Truck Tracking** (PR #63) - Real-time fleet tracking
- **Gamification Module** (PR #59) - Points, badges, leaderboards
- **Prediction Module** (PR #61) - ML-based schedule predictions
- **Multi-Agent Validation** (PR #62) - AI validation pipeline
- **Load Testing Suite** (PR #64) - Performance benchmarks

### TrashAlert's Distinct Identity

| Aspect | TrashAlert Identity |
|--------|---------------------|
| **Mission** | Simplify trash day lookup for communities |
| **Primary Users** | Residents, municipal partners |
| **Core Value Prop** | Never miss trash day again |
| **Visual Identity** | Purple gradient, green success states |
| **Emoji** | 🗑️ (Trash can) |
| **Domain Focus** | Municipal services, crowdsourced civic data |

---

## File References

### Key Architecture Files
- `app/main.py:1-2993` - Core API routes and error handlers
- `app/models.py:1-756` - Database models
- `app/auth.py:1-343` - JWT authentication
- `app/security.py:1-411` - Input validation and security
- `app/repositories.py:1-472` - Data access layer
- `app/services.py:1-388` - Business logic

### Design Token Sources
- `frontend/index.html:1-892` - Original frontend with all CSS
- `frontend/admin-dashboard/src/index.css:1-17` - Global styles
- `frontend/admin-dashboard/tailwind.config.js` - Tailwind config
- `website/src/css/custom.css:1-30` - Docusaurus theme

### Deployment Configs
- `railway.toml` - Railway deployment
- `docker-compose.yaml` - Full stack orchestration
- `.github/workflows/` - CI/CD pipelines

---

## Next Steps

1. **Create Shared UI Package**
   - Extract Button, Card, Badge, Input components
   - Publish to private npm registry

2. **Create Auth Package**
   - Extract JWT utilities, password hashing
   - Standardize across all projects

3. **Create Security Package**
   - Extract input validation, security headers
   - Mandatory for all TombStone Dash projects

4. **Define Per-Project Primary Colors**
   - TrashAlert: Purple (#667eea → #764ba2)
   - BluePlanet: Sky Blue (#0ea5e9 → #0284c7)
   - CastAlert: Orange (#f97316 → #ea580c)

5. **Set Up Monorepo (Optional)**
   - Shared packages in one repo
   - Per-project apps in separate repos
   - Or full monorepo with Turborepo/Nx

---

*This document serves as the foundation for TombStone Dash LLC's cross-domain design standards. Each project should maintain its distinct identity while adhering to the shared technical patterns, color semantics, and quality standards documented here.*

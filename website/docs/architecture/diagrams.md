---
sidebar_position: 4
title: System Diagrams
slug: /architecture/diagrams
---

# System Architecture Diagrams

Visual representations of TrashAlert's data flow, components, and interactions.

## Data Flow Diagram

### Address Lookup Flow

```mermaid
graph TD
    A["👤 User"] -->|"GET /lookup?address=..."| B["🌐 Nginx<br/>Reverse Proxy"]
    B -->|"Rate limit check"| C["✅ Allowed?"]
    C -->|"No"| D["429 Too Many<br/>Requests"]
    C -->|"Yes"| E["🚀 FastAPI<br/>Request Handler"]

    E -->|"Parse & Validate"| F["📋 Normalize<br/>Address"]
    F -->|"Search DB"| G[("🗄️ Database<br/>Queries")]

    G -->|"Get Address"| H["📍 Address<br/>Record"]
    G -->|"Get Reports"| I["📊 Consensus<br/>Calculation"]

    I -->|"≥3 reports &<br/>≥67% agreement?"| J{"Verified?"}
    J -->|"Yes"| K["✓ CROWD_VERIFIED"]
    J -->|"No"| L["Official data?"]
    L -->|"Yes"| M["📜 OFFICIAL"]
    L -->|"No"| N["CROWD_UNVERIFIED<br/>or UNKNOWN"]

    K --> O["📦 Build<br/>Response"]
    M --> O
    N --> O

    O -->|"200 OK + JSON"| A

    style A fill:#e1f5ff
    style B fill:#fff3e0
    style E fill:#f3e5f5
    style G fill:#e8f5e9
    style O fill:#fce4ec
```

### Report Submission Flow

```mermaid
graph TD
    A["👤 User Submits<br/>Report"] -->|"POST /report<br/>JSON"| B["🌐 Nginx<br/>Reverse Proxy"]

    B -->|"Rate limit<br/>check"| C{"Allowed?"}
    C -->|"No"| D["❌ 429<br/>Rate Limited"]
    C -->|"Yes"| E["✅ Accepted"]

    E -->|"Validate<br/>request"| F["📋 Parse<br/>Address & Days"]

    F -->|"Find or<br/>create"| G[("🗄️ Address<br/>Lookup")]

    G -->|"Address<br/>record"| H["💾 Insert<br/>Report"]

    H -->|"New report<br/>added"| I["🔄 Recalculate<br/>Consensus"]

    I -->|"Query all<br/>reports"| J["📊 Calculate<br/>Mode"]
    J -->|"Compute<br/>agreement"| K["📈 Check<br/>Verification"]

    K -->|"≥3 & ≥67%?"| L{"Verified?"}
    L -->|"Yes"| M["✓ is_verified<br/>= true"]
    L -->|"No"| N["❌ is_verified<br/>= false"]

    M --> O["📦 Response:<br/>Success +<br/>Consensus"]
    N --> O

    O -->|"200 OK"| A

    style A fill:#e1f5ff
    style H fill:#fff3e0
    style I fill:#f3e5f5
    style K fill:#e8f5e9
    style O fill:#fce4ec
```

## System Component Diagram

```mermaid
graph LR
    subgraph Client["Client Layer"]
        Web["🌐 Web App<br/>React"]
        Mobile["📱 Mobile<br/>React Native"]
        Admin["🔧 Admin<br/>Dashboard"]
    end

    subgraph Gateway["Gateway Layer"]
        Nginx["🔒 Nginx<br/>SSL/TLS<br/>Rate Limiting<br/>Load Balancing"]
    end

    subgraph API["API Layer"]
        FastAPI["🚀 FastAPI<br/>Application"]
        Routes["📍 Routes<br/>/lookup<br/>/report<br/>/interpret<br/>/stats"]
    end

    subgraph Business["Business Logic"]
        AddressLogic["📍 Address<br/>Lookup"]
        ConsensusLogic["📊 Consensus<br/>Calculation"]
        ValidationLogic["✅ Validation"]
        AILogic["🤖 AI<br/>Interpreter"]
    end

    subgraph Data["Data Layer"]
        SQLAlchemy["🔗 SQLAlchemy<br/>ORM"]
        Cache["⚡ Redis<br/>Cache"]
    end

    subgraph Database["Database"]
        Postgres["🗄️ PostgreSQL<br/>Primary Data<br/>PostGIS for<br/>Geospatial"]
        SQLite["💾 SQLite<br/>Dev/Light"]
    end

    Client -->|HTTP/S| Nginx
    Nginx -->|Route| FastAPI
    FastAPI --> Routes
    Routes --> AddressLogic
    Routes --> ConsensusLogic
    Routes --> ValidationLogic
    Routes --> AILogic

    AddressLogic --> SQLAlchemy
    ConsensusLogic --> SQLAlchemy
    ValidationLogic --> SQLAlchemy

    SQLAlchemy -->|Query| Cache
    Cache -->|Hit| Data
    Cache -->|Miss| Postgres
    SQLAlchemy -->|Query| Postgres
    SQLAlchemy -->|Dev| SQLite

    style Client fill:#e3f2fd
    style Gateway fill:#fff3e0
    style API fill:#f3e5f5
    style Business fill:#e8f5e9
    style Data fill:#fce4ec
    style Database fill:#ede7f6
```

## Data Model Diagram

```mermaid
erDiagram
    CITIES ||--o{ ADDRESSES : contains
    CITIES ||--o{ PICKUP_ZONES : defines
    CITIES ||--o{ SCHEDULES : has
    CITIES ||--o{ SCHEDULE_EXCEPTIONS : has

    ADDRESSES ||--o{ CROWD_REPORTS : receives
    ADDRESSES ||--o| CROWD_CONSENSUS : has
    ADDRESSES ||--o| ADDRESS_PICKUP_INFO : has

    PICKUP_ZONES ||--o{ SCHEDULES : contains

    CITIES {
        int id PK
        string name
        string state
        string timezone
        boolean enabled
    }

    ADDRESSES {
        int id PK
        string normalized_address
        string house_number
        string street
        string city_slug FK
        float lat
        float lon
        string official_trash_day
    }

    CROWD_REPORTS {
        int id PK
        int address_id FK
        string trash_day
        string recycling_day
        string green_day
        string user_hash
        timestamp created_at
    }

    CROWD_CONSENSUS {
        int id PK
        int address_id FK
        string consensus_trash_day
        float trash_agreement_ratio
        int total_reports
        boolean is_verified
    }

    PICKUP_ZONES {
        int id PK
        int city_id FK
        string name
    }

    SCHEDULES {
        int id PK
        int city_id FK
        int pickup_zone_id FK
        string trash_day_of_week
    }

    SCHEDULE_EXCEPTIONS {
        int id PK
        int city_id FK
        date exception_date
        string rule_description
    }

    ADDRESS_PICKUP_INFO {
        int id PK
        int address_id FK
        string trash_day_of_week
        string source
    }
```

## Request/Response Cycle

```mermaid
sequenceDiagram
    participant User as User/App
    participant Nginx as Nginx
    participant API as FastAPI
    participant DB as Database
    participant Cache as Cache

    User->>Nginx: GET /lookup?address=...
    Note over Nginx: Check rate limit
    Nginx->>API: Route request

    API->>Cache: Check cache
    alt Cache hit
        Cache-->>API: Cached result
    else Cache miss
        API->>DB: Query address
        DB-->>API: Address record
        API->>DB: Query reports
        DB-->>API: Report data
        API->>API: Calculate consensus
        API->>Cache: Store result
    end

    API->>API: Format response
    API-->>Nginx: JSON response
    Nginx-->>User: HTTP 200 + JSON
```

## Consensus Algorithm Flow

```mermaid
graph TD
    A["📥 New Report<br/>Submitted"] -->|"Address + Days"| B["🔍 Find<br/>Address Record"]

    B -->|"Address ID"| C["📊 Query<br/>All Reports<br/>Last 6 months"]

    C -->|"List of<br/>reports"| D["🔢 Count<br/>Reports by Day"]

    D -->|"Day counts"| E["📈 Find Mode<br/>Most common day"]

    E -->|"Mode day<br/>+ counts"| F["⚖️ Calculate<br/>Agreement Ratio"]

    F -->|"Ratio &<br/>counts"| G{"Check<br/>Verification<br/>≥3 & ≥67%?"}

    G -->|"Yes"| H["✅ is_verified<br/>= true"]
    G -->|"No"| I["❌ is_verified<br/>= false"]

    H -->|"Update<br/>database"| J["💾 Store<br/>Consensus"]
    I -->|"Update<br/>database"| J

    J -->|"New<br/>consensus"| K["🔄 Invalidate<br/>Cache"]

    K -->|"Consensus<br/>data"| L["📦 Return to<br/>User"]

    style A fill:#e1f5ff
    style D fill:#fff3e0
    style G fill:#f3e5f5
    style J fill:#e8f5e9
    style L fill:#fce4ec
```

## Deployment Architecture

### Development

```
┌─────────────────────┐
│  Developer Machine  │
├─────────────────────┤
│ - Python app        │
│ - SQLite database   │
│ - Localhost:8000    │
└─────────────────────┘
```

### Production

```
┌──────────────────────────────────────────────────┐
│          Cloud Infrastructure                     │
├──────────────────────────────────────────────────┤
│                                                  │
│  ┌────────────────────────────────────┐          │
│  │ Load Balancer / DNS                │          │
│  │ (AWS ELB, Azure LB, etc.)          │          │
│  └──────┬─────────────────────┬───────┘          │
│         │                     │                  │
│  ┌──────▼──────┐    ┌────────▼──────┐           │
│  │ API Server 1│    │ API Server 2   │  ...      │
│  │ - FastAPI   │    │ - FastAPI      │           │
│  │ - Nginx     │    │ - Nginx        │           │
│  └──────┬──────┘    └────────┬───────┘           │
│         │                     │                  │
│         └──────────┬──────────┘                  │
│                    │                            │
│         ┌──────────▼──────────┐                 │
│         │  Shared Services    │                 │
│         ├─────────────────────┤                 │
│         │ - PostgreSQL        │                 │
│         │ - Redis Cache       │                 │
│         │ - Monitoring        │                 │
│         │ - Logging           │                 │
│         └─────────────────────┘                 │
│                                                  │
└──────────────────────────────────────────────────┘
```

## Cache Layer Diagram

```mermaid
graph LR
    A["Request"] -->|"Check"| B["Redis<br/>Cache"]
    B -->|"Miss"| C["PostgreSQL<br/>Database"]
    C -->|"Result"| D["Store in<br/>Cache"]
    D -->|"Return"| E["Response"]
    B -->|"Hit"| E

    F["5 min TTL"] -.->|"Invalidate"| B
    G["New Report"] -.->|"Invalidate"| B

    style B fill:#fff3e0
    style C fill:#e8f5e9
```

## Related Documentation

- **[System Architecture](/docs/architecture/overview)** - Component details
- **[Database Schema](/docs/architecture/database)** - Table definitions
- **[Crowdsourcing Logic](/docs/architecture/crowdsourcing)** - Consensus algorithm


# AutoTrader AI - System Architecture

> Enterprise-grade AI-powered trading intelligence platform with explainable recommendations and secure trade execution.

## Table of Contents

1. [Overview](#overview)
2. [Two-Plane Architecture](#two-plane-architecture)
3. [Service Components](#service-components)
4. [Data Flow](#data-flow)
5. [Technology Stack](#technology-stack)
6. [Security Architecture](#security-architecture)
7. [Database Design](#database-design)
8. [API Design](#api-design)
9. [Deployment Architecture](#deployment-architecture)
10. [Observability](#observability)

---

## Overview

AutoTrader AI is a fintech platform that delivers AI-powered trading recommendations with secure trade execution via connected brokerages (e.g., Robinhood). The system is designed following FAANG-grade engineering principles with emphasis on:

- **Security First**: Backend-only brokerage access, encrypted secrets, audit logging
- **Scalability**: Event-driven microservices, horizontal scaling
- **Explainability**: Human-readable AI reasoning for every recommendation
- **Compliance**: Immutable audit logs, 7+ year data retention

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           AutoTrader AI Platform                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │              CONTINUOUS INTELLIGENCE PLANE (Always-On)              │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────┐  │   │
│  │  │   Market    │  │    News     │  │      ML Recommendation      │  │   │
│  │  │    Data     │──│  Sentiment  │──│          Engine             │  │   │
│  │  │  Ingestion  │  │   Analysis  │  │  (Feature Eng + Inference)  │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │              USER INTERACTION & EXECUTION PLANE (Session-Driven)    │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────────┐  ┌───────────────────┐  │   │
│  │  │  Auth   │  │ Config  │  │Recommendation│  │ Trade Execution   │  │   │
│  │  │ Service │  │ Service │  │   Service    │  │     Service       │  │   │
│  │  └─────────┘  └─────────┘  └─────────────┘  └───────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Two-Plane Architecture

The platform is divided into two distinct operational planes, each optimized for different workloads:

### 1. Continuous Intelligence Plane (Always-On)

**Purpose**: Generate AI recommendations continuously, independent of user sessions.

**Characteristics**:
- Event-driven processing via Apache Kafka
- Horizontally scalable workers
- No direct user interaction
- Batch and stream processing

**Components**:
| Component | Technology | Responsibility |
|-----------|------------|----------------|
| Signal Ingestion | Kafka Connectors | Ingest market data, news, social signals |
| Feature Engineering | Python/Flink | Compute technical indicators, sentiment scores |
| Recommendation Engine | Python/FastAPI | Run ML inference, generate BUY/SELL/HOLD |
| Explainability Service | Python/LangChain | Generate human-readable explanations |

**Data Flow**:
```
Market Data APIs ──┐
                   │
News APIs ─────────┼──► Kafka ──► Feature Engineering ──► ML Model ──► PostgreSQL
                   │                                                        │
Social APIs ───────┘                                                        │
                                                                            ▼
                                                               Recommendations Table
```

### 2. User Interaction & Execution Plane (Session-Driven)

**Purpose**: Handle user requests with low latency and execute trades securely.

**Characteristics**:
- Request-response pattern (REST APIs)
- User session management (JWT)
- Strict security boundaries
- Real-time trade execution

**Components**:
| Component | Technology | Port | Responsibility |
|-----------|------------|------|----------------|
| API Gateway | Node.js/Express | 3001 | Route requests, Plaid integration, trade auth |
| Auth Service | Java/Spring Boot | 8081 | Authentication, JWT tokens, OAuth |
| Config Service | Java/Spring Boot | 8082 | User preferences, risk limits |
| Recommendation Service | Java/Spring Boot | 8083 | Serve pre-computed recommendations |
| Trade Execution Service | Java/Spring Boot | 8084 | Validate and execute trades |
| Web App | React/TypeScript | 5173 | User interface |

---

## Service Components

### Backend Microservices (Java/Spring Boot)

#### Auth Service (`services/auth-service/`)
```
Port: 8081
Base Path: /api/v1/auth

Endpoints:
  POST /login          - Authenticate user (Google OAuth or email)
  GET  /session        - Get current session info
  POST /logout         - End session

Responsibilities:
  - User registration and lookup
  - JWT token generation (15-minute expiry)
  - Session validation
  - Brokerage connection status

Dependencies:
  - PostgreSQL (users table)
  - Redis (session cache - future)
```

#### Config Service (`services/config-service/`)
```
Port: 8082
Base Path: /api/v1/config

Endpoints:
  GET  /config         - Get user configuration
  PUT  /config         - Update configuration

Responsibilities:
  - Manage watchlist symbols
  - Risk limits (max position %, daily trade limit)
  - Signal weights (technical vs sentiment)

Dependencies:
  - PostgreSQL (user_configurations table)
```

#### Recommendation Service (`services/recommendation-service/`)
```
Port: 8083
Base Path: /api/v1/recommendations

Endpoints:
  GET /recommendations - Get latest recommendations for user

Responsibilities:
  - Fetch pre-computed recommendations from database
  - Filter by user's watchlist
  - Include explanations

Dependencies:
  - PostgreSQL (recommendations, recommendation_explanations tables)
  - Redis (recommendation cache)
```

#### Trade Execution Service (`services/trade-execution-service/`)
```
Port: 8084
Base Path: /api/v1/trades

Endpoints:
  POST /execute        - Execute a trade
  GET  /{id}           - Get trade status

Responsibilities:
  - Validate against risk limits
  - Idempotency handling
  - Brokerage API integration
  - Audit logging

Dependencies:
  - PostgreSQL (trades, trade_events, audit_logs tables)
  - Vault (brokerage OAuth tokens)
```

### API Gateway (`api-gateway/`)

The Node.js API Gateway serves as the primary backend for the frontend application, handling:

```
Port: 3001
Base Path: /api

Key Routes:
  /api/users/auth           - User authentication with Google
  /api/onboarding/*         - Onboarding flow management
  /api/stocks/search        - Yahoo Finance stock search
  /api/plaid/*              - Plaid Link integration
  /api/brokerage/*          - Brokerage connection management
  /api/trade/*              - Trade authorization flow

Special Features:
  - Plaid integration for brokerage OAuth
  - Short-lived trade authorization tokens (5-minute TTL)
  - PIN verification for trades
  - Vault integration for secure token storage
```

### ML Services (`ml-services/`)

#### Recommendation Engine (`recommendation-engine/`)
```
Port: 8000
Framework: FastAPI

Endpoints:
  GET  /health              - Health check
  POST /recommendations     - Generate recommendations

Responsibilities:
  - Load ML models (scikit-learn, PyTorch)
  - Run inference on feature vectors
  - Generate confidence scores
  - Produce recommendation objects
```

#### Feature Engineering (`feature-engineering/`)
```
Responsibilities:
  - Compute technical indicators (RSI, MACD, Bollinger)
  - Normalize signal data
  - Store features in ClickHouse
  - Real-time feature updates via Kafka
```

#### Explainability Service (`explainability-service/`)
```
Responsibilities:
  - Generate human-readable explanations
  - Use LLM (via LangChain) for natural language
  - Map signal contributions to text
```

### Frontend (`web-app/`)

```
Port: 5173
Framework: React 18 + TypeScript + Vite

Pages:
  /              - Home (landing page with Google Sign-In)
  /onboarding    - Multi-step onboarding wizard
  /dashboard     - Main trading dashboard
  /settings      - User preferences management

Key Components:
  - AuthContext: Global authentication state
  - BrokerageConnect: Plaid Link integration
  - StockSearch: Yahoo Finance search with autocomplete
  - TradeConfirmationModal: Secure trade flow with PIN
  - OnboardingStatusCard: Progress tracking
```

---

## Data Flow

### Authentication Flow
```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  User    │────►│  Google  │────►│ Frontend │────►│   API    │
│          │     │  OAuth   │     │          │     │ Gateway  │
└──────────┘     └──────────┘     └──────────┘     └────┬─────┘
                                                        │
                                                        ▼
                                                  ┌──────────┐
                                                  │PostgreSQL│
                                                  │ (users)  │
                                                  └──────────┘
```

### Recommendation Flow
```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Market  │────►│  Kafka   │────►│ Feature  │────►│    ML    │
│   Data   │     │          │     │   Eng    │     │  Engine  │
└──────────┘     └──────────┘     └──────────┘     └────┬─────┘
                                                        │
                 ┌──────────────────────────────────────┘
                 ▼
           ┌──────────┐     ┌──────────┐     ┌──────────┐
           │PostgreSQL│────►│   Rec    │────►│ Frontend │
           │  (recs)  │     │ Service  │     │          │
           └──────────┘     └──────────┘     └──────────┘
```

### Trade Execution Flow
```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│ Frontend │────►│   API    │────►│  Vault   │────►│Brokerage │
│ (confirm)│     │ Gateway  │     │ (token)  │     │   API    │
└──────────┘     └────┬─────┘     └──────────┘     └──────────┘
                      │
                      ▼
                ┌──────────┐
                │PostgreSQL│
                │(trades,  │
                │ audit)   │
                └──────────┘
```

---

## Technology Stack

### Languages & Frameworks

| Layer | Technology | Version | Purpose |
|-------|------------|---------|---------|
| Frontend | React + TypeScript | 18.x | User interface |
| Frontend | Vite | 5.x | Build tooling |
| Frontend | TailwindCSS | 3.x | Styling |
| Backend | Java + Spring Boot | 17 / 3.2 | Microservices |
| Backend | Node.js + Express | 20.x | API Gateway |
| ML | Python + FastAPI | 3.11 | ML services |
| ML | scikit-learn, PyTorch | Latest | ML models |

### Data Stores

| Store | Technology | Version | Purpose |
|-------|------------|---------|---------|
| Primary DB | PostgreSQL | 15 | Users, trades, configs |
| Analytics DB | ClickHouse | Latest | Time-series features |
| Cache | Redis | 7 | Session cache, hot data |
| Secrets | HashiCorp Vault | 1.15 | OAuth tokens, API keys |

### Infrastructure

| Component | Technology | Purpose |
|-----------|------------|---------|
| Message Queue | Apache Kafka | Event streaming |
| Stream Processing | Apache Flink | Real-time feature computation |
| Container Runtime | Docker | Local development |
| Orchestration | Kubernetes | Production deployment |
| IaC | Terraform | Cloud infrastructure |
| CI/CD | GitHub Actions | Build, test, deploy |

---

## Security Architecture

### Authentication & Authorization

```
┌─────────────────────────────────────────────────────────────┐
│                    Security Layers                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Google OAuth 2.0                                        │
│     └── User identity verification                          │
│                                                             │
│  2. JWT Tokens (15-minute expiry)                          │
│     └── Stateless session management                        │
│     └── HMAC-SHA256 signing                                 │
│                                                             │
│  3. Trade Authorization Tokens (5-minute TTL)              │
│     └── One-time use for trade execution                    │
│     └── Stored in Vault, not database                       │
│                                                             │
│  4. Optional Trade PIN (4-6 digits)                        │
│     └── Additional confirmation step                        │
│     └── Account lockout after 5 failures                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Secrets Management

```
┌──────────────────────────────────────────────────────────────┐
│                    HashiCorp Vault                           │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  secret/autotrader/plaid/{userId}/{itemId}                  │
│  └── Plaid access tokens (brokerage OAuth)                  │
│                                                              │
│  secret/autotrader/trade-auth/{userId}/{tradeId}            │
│  └── Short-lived trade authorization tokens                 │
│                                                              │
│  secret/autotrader/config/*                                 │
│  └── API keys, service credentials                          │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### Security Best Practices

1. **Backend-Only Brokerage Access**: OAuth tokens never sent to frontend
2. **Short Token Lifetimes**: JWT 15 min, trade auth 5 min
3. **Idempotency Keys**: Prevent duplicate trade execution
4. **Audit Logging**: All trade actions logged immutably
5. **HTTPS Only**: All traffic encrypted in transit
6. **UUID Identifiers**: No sequential IDs (prevents enumeration)

---

## Database Design

### PostgreSQL Schema Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         PostgreSQL                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Core Tables:                                                   │
│  ├── users                    (user accounts)                   │
│  ├── user_onboarding          (onboarding progress)             │
│  ├── user_profiles            (display name, phone, etc.)       │
│  ├── user_trading_preferences (risk settings)                   │
│  └── user_configurations      (watchlist, signal weights)       │
│                                                                 │
│  Brokerage:                                                     │
│  ├── user_brokerage_connections (Plaid connections)             │
│  └── user_brokerage_accounts    (individual accounts)           │
│                                                                 │
│  Trading:                                                       │
│  ├── trade_authorizations     (pending/executed trades)         │
│  ├── trade_audit_log          (immutable action log)            │
│  └── user_trade_pins          (optional PIN security)           │
│                                                                 │
│  ML Output:                                                     │
│  ├── recommendations          (AI predictions)                  │
│  └── recommendation_explanations (XAI output)                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Key Relationships

```
users (1) ──────────────────── (1) user_onboarding
  │
  ├── (1) ─────────────────── (1) user_profiles
  │
  ├── (1) ─────────────────── (1) user_trading_preferences
  │
  ├── (1) ─────────────────── (N) user_watchlist
  │
  ├── (1) ─────────────────── (N) user_brokerage_connections
  │                                     │
  │                                     └── (1) ── (N) user_brokerage_accounts
  │
  ├── (1) ─────────────────── (N) trade_authorizations
  │                                     │
  │                                     └── (1) ── (N) trade_audit_log
  │
  └── (1) ─────────────────── (N) recommendations
                                        │
                                        └── (1) ── (1) recommendation_explanations
```

### ClickHouse (Analytics)

```
┌─────────────────────────────────────────────────────────────────┐
│                         ClickHouse                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  symbol_features (time-series)                                  │
│  ├── symbol        String                                       │
│  ├── timestamp     DateTime                                     │
│  ├── price         Float64                                      │
│  ├── volume        UInt64                                       │
│  ├── rsi           Float64                                      │
│  ├── macd          Float64                                      │
│  ├── sentiment     Float64                                      │
│  └── social_score  Float64                                      │
│                                                                 │
│  Optimized for: Time-range queries, aggregations                │
│  Partitioned by: Date                                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## API Design

### RESTful Conventions

| Method | Path Pattern | Action |
|--------|--------------|--------|
| GET | /resources | List all |
| GET | /resources/{id} | Get one |
| POST | /resources | Create |
| PUT | /resources/{id} | Replace |
| PATCH | /resources/{id} | Update |
| DELETE | /resources/{id} | Remove |

### API Versioning

All APIs are versioned via URL path: `/api/v1/...`

### Standard Response Format

**Success:**
```json
{
  "data": { ... },
  "meta": {
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

**Error:**
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input",
    "details": [...]
  }
}
```

### Key Endpoints Summary

| Service | Endpoint | Method | Description |
|---------|----------|--------|-------------|
| Gateway | /api/users/auth | POST | Authenticate user |
| Gateway | /api/onboarding/{userId} | GET | Get onboarding data |
| Gateway | /api/trade/authorize | POST | Create trade auth |
| Gateway | /api/trade/execute | POST | Execute trade |
| Auth | /api/v1/auth/login | POST | Login |
| Auth | /api/v1/auth/session | GET | Session info |
| Recs | /api/v1/recommendations | GET | Get recommendations |
| ML | /recommendations | POST | Generate recommendations |

---

## Deployment Architecture

### Local Development

```
┌─────────────────────────────────────────────────────────────────┐
│                    Docker Compose Stack                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│  │Postgres │ │  Redis  │ │  Kafka  │ │ClickHse│ │  Vault  │   │
│  │  :5432  │ │  :6379  │ │  :9092  │ │  :8123  │ │  :8200  │   │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘   │
│                                                                 │
│  Network: autotrader-network (bridge)                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
          │           │           │           │
          ▼           ▼           ▼           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Application Services                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│  │  Auth   │ │ Config  │ │   Rec   │ │  Trade  │ │   ML    │   │
│  │  :8081  │ │  :8082  │ │  :8083  │ │  :8084  │ │  :8000  │   │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘   │
│                                                                 │
│  ┌──────────────────┐  ┌──────────────────────────────────┐    │
│  │   API Gateway    │  │           Web App                │    │
│  │      :3001       │  │            :5173                 │    │
│  └──────────────────┘  └──────────────────────────────────┘    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Production (Kubernetes)

```
┌─────────────────────────────────────────────────────────────────┐
│                      Kubernetes Cluster                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Ingress Controller                    │   │
│  │              (NGINX / AWS ALB Ingress)                   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│           ┌──────────────────┼──────────────────┐              │
│           ▼                  ▼                  ▼              │
│    ┌────────────┐    ┌────────────┐    ┌────────────┐         │
│    │  Web App   │    │API Gateway │    │   Auth     │         │
│    │ (3 replicas)│    │(3 replicas)│    │(2 replicas)│         │
│    └────────────┘    └────────────┘    └────────────┘         │
│                                                                 │
│    ┌────────────┐    ┌────────────┐    ┌────────────┐         │
│    │   Config   │    │    Rec     │    │   Trade    │         │
│    │(2 replicas)│    │(2 replicas)│    │(2 replicas)│         │
│    └────────────┘    └────────────┘    └────────────┘         │
│                                                                 │
│    ┌────────────┐    ┌────────────┐                            │
│    │ML Engine   │    │Feature Eng │                            │
│    │(3 replicas)│    │(2 replicas)│                            │
│    └────────────┘    └────────────┘                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Managed Services                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │  RDS        │  │ElastiCache  │  │   MSK (Managed Kafka)   │ │
│  │ (Postgres)  │  │  (Redis)    │  │                         │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
│                                                                 │
│  ┌─────────────┐  ┌─────────────────────────────────────────┐  │
│  │   Vault     │  │          S3 (ML Models, Backups)        │  │
│  │ (HashiCorp) │  │                                         │  │
│  └─────────────┘  └─────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Observability

### Metrics (Prometheus)

```yaml
Key Metrics:
  - http_requests_total (counter)
  - http_request_duration_seconds (histogram)
  - trade_executions_total (counter)
  - recommendation_generation_duration (histogram)
  - kafka_consumer_lag (gauge)
  - db_connection_pool_size (gauge)
```

### Logging (ELK Stack)

```
Log Format: Structured JSON

{
  "timestamp": "2024-01-15T10:30:00.000Z",
  "level": "INFO",
  "service": "auth-service",
  "traceId": "abc123",
  "message": "User authenticated",
  "userId": "uuid-here"
}
```

### Tracing (Jaeger/OpenTelemetry)

```
Trace Flow:
  Frontend Request
    └── API Gateway
          └── Auth Service
                └── PostgreSQL Query
          └── Trade Service
                └── Vault Token Retrieval
                └── Brokerage API Call
```

### Alerting (PagerDuty)

| Alert | Condition | Severity |
|-------|-----------|----------|
| High Error Rate | >1% 5xx responses | P1 |
| Trade Failures | >5 failed trades/min | P1 |
| Kafka Lag | Consumer lag >1000 | P2 |
| DB Connection Pool | >80% utilization | P2 |
| ML Latency | p99 >500ms | P3 |

---

## Future Roadmap

### Phase 2
- [ ] Multi-broker support (TD Ameritrade, E*TRADE)
- [ ] Options trading
- [ ] Cryptocurrency support

### Phase 3
- [ ] Advanced automation (conditional orders)
- [ ] Mobile applications (iOS/Android)
- [ ] Backtesting framework

### Phase 4
- [ ] Social trading features
- [ ] Portfolio optimization
- [ ] Tax-loss harvesting

---

## References

- [README.md](./README.md) - Project overview
- [GETTING_STARTED.md](./GETTING_STARTED.md) - Setup guide
- [CONTRIBUTING.md](./CONTRIBUTING.md) - Development guidelines
- [SECURITY.md](./SECURITY.md) - Security policies
- [DEPLOYMENT.md](./DEPLOYMENT.md) - Deployment guide

---

*This document is maintained by the AutoTrader AI engineering team. Last updated: January 2026*

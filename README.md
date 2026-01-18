# AutoTrader AI

**AI-Powered Trading Intelligence Platform**

Enterprise-grade fintech application that delivers continuously generated, explainable AI-powered trading recommendations with secure trade execution via Robinhood.

## 🏗️ Architecture

### Two-Plane Design

1. **Continuous Intelligence Plane** (Always-On)
   - Real-time signal ingestion from market data, news, and social sources
   - Stream processing for feature engineering
   - ML-powered recommendation generation
   - Event-driven, horizontally scalable

2. **User Interaction & Execution Plane** (Session-Driven)
   - Low-latency web application
   - Secure authentication and authorization
   - User-confirmed trade execution
   - Backend-only brokerage access

## 🚀 Technology Stack

- **Frontend**: React 18 + TypeScript + Vite
- **Backend Services**: Java 17 + Spring Boot 3.2
- **API Gateway**: Envoy Proxy
- **Streaming**: Apache Kafka + Apache Flink
- **Databases**: PostgreSQL 15, ClickHouse, Redis
- **ML/AI**: Python 3.11, scikit-learn, PyTorch, LangChain
- **Infrastructure**: Docker, Kubernetes, Terraform
- **CI/CD**: GitHub Actions

## 📁 Project Structure

```
autotrader-ai/
├── services/                    # Backend microservices (Java/Spring Boot)
│   ├── auth-service/           # Authentication & user management
│   ├── config-service/         # User configuration management
│   ├── recommendation-service/ # Recommendation retrieval
│   └── trade-execution-service/ # Trade validation & execution
├── streaming/                   # Event streaming & processing
│   ├── connectors/             # Data source connectors
│   ├── processors/             # Flink stream processors
│   └── kafka-configs/          # Kafka topic definitions
├── ml-services/                 # AI/ML services (Python)
│   ├── feature-engineering/    # Feature computation
│   ├── recommendation-engine/  # ML inference & ranking
│   └── explainability-service/ # LLM-based explanations
├── web-app/                    # React frontend (TypeScript)
├── infrastructure/             # IaC and deployment configs
│   ├── docker/                 # Docker Compose for local dev
│   ├── kubernetes/             # K8s manifests
│   └── terraform/              # Cloud infrastructure
├── database/                   # Database schemas & migrations
│   ├── postgres/               # PostgreSQL migrations (Flyway)
│   └── clickhouse/             # ClickHouse schemas
├── api-gateway/                # Envoy proxy configuration
├── docs/                       # Documentation
└── scripts/                    # Utility scripts
```

## 🔧 Local Development Setup

### Prerequisites

- Docker Desktop 4.x
- Java 17 JDK
- Node.js 20.x
- Python 3.11+
- Maven 3.9+
- Git

### Quick Start

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/autotrader-ai.git
cd autotrader-ai

# Start infrastructure (Kafka, PostgreSQL, Redis, ClickHouse)
docker-compose -f infrastructure/docker/docker-compose.yml up -d

# Run database migrations
cd database/postgres && ./migrate.sh

# Start backend services
cd services
./mvnw spring-boot:run -pl auth-service
./mvnw spring-boot:run -pl config-service
./mvnw spring-boot:run -pl recommendation-service
./mvnw spring-boot:run -pl trade-execution-service

# Start ML services
cd ml-services
pip install -r requirements.txt
python -m feature_engineering.main &
python -m recommendation_engine.main &

# Start frontend
cd web-app
npm install
npm run dev
```

Access the application at: http://localhost:5173

## 🔒 Security & Compliance

- **Authentication**: OAuth 2.0 + JWT with short-lived tokens
- **Secrets Management**: HashiCorp Vault
- **Brokerage Access**: Backend-only, tokens encrypted at rest
- **Audit Logging**: Immutable, append-only logs for all financial actions
- **Data Retention**: 7+ years for trades and audit logs

## 🎯 Key Features

### Phase 1 (MVP)
- ✅ Google SSO + Email/Password authentication
- ✅ Robinhood brokerage connection (OAuth)
- ✅ Real-time signal ingestion (market data, news, social)
- ✅ AI-powered BUY/SELL/HOLD recommendations
- ✅ Explainable AI rationale for each recommendation
- ✅ User-confirmed trade execution
- ✅ Risk limits and position management
- ✅ Watchlist management

### Future Phases
- [ ] Multi-broker support (TD Ameritrade, E*TRADE)
- [ ] Options and crypto trading
- [ ] Advanced automation (conditional orders)
- [ ] Mobile applications (iOS/Android)
- [ ] Backtesting framework

## 📊 Monitoring & Observability

- **Metrics**: Prometheus + Grafana
- **Logging**: ELK Stack (Elasticsearch, Logstash, Kibana)
- **Tracing**: Jaeger (OpenTelemetry)
- **Alerting**: PagerDuty integration

## 🧪 Testing Strategy

- **Unit Tests**: JUnit 5, Jest
- **Integration Tests**: TestContainers, Cypress
- **Contract Tests**: Pact
- **Load Tests**: k6, Gatling
- **Security Tests**: OWASP ZAP

## 📝 Documentation

- [Architecture Decision Records](docs/adr/)
- [API Documentation](docs/api/)
- [Deployment Guide](docs/deployment/)
- [Development Guide](docs/development/)

## 🤝 Contributing

This is a production-grade system. All contributions must:
1. Include comprehensive tests
2. Follow existing code style (enforced by linters)
3. Update documentation
4. Pass all CI checks

## 📜 License

Proprietary - All Rights Reserved

## ⚠️ Disclaimer

This software is for informational purposes only. Trading stocks involves risk. Past performance does not guarantee future results. This is not financial advice.

---

**Built with enterprise-grade architecture principles and FAANG best practices**

# 🚀 Getting Started with AutoTrader AI

Welcome to AutoTrader AI - your enterprise-grade AI-powered trading intelligence platform!

## What's Been Built

✅ **Complete Monorepo Structure** - Enterprise-grade organization  
✅ **4 Backend Microservices** (Java 17/Spring Boot 3.2)
  - Auth Service (port 8081)
  - Config Service
  - Recommendation Service
  - Trade Execution Service

✅ **Modern React Frontend** (TypeScript/Vite)  
✅ **3 ML Services** (Python 3.11)
  - Feature Engineering
  - Recommendation Engine
  - Explainability Service

✅ **Complete Infrastructure**
  - PostgreSQL with Flyway migrations
  - Redis cache
  - Kafka + Zookeeper
  - ClickHouse analytics DB
  - HashiCorp Vault

✅ **CI/CD Pipelines** (GitHub Actions)  
✅ **Docker Compose** for local development  
✅ **Comprehensive Documentation**

## Prerequisites

Install these on your machine:

```bash
# Check versions
java -version        # Need Java 17
node -v             # Need Node 20+
python3 --version   # Need Python 3.11+
docker --version    # Need Docker Desktop 4.x
git --version       # Need Git 2.x
```

## Quick Start (5 Minutes)

### 1. Navigate to Project
```bash
cd ~/autotrader-ai
```

### 2. Install Dependencies
```bash
make install
# This installs: Maven deps, npm packages, Python packages
```

### 3. Start Infrastructure
```bash
make start
# Starts: PostgreSQL, Redis, Kafka, ClickHouse, Vault
```

### 4. Start Services (in separate terminals)

**Terminal 1 - Auth Service:**
```bash
cd ~/autotrader-ai/services
mvn spring-boot:run -pl auth-service
```

**Terminal 2 - ML Service:**
```bash
cd ~/autotrader-ai/ml-services
python -m recommendation_engine.src.main
```

**Terminal 3 - Frontend:**
```bash
cd ~/autotrader-ai/web-app
npm install  # first time only
npm run dev
```

### 5. Access Application
- **Frontend**: http://localhost:5173
- **Auth API**: http://localhost:8081/api/v1/auth/session
- **ML API**: http://localhost:8000/health

## Project Structure

```
autotrader-ai/
├── services/                 # ☕ Java microservices
│   ├── auth-service/        # Authentication & user management
│   ├── config-service/      # User configuration
│   ├── recommendation-service/  # Recommendation retrieval
│   └── trade-execution-service/ # Trade execution
│
├── web-app/                 # ⚛️ React TypeScript app
│   ├── src/
│   │   ├── components/      # React components
│   │   ├── pages/          # Page components
│   │   ├── services/       # API clients
│   │   └── types/          # TypeScript types
│   └── package.json
│
├── ml-services/             # 🤖 Python ML services
│   ├── feature-engineering/
│   ├── recommendation-engine/
│   └── explainability-service/
│
├── infrastructure/          # 🏗️ Infrastructure configs
│   ├── docker/             # Docker Compose
│   ├── kubernetes/         # K8s manifests
│   └── terraform/          # IaC configs
│
├── database/               # 🗄️ Database schemas
│   ├── postgres/           # PostgreSQL migrations
│   └── clickhouse/         # ClickHouse schemas
│
├── .github/workflows/      # 🔄 CI/CD pipelines
└── scripts/                # 🛠️ Utility scripts
```

## Development Workflow

### Make a Change

```bash
# 1. Create feature branch
git checkout -b feature/your-feature

# 2. Make changes to code
# Edit files...

# 3. Test locally
make test

# 4. Commit changes
git add .
git commit -m "feat: add new feature"

# 5. Push to GitHub
git push origin feature/your-feature

# 6. Create Pull Request on GitHub
```

## Common Commands

```bash
# Start everything
make start

# Stop everything
make stop

# Clean all data
make clean

# Install dependencies
make install

# Run tests
make test

# View logs
docker compose -f infrastructure/docker/docker-compose.yml logs -f postgres

# Database access
psql -h localhost -U autotrader -d autotrader
```

## Connecting to GitHub

Follow the detailed guide in [GITHUB_SETUP.md](./GITHUB_SETUP.md)

**Quick version:**
```bash
# 1. Create repo on GitHub (don't initialize)
# 2. Add remote
git remote add origin https://github.com/YOUR_USERNAME/autotrader-ai.git

# 3. Push
git push -u origin main
```

## Next Steps

1. ✅ Read [GITHUB_SETUP.md](./GITHUB_SETUP.md) - Connect to GitHub
2. ✅ Read [DEPLOYMENT.md](./DEPLOYMENT.md) - Deploy to cloud
3. ✅ Read [CONTRIBUTING.md](./CONTRIBUTING.md) - Learn contribution guidelines
4. ✅ Review [API Documentation](./docs/api/) - Understand APIs
5. ✅ Check [Architecture Docs](./docs/) - Deep dive into design

## Key Features

### Backend Services
- JWT-based authentication
- PostgreSQL for data persistence
- Redis caching layer
- RESTful API design
- Comprehensive error handling

### Frontend
- Modern React with TypeScript
- TanStack Query for data fetching
- Tailwind CSS for styling
- Vite for fast builds
- Component-based architecture

### ML Services
- FastAPI framework
- Real-time recommendations
- Explainable AI
- Kafka integration ready

### Infrastructure
- Docker Compose for local dev
- Kubernetes-ready architecture
- Terraform for cloud deployment
- Complete observability stack

## Troubleshooting

### Services won't start
```bash
# Check Docker
docker ps

# Restart infrastructure
make stop && make start

# Check logs
docker compose -f infrastructure/docker/docker-compose.yml logs
```

### Port conflicts
```bash
# Check what's using a port
lsof -i :5432  # PostgreSQL
lsof -i :3001  # API gateway
lsof -i :5173  # Web app
```

### Database issues
```bash
# Reset database
make clean
make start
cd database/postgres && ./migrate.sh
```

## Getting Help

- 📖 Check [README.md](./README.md) for detailed info
- 🔧 Review [DEPLOYMENT.md](./DEPLOYMENT.md) for deployment
- 💻 Read [CONTRIBUTING.md](./CONTRIBUTING.md) for dev guidelines
- 🐛 Create GitHub issue for bugs
- 💬 Reach out to the team

## What's Different from Standard Apps?

This is built following **FAANG enterprise standards**:

1. **Separation of Concerns** - Intelligence plane vs execution plane
2. **Security First** - Vault for secrets, JWT auth, backend-only brokerage access
3. **Scalability** - Event-driven with Kafka, horizontal scaling ready
4. **Observability** - Structured logging, metrics, tracing built-in
5. **Compliance** - Audit logs, deterministic recommendations, ACID guarantees
6. **Quality** - Type safety, comprehensive tests, CI/CD pipelines

## Architecture Highlights

- **Continuous Intelligence Plane**: Always-on signal processing
- **User Execution Plane**: Low-latency trade execution
- **No AI in Critical Path**: Recommendations pre-computed
- **Backend-Only Brokerage**: Security boundary enforced
- **Event Sourcing**: Kafka for replayability
- **Polyglot Persistence**: Right DB for right workload

---

**Happy Coding! 🚀**

Built with enterprise-grade architecture and FAANG best practices.

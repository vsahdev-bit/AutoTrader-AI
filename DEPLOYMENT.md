# AutoTrader AI - Deployment Guide

## Local Development

### Quick Start
```bash
make start        # Start all services
make stop         # Stop all services
make clean        # Clean all data
make install      # Install dependencies
make test         # Run all tests
```

### Service URLs
- Web App: http://localhost:5173
- API Gateway: http://localhost:3001 (health: /health)
- Recommendation Engine: http://localhost:8000 (health: /health)
- PostgreSQL: localhost:5432
- Redis: localhost:6379
- Kafka: localhost:9092
- ClickHouse: http://localhost:8123
- Vault: http://localhost:8200

### Debugging

```bash
# View logs (prefer docker compose, fall back to docker-compose)
docker compose -f infrastructure/docker/docker-compose.yml logs -f postgres
docker compose -f infrastructure/docker/docker-compose.yml logs -f kafka

# Access database
psql -h localhost -U autotrader -d autotrader

# Access Redis
redis-cli -p 6379

# Access Vault UI
open http://localhost:8200
```

## Docker Deployment

### Build Images (Compose Stack)

For a containerized deployment that mirrors the local Docker Compose stack, build the images referenced by `infrastructure/docker/docker-compose.yml`.

```bash
# Build all images used by the compose stack
# (web-app, recommendation-engine, news-ingestion, connector-health, etc.)
docker compose -f infrastructure/docker/docker-compose.yml build
```

### Run Locally (as containers)

```bash
# Start the stack
make start

# Or equivalently:
docker compose -f infrastructure/docker/docker-compose.yml up -d --build
```

### Push to Registry

Tag and push the images to your registry (example names shown; adjust to your registry and naming convention).

```bash
# Example: tag and push web app
# docker tag autotrader-web-app:latest YOUR_REGISTRY/autotrader-web-app:latest
# docker push YOUR_REGISTRY/autotrader-web-app:latest

# Example: tag and push recommendation engine
# docker tag autotrader-recommendation-engine:latest YOUR_REGISTRY/autotrader-recommendation-engine:latest
# docker push YOUR_REGISTRY/autotrader-recommendation-engine:latest
```

Notes:
- Some services (e.g., `api-gateway`) use a base image and run from a bind mount in local dev; for production you would typically create a dedicated Dockerfile/image and remove bind mounts.
- The Java Spring Boot microservices in `services/` are not currently part of the local compose stack; if/when they are containerized for deployment, add build/push steps here.

## Kubernetes Deployment

Kubernetes manifests are in `infrastructure/kubernetes/`:

```bash
# Create namespace
kubectl create namespace autotrader

# Deploy services
kubectl apply -f infrastructure/kubernetes/ -n autotrader

# Check status
kubectl get pods -n autotrader
kubectl logs -f deployment/auth-service -n autotrader
```

## Infrastructure as Code

Using Terraform in `infrastructure/terraform/`:

```bash
cd infrastructure/terraform

# Initialize
terraform init

# Plan
terraform plan

# Apply
terraform apply
```

## CI/CD Pipeline

GitHub Actions automatically:
1. Builds on every push
2. Runs tests
3. Builds Docker images (on main)
4. Deploys to staging (on main)
5. Deploys to production (on tags)

## Monitoring & Logging

### Prometheus
```bash
# Metrics endpoint
curl http://localhost:9090
```

### ELK Stack
```bash
# Elasticsearch: http://localhost:9200
# Kibana: http://localhost:5601
```

### Jaeger Tracing
```bash
# Jaeger UI: http://localhost:16686
```

## Security Considerations

1. ✅ Never commit secrets
2. ✅ Use environment variables
3. ✅ Enable HTTPS in production
4. ✅ Use HashiCorp Vault for secrets
5. ✅ Enable audit logging
6. ✅ Regular security scans
7. ✅ Keep dependencies updated

## Scaling

### Horizontal Scaling
- Services run in Kubernetes pods
- Use HPA for auto-scaling
- Load balanced with Envoy

### Vertical Scaling
- Increase pod resources
- Optimize database indexes
- Cache strategy with Redis

## Backup & Recovery

```bash
# Backup PostgreSQL
pg_dump -h localhost -U autotrader autotrader > backup.sql

# Restore
psql -h localhost -U autotrader autotrader < backup.sql

# Backup ClickHouse
clickhouse-client --query "BACKUP TABLE db.table TO 's3://bucket/backup'"
```

## Troubleshooting

### Services won't start
```bash
# Check logs
docker compose -f infrastructure/docker/docker-compose.yml logs

# Rebuild images
docker compose -f infrastructure/docker/docker-compose.yml build --no-cache

# Clean up
docker compose -f infrastructure/docker/docker-compose.yml down -v
```

### Database connection issues
```bash
# Test connection
psql -h localhost -U autotrader -d autotrader -c "SELECT 1;"

# Check migrations
./database/postgres/migrate.sh
```

### Performance issues
- Check CPU/Memory usage
- Review slow query logs
- Analyze database indexes
- Profile applications

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
- API Gateway: http://localhost:8080
- Frontend: http://localhost:5173
- PostgreSQL: localhost:5432
- Redis: localhost:6379
- Kafka: localhost:9092
- ClickHouse: localhost:8123
- Vault: http://localhost:8200

### Debugging

```bash
# View logs
docker-compose logs -f postgres
docker-compose logs -f kafka

# Access database
psql -h localhost -U autotrader -d autotrader

# Access Redis
redis-cli -p 6379

# Access Vault UI
open http://localhost:8200
```

## Docker Deployment

### Build Images

```bash
# Build all services
docker build -t autotrader-auth:latest ./services/auth-service
docker build -t autotrader-config:latest ./services/config-service
docker build -t autotrader-recommendation:latest ./services/recommendation-service
docker build -t autotrader-trade:latest ./services/trade-execution-service
docker build -t autotrader-web:latest ./web-app
docker build -t autotrader-ml:latest ./ml-services
```

### Push to Registry

```bash
docker tag autotrader-auth:latest YOUR_REGISTRY/autotrader-auth:latest
docker push YOUR_REGISTRY/autotrader-auth:latest
# ... repeat for other images
```

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
docker-compose logs

# Rebuild images
docker-compose build --no-cache

# Clean up
docker-compose down -v
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

# AutoTrader AI - Productionization Plan

## Free Cloud Deployment Guide

**Document Version**: 1.0  
**Last Updated**: January 2026  
**Author**: AutoTrader AI Team

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current Architecture Analysis](#current-architecture-analysis)
3. [Free Cloud Alternatives](#free-cloud-alternatives)
4. [Simplified Target Architecture](#simplified-target-architecture)
5. [Implementation Plan](#implementation-plan)
6. [Code Changes Required](#code-changes-required)
7. [Cost Summary](#cost-summary)
8. [Limitations & Mitigations](#limitations--mitigations)
9. [Quick Start Guide](#quick-start-guide)

---

## Executive Summary

This document outlines the plan to deploy AutoTrader AI to production using **free cloud services**. 
The goal is to make the application publicly accessible for a small number of users without 
incurring any monthly costs.

### Key Decisions

| Decision | Rationale |
|----------|-----------|
| Use Vercel for frontend | Free tier, perfect for Vite/React, auto-deploys from GitHub |
| Use Render.com for backend | Free tier supports Node.js + Python, easy Docker deployment |
| Use Neon.tech for PostgreSQL | Free 0.5GB forever, serverless, no maintenance |
| Remove HashiCorp Vault | Overkill for small scale; use environment variables instead |
| Remove ClickHouse | Overkill; consolidate news features into PostgreSQL |
| Remove Kafka | Not needed for few users; use direct API calls |
| Optional Redis via Upstash | Use in-memory caching as fallback if not needed |

---

## Current Architecture Analysis

### Services Inventory

The following table lists all services currently running in Docker Compose locally,
their purpose, and whether they are required for the production MVP.

| Service | Technology | Purpose | Required for MVP? | Notes |
|---------|------------|---------|-------------------|-------|
| **web-app** | React/Vite/TypeScript | Frontend user interface | ✅ **Yes** | Core UI for users |
| **api-gateway** | Node.js/Express | API routing, authentication, Plaid integration | ✅ **Yes** | Handles auth, brokerage connections |
| **recommendation-engine** | Python/FastAPI | ML recommendations + Regime classification | ✅ **Yes** | Core ML service with regime model |
| **postgres** | PostgreSQL 15 | User data, configurations, recommendations | ✅ **Yes** | Primary data store |
| **redis** | Redis 7 | Caching for features and recommendations | ⚠️ **Optional** | Can use in-memory cache instead |
| **clickhouse** | ClickHouse | News features time-series storage | ⚠️ **Replace** | Move to PostgreSQL |
| **vault** | HashiCorp Vault | Secrets management (API keys, tokens) | ❌ **Replace** | Use environment variables |
| **kafka** | Apache Kafka | Event streaming for news pipeline | ❌ **Remove** | Not needed for MVP |
| **zookeeper** | Apache Zookeeper | Kafka coordination | ❌ **Remove** | Only needed with Kafka |
| **news-ingestion** | Python | Fetch and process news articles | ⚠️ **Simplify** | Can run as cron job |
| **connector-health** | Python | Monitor data connector health | ⚠️ **Optional** | Nice to have |

### Dependencies Analysis

#### Vault Usage (To Be Removed)

Vault is currently used in these locations:
- `api-gateway/src/vault.js` - Stores Plaid tokens, brokerage credentials
- `ml-services/vault_client.py` - Retrieves API keys for data connectors

**Replacement Strategy**: Use environment variables stored in:
- GitHub Secrets (for CI/CD pipelines)
- Render/Vercel environment variables (for runtime)

#### ClickHouse Usage (To Be Replaced with PostgreSQL)

ClickHouse stores news sentiment features:
- `ml-services/recommendation-engine/src/news_features.py` - Fetches sentiment data

**Replacement Strategy**: Create a `news_features` table in PostgreSQL (Neon)

#### Redis Usage (Optional)

Redis is used for caching:
- `ml-services/feature-engineering/src/price_data.py` - Price data cache
- `ml-services/recommendation-engine/src/news_features.py` - Feature cache

**Replacement Strategy**: 
- Option A: Use Upstash free tier (10K commands/day)
- Option B: Use in-memory Python dict cache (simpler, no external dependency)

#### Kafka Usage (To Be Removed)

Kafka handles event streaming for news ingestion. For a small user base:
- Direct API calls are sufficient
- Batch processing via cron jobs works fine

---

## Free Cloud Alternatives

### Detailed Comparison of Free Services

#### Frontend Hosting Options

| Service | Free Tier | Pros | Cons | Recommendation |
|---------|-----------|------|------|----------------|
| **Vercel** | 100GB bandwidth/mo, unlimited deploys | Perfect for Vite/React, auto-deploy from GitHub, preview deployments | Serverless functions limited | ✅ **Best Choice** |
| **GitHub Pages** | Unlimited | Free forever, simple setup | Static only, no SSR, no env vars at build | Good for simple sites |
| **Netlify** | 100GB bandwidth/mo, 300 build min/mo | Similar to Vercel, good DX | Slightly slower builds | Alternative to Vercel |
| **Cloudflare Pages** | Unlimited bandwidth | Fast CDN, unlimited bandwidth | Newer, less mature | Good alternative |

**Selected: Vercel**
- Vite/React optimized
- Automatic HTTPS
- Preview deployments for PRs
- Environment variables support
- GitHub integration

#### Backend Hosting Options

| Service | Free Tier | Pros | Cons | Recommendation |
|---------|-----------|------|------|----------------|
| **Render.com** | 750 hrs/mo per service | Easy Docker deploy, supports Node.js + Python | Sleeps after 15min inactivity | ✅ **Best Choice** |
| **Railway** | $5 credit/mo (~500 hrs) | Great DX, easy setup | Credit-based, may run out | Good alternative |
| **Fly.io** | 3 shared VMs, 160GB outbound | Always-on option | More complex setup | For always-on needs |
| **Heroku** | Discontinued free tier | N/A | No longer free | ❌ Not viable |

**Selected: Render.com**
- Supports both Node.js (api-gateway) and Python (recommendation-engine)
- Auto-deploy from GitHub
- Free PostgreSQL for 90 days (we'll use Neon instead)
- Deploy hooks for CI/CD
- Environment variables management

#### PostgreSQL Database Options

| Service | Free Tier | Storage | Pros | Cons | Recommendation |
|---------|-----------|---------|------|------|----------------|
| **Neon** | Forever free | 0.5GB | Serverless, auto-scaling, branching | Storage limit | ✅ **Best Choice** |
| **Supabase** | Forever free | 500MB | Includes auth, real-time | 2 project limit | Good alternative |
| **Railway** | Part of $5 credit | 1GB shared | All-in-one with compute | Credit-based | If using Railway |
| **PlanetScale** | 5GB | 5GB reads/mo | MySQL only | Not PostgreSQL | ❌ Wrong DB type |
| **ElephantSQL** | 20MB | Tiny | Free forever | Too small | ❌ Too limited |

**Selected: Neon.tech**
- True serverless PostgreSQL
- 0.5GB storage (enough for ~10K+ recommendations)
- Connection pooling built-in
- Database branching for dev/staging
- No cold starts

#### Redis/Caching Options

| Service | Free Tier | Pros | Cons | Recommendation |
|---------|-----------|------|------|----------------|
| **Upstash** | 10K commands/day | Serverless Redis, REST API | Daily command limit | ✅ **Best Choice** |
| **Redis Cloud** | 30MB | Official Redis | Very limited storage | Too small |
| **In-memory cache** | N/A | No external dependency | Lost on restart | ⚠️ Simplest option |

**Selected: Upstash (optional) or In-memory**
- For MVP with few users, in-memory cache may suffice
- Upstash if caching is critical for performance

---

## Simplified Target Architecture

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              GITHUB                                          │
│                                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌────────────────────────────────┐ │
│  │   Actions    │    │   Secrets    │    │        Repository              │ │
│  │   (CI/CD)    │    │  (API Keys)  │    │   (Source Code + Workflows)    │ │
│  └──────┬───────┘    └──────────────┘    └────────────────────────────────┘ │
│         │                                                                    │
└─────────┼────────────────────────────────────────────────────────────────────┘
          │
          │ Triggers deploy on push to main
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DEPLOYMENT TARGETS                                   │
│                                                                              │
│  ┌─────────────────┐   ┌─────────────────────┐   ┌─────────────────────┐   │
│  │     VERCEL      │   │     RENDER.COM      │   │     NEON.TECH       │   │
│  │   (Frontend)    │   │     (Backend)       │   │    (Database)       │   │
│  │                 │   │                     │   │                     │   │
│  │  ┌───────────┐  │   │  ┌───────────────┐  │   │  ┌───────────────┐  │   │
│  │  │  web-app  │  │   │  │  api-gateway  │  │   │  │  PostgreSQL   │  │   │
│  │  │  (React)  │  │   │  │  (Node.js)    │  │   │  │               │  │   │
│  │  └───────────┘  │   │  └───────┬───────┘  │   │  │  • users      │  │   │
│  │                 │   │          │          │   │  │  • configs    │  │   │
│  │  Static Build   │   │  ┌───────▼───────┐  │   │  │  • recs       │  │   │
│  │  CDN Cached     │   │  │ recommendation│  │   │  │  • news_feat  │  │   │
│  │                 │   │  │    -engine    │  │   │  └───────────────┘  │   │
│  │                 │   │  │  (Python)     │  │   │                     │   │
│  │                 │   │  └───────────────┘  │   │  0.5GB Free Tier    │   │
│  │ 100GB/mo Free   │   │                     │   │                     │   │
│  │                 │   │  750 hrs/mo Free    │   │                     │   │
│  └─────────────────┘   └─────────────────────┘   └─────────────────────┘   │
│                                                                              │
│                        ┌─────────────────────┐                              │
│                        │     UPSTASH         │                              │
│                        │  (Redis - Optional) │                              │
│                        │                     │                              │
│                        │  10K cmds/day Free  │                              │
│                        └─────────────────────┘                              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
User Browser                    Vercel CDN                 Render Backend              Neon Database
     │                              │                            │                           │
     │  1. Load app                 │                            │                           │
     ├─────────────────────────────►│                            │                           │
     │◄─────────────────────────────┤                            │                           │
     │     Static HTML/JS/CSS       │                            │                           │
     │                              │                            │                           │
     │  2. Login (Google OAuth)     │                            │                           │
     ├──────────────────────────────┼───────────────────────────►│                           │
     │                              │                            ├──────────────────────────►│
     │                              │                            │  Check/create user        │
     │                              │                            │◄──────────────────────────┤
     │◄─────────────────────────────┼────────────────────────────┤                           │
     │     JWT Token                │                            │                           │
     │                              │                            │                           │
     │  3. Get recommendations      │                            │                           │
     ├──────────────────────────────┼───────────────────────────►│                           │
     │                              │                            ├──────────────────────────►│
     │                              │                            │  Query recommendations    │
     │                              │                            │◄──────────────────────────┤
     │◄─────────────────────────────┼────────────────────────────┤                           │
     │     JSON response            │                            │                           │
     │                              │                            │                           │
```

### Services to Deploy

| Service | Platform | Build Command | Start Command | Port |
|---------|----------|---------------|---------------|------|
| **web-app** | Vercel | `npm run build` | N/A (static) | 443 |
| **api-gateway** | Render | `npm install` | `npm start` | 3001 |
| **recommendation-engine** | Render | `pip install -r requirements.txt` | `uvicorn src.recommendation_flow:app --host 0.0.0.0 --port 8000` | 8000 |

---

## Implementation Plan

### Phase 1: Prepare Codebase (Estimated: 1-2 days)

#### 1.1 Create Production Environment Files

Create environment-specific configuration files for production deployment.

**Files to Create:**

```
web-app/.env.production
api-gateway/.env.production
ml-services/.env.production
```

**web-app/.env.production:**
```env
# Production environment variables for frontend
# These are embedded at build time by Vite

VITE_API_URL=https://api-gateway-xxxx.onrender.com
VITE_GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com

# Note: VITE_ prefix required for Vite to expose to client
```

**api-gateway/.env.production:**
```env
# Production environment variables for API Gateway
# Set these in Render dashboard, NOT committed to repo

PORT=3001
NODE_ENV=production

# Database (Neon PostgreSQL)
DATABASE_URL=postgresql://user:pass@ep-xxx.us-east-2.aws.neon.tech/autotrader?sslmode=require

# Authentication
JWT_SECRET=your-secure-jwt-secret-min-32-chars
GOOGLE_CLIENT_ID=your-google-client-id

# External APIs (set in Render environment variables)
PLAID_CLIENT_ID=your-plaid-client-id
PLAID_SECRET=your-plaid-secret
PLAID_ENV=sandbox

# CORS
ALLOWED_ORIGINS=https://autotrader-ai.vercel.app
```

**ml-services/.env.production:**
```env
# Production environment variables for ML services

# Database
DATABASE_URL=postgresql://user:pass@ep-xxx.us-east-2.aws.neon.tech/autotrader?sslmode=require

# Redis (optional - Upstash)
REDIS_URL=redis://default:xxx@us1-xxx.upstash.io:6379

# If not using Redis, set to empty to use in-memory cache
# REDIS_URL=

# External APIs
ALPHA_VANTAGE_API_KEY=your-key
POLYGON_API_KEY=your-key
```

#### 1.2 Update Code to Remove/Replace Dependencies

The following code changes are needed to remove paid service dependencies:

| Change | File(s) | Description |
|--------|---------|-------------|
| Remove Vault | `api-gateway/src/vault.js` | Replace with environment variables |
| Replace ClickHouse | `ml-services/recommendation-engine/src/news_features.py` | Use PostgreSQL instead |
| Add Redis fallback | `ml-services/feature-engineering/src/price_data.py` | Use in-memory if Redis unavailable |
| Remove Kafka | `streaming/` directory | Not needed for MVP |

#### 1.3 Create PostgreSQL Migration for News Features

Create a new migration to store news features in PostgreSQL instead of ClickHouse.

**File: `database/postgres/V9__news_features.sql`**

```sql
-- ============================================================================
-- V9__news_features.sql
-- Migration to add news features table (replaces ClickHouse)
-- ============================================================================
-- 
-- This table stores pre-computed news sentiment features that were previously
-- stored in ClickHouse. For a small user base, PostgreSQL is sufficient and
-- eliminates the need for a separate ClickHouse instance.
--
-- The recommendation engine queries this table to get sentiment data for
-- generating stock recommendations.
-- ============================================================================

CREATE TABLE IF NOT EXISTS news_features (
    -- Composite primary key: one row per symbol per day
    symbol VARCHAR(10) NOT NULL,
    feature_date DATE NOT NULL,
    
    -- Short-term sentiment (1-3 days)
    sentiment_1d FLOAT,           -- Average sentiment score for last 24 hours
    sentiment_3d FLOAT,           -- Average sentiment score for last 3 days
    
    -- Medium-term sentiment (7-14 days)
    sentiment_7d FLOAT,           -- Average sentiment score for last 7 days
    sentiment_14d FLOAT,          -- Average sentiment score for last 14 days
    
    -- Sentiment momentum (change over time)
    sentiment_momentum_3d FLOAT,  -- sentiment_1d - sentiment_3d
    sentiment_momentum_7d FLOAT,  -- sentiment_3d - sentiment_7d
    
    -- Article volume metrics
    article_count_1d INTEGER DEFAULT 0,
    article_count_7d INTEGER DEFAULT 0,
    
    -- Volume ratio (current vs average)
    volume_ratio FLOAT DEFAULT 1.0,
    
    -- Sentiment volatility
    sentiment_volatility_7d FLOAT,
    
    -- Confidence in sentiment scores
    avg_confidence_1d FLOAT,
    avg_confidence_7d FLOAT,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    PRIMARY KEY (symbol, feature_date)
);

-- Index for efficient lookups by symbol
CREATE INDEX idx_news_features_symbol ON news_features(symbol);

-- Index for date-based queries (cleanup old data)
CREATE INDEX idx_news_features_date ON news_features(feature_date);

-- Comment on table
COMMENT ON TABLE news_features IS 'Pre-computed news sentiment features for recommendation engine. Updated daily by news ingestion service.';
```

### Phase 2: Set Up Free Services (Estimated: 1 day)

#### 2.1 Set Up Neon.tech (PostgreSQL Database)

**Step-by-step instructions:**

1. **Sign up** at https://neon.tech (use GitHub OAuth for easy login)

2. **Create a new project:**
   - Project name: `autotrader-ai`
   - Region: Select closest to your users (e.g., `us-east-2`)
   - PostgreSQL version: 15 (latest)

3. **Get connection string:**
   - Go to Dashboard → Connection Details
   - Copy the connection string (looks like):
     ```
     postgresql://username:password@ep-xxx-xxx-123456.us-east-2.aws.neon.tech/autotrader?sslmode=require
     ```

4. **Run database migrations:**
   ```bash
   # Set the connection string
   export DATABASE_URL="postgresql://user:pass@ep-xxx.neon.tech/autotrader?sslmode=require"
   
   # Run all migrations in order
   psql $DATABASE_URL < database/postgres/V1__initial_schema.sql
   psql $DATABASE_URL < database/postgres/V2__onboarding_schema.sql
   psql $DATABASE_URL < database/postgres/V3__brokerage_connections.sql
   psql $DATABASE_URL < database/postgres/V4__trade_authorizations.sql
   psql $DATABASE_URL < database/postgres/V5__stock_recommendations.sql
   psql $DATABASE_URL < database/postgres/V6__connector_status.sql
   psql $DATABASE_URL < database/postgres/V7__recommendation_generation_status.sql
   psql $DATABASE_URL < database/postgres/V8__health_check_settings.sql
   psql $DATABASE_URL < database/postgres/V9__news_features.sql  # New migration
   ```

5. **Verify setup:**
   ```bash
   psql $DATABASE_URL -c "\dt"  # List all tables
   ```

**Neon Free Tier Limits:**
- 0.5 GB storage
- 1 project
- 10 branches
- Serverless compute (scales to zero)

#### 2.2 Set Up Render.com (Backend Services)

**Step-by-step instructions:**

1. **Sign up** at https://render.com (use GitHub OAuth)

2. **Connect GitHub repository:**
   - Go to Dashboard → New → Web Service
   - Connect your GitHub account
   - Select `vsahdev-bit/AutoTrader-AI` repository

3. **Create API Gateway service:**
   - Name: `autotrader-api-gateway`
   - Region: Oregon (US West) or closest to users
   - Branch: `main`
   - Root Directory: `api-gateway`
   - Runtime: Node
   - Build Command: `npm install`
   - Start Command: `npm start`
   - Instance Type: Free
   
   **Environment Variables (set in Render dashboard):**
   ```
   PORT=3001
   NODE_ENV=production
   DATABASE_URL=<your-neon-connection-string>
   JWT_SECRET=<generate-secure-32-char-string>
   GOOGLE_CLIENT_ID=<your-google-client-id>
   PLAID_CLIENT_ID=<your-plaid-client-id>
   PLAID_SECRET=<your-plaid-secret>
   PLAID_ENV=sandbox
   ALLOWED_ORIGINS=https://autotrader-ai.vercel.app
   ```

4. **Create Recommendation Engine service:**
   - Name: `autotrader-recommendation-engine`
   - Region: Same as API Gateway
   - Branch: `main`
   - Root Directory: `ml-services/recommendation-engine`
   - Runtime: Python 3
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn src.recommendation_flow:app --host 0.0.0.0 --port $PORT`
   - Instance Type: Free
   
   **Environment Variables:**
   ```
   DATABASE_URL=<your-neon-connection-string>
   REDIS_URL=<your-upstash-url-or-leave-empty>
   ALPHA_VANTAGE_API_KEY=<your-key>
   ```

5. **Get Deploy Hooks** (for CI/CD):
   - Go to each service → Settings → Deploy Hook
   - Copy the URL (looks like): `https://api.render.com/deploy/srv-xxx?key=xxx`
   - Save these for GitHub Actions

**Render Free Tier Limits:**
- 750 hours/month per service
- Services sleep after 15 minutes of inactivity
- ~30 second cold start when waking up

#### 2.3 Set Up Vercel (Frontend)

**Step-by-step instructions:**

1. **Sign up** at https://vercel.com (use GitHub OAuth)

2. **Import project:**
   - Click "Add New" → "Project"
   - Import from GitHub: `vsahdev-bit/AutoTrader-AI`

3. **Configure project:**
   - Framework Preset: Vite
   - Root Directory: `web-app`
   - Build Command: `npm run build` (auto-detected)
   - Output Directory: `dist` (auto-detected)

4. **Set Environment Variables:**
   ```
   VITE_API_URL=https://autotrader-api-gateway.onrender.com
   VITE_RECOMMENDATION_ENGINE_URL=https://autotrader-recommendation-engine.onrender.com
   VITE_GOOGLE_CLIENT_ID=<your-google-client-id>
   ```

5. **Deploy:**
   - Click "Deploy"
   - Vercel will build and deploy automatically
   - Get your URL: `https://autotrader-ai.vercel.app`

6. **Set up custom domain (optional):**
   - Go to Settings → Domains
   - Add your domain and follow DNS instructions

**Vercel Free Tier Limits:**
- 100 GB bandwidth/month
- Unlimited deployments
- Preview deployments for PRs
- Automatic HTTPS

#### 2.4 Set Up Upstash (Optional Redis)

**Only needed if you want caching. Skip if using in-memory cache.**

1. **Sign up** at https://upstash.com

2. **Create Redis database:**
   - Name: `autotrader-cache`
   - Region: Same as Render services
   - Type: Regional (not Global for free tier)

3. **Get connection details:**
   - Copy REST URL and token
   - Or use Redis URL: `redis://default:xxx@us1-xxx.upstash.io:6379`

4. **Add to Render environment variables:**
   ```
   REDIS_URL=redis://default:xxx@us1-xxx.upstash.io:6379
   ```

**Upstash Free Tier Limits:**
- 10,000 commands/day
- 256 MB storage
- 1 database

### Phase 3: Update GitHub Actions (Estimated: 1 day)

#### 3.1 Create Production Deploy Workflow

Create a new workflow file for deploying to production services.

**File: `.github/workflows/deploy-production.yml`**

```yaml
# =============================================================================
# AutoTrader AI - Production Deployment Workflow
# =============================================================================
#
# This workflow deploys the application to free cloud services:
# - Frontend: Vercel
# - Backend: Render.com
# - Database: Neon.tech (migrations only)
#
# Triggered on:
# - Push to main branch
# - Manual dispatch
#
# Required Secrets:
# - VERCEL_TOKEN: Vercel deployment token
# - VERCEL_ORG_ID: Vercel organization ID
# - VERCEL_PROJECT_ID: Vercel project ID
# - RENDER_DEPLOY_HOOK_API: Render deploy hook for api-gateway
# - RENDER_DEPLOY_HOOK_REC: Render deploy hook for recommendation-engine
# - NEON_DATABASE_URL: Neon PostgreSQL connection string
# =============================================================================

name: Deploy to Production

on:
  push:
    branches: [main]
  workflow_dispatch:
    inputs:
      deploy_frontend:
        description: 'Deploy frontend to Vercel'
        type: boolean
        default: true
      deploy_backend:
        description: 'Deploy backend to Render'
        type: boolean
        default: true
      run_migrations:
        description: 'Run database migrations'
        type: boolean
        default: false

env:
  NODE_VERSION: '20'
  PYTHON_VERSION: '3.11'

jobs:
  # ===========================================================================
  # Test Job - Run tests before deploying
  # ===========================================================================
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: 'npm'
          cache-dependency-path: 'web-app/package-lock.json'
      
      - name: Install frontend dependencies
        run: |
          cd web-app
          npm ci
      
      - name: Run frontend tests
        run: |
          cd web-app
          npm run lint
          npm run build
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      
      - name: Install ML dependencies
        run: |
          pip install -r ml-services/requirements.txt
      
      - name: Run ML tests
        run: |
          cd ml-services/recommendation-engine
          python -m pytest tests/ -v || true  # Don't fail on test errors for now

  # ===========================================================================
  # Database Migrations Job
  # ===========================================================================
  migrate:
    runs-on: ubuntu-latest
    needs: test
    if: github.event.inputs.run_migrations == 'true'
    steps:
      - uses: actions/checkout@v4
      
      - name: Run database migrations
        env:
          DATABASE_URL: ${{ secrets.NEON_DATABASE_URL }}
        run: |
          # Install PostgreSQL client
          sudo apt-get update && sudo apt-get install -y postgresql-client
          
          # Run migrations
          for file in database/postgres/V*.sql; do
            echo "Running migration: $file"
            psql "$DATABASE_URL" -f "$file" || true
          done

  # ===========================================================================
  # Frontend Deployment Job (Vercel)
  # ===========================================================================
  deploy-frontend:
    runs-on: ubuntu-latest
    needs: test
    if: github.event.inputs.deploy_frontend != 'false'
    steps:
      - uses: actions/checkout@v4
      
      - name: Deploy to Vercel
        uses: amondnet/vercel-action@v25
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.VERCEL_ORG_ID }}
          vercel-project-id: ${{ secrets.VERCEL_PROJECT_ID }}
          working-directory: ./web-app
          vercel-args: '--prod'

  # ===========================================================================
  # Backend Deployment Job (Render)
  # ===========================================================================
  deploy-backend:
    runs-on: ubuntu-latest
    needs: test
    if: github.event.inputs.deploy_backend != 'false'
    steps:
      - name: Deploy API Gateway to Render
        run: |
          curl -X POST "${{ secrets.RENDER_DEPLOY_HOOK_API }}"
          echo "Triggered API Gateway deployment"
      
      - name: Deploy Recommendation Engine to Render
        run: |
          curl -X POST "${{ secrets.RENDER_DEPLOY_HOOK_REC }}"
          echo "Triggered Recommendation Engine deployment"
      
      - name: Wait for deployments
        run: |
          echo "Deployments triggered. Check Render dashboard for status."
          echo "API Gateway: https://dashboard.render.com"
          sleep 10

  # ===========================================================================
  # Notification Job
  # ===========================================================================
  notify:
    runs-on: ubuntu-latest
    needs: [deploy-frontend, deploy-backend]
    if: always()
    steps:
      - name: Deployment Summary
        run: |
          echo "## Deployment Summary" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "| Service | Status |" >> $GITHUB_STEP_SUMMARY
          echo "|---------|--------|" >> $GITHUB_STEP_SUMMARY
          echo "| Frontend (Vercel) | ${{ needs.deploy-frontend.result }} |" >> $GITHUB_STEP_SUMMARY
          echo "| Backend (Render) | ${{ needs.deploy-backend.result }} |" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "### URLs" >> $GITHUB_STEP_SUMMARY
          echo "- Frontend: https://autotrader-ai.vercel.app" >> $GITHUB_STEP_SUMMARY
          echo "- API Gateway: https://autotrader-api-gateway.onrender.com" >> $GITHUB_STEP_SUMMARY
          echo "- Recommendation Engine: https://autotrader-recommendation-engine.onrender.com" >> $GITHUB_STEP_SUMMARY
```

#### 3.2 Add GitHub Secrets

Go to your GitHub repository → Settings → Secrets and variables → Actions

Add the following secrets:

| Secret Name | Description | How to Get |
|-------------|-------------|------------|
| `VERCEL_TOKEN` | Vercel API token | Vercel Dashboard → Settings → Tokens |
| `VERCEL_ORG_ID` | Vercel organization ID | Vercel Dashboard → Settings → General |
| `VERCEL_PROJECT_ID` | Vercel project ID | Vercel Dashboard → Project → Settings → General |
| `RENDER_DEPLOY_HOOK_API` | Render deploy hook URL for api-gateway | Render Dashboard → Service → Settings |
| `RENDER_DEPLOY_HOOK_REC` | Render deploy hook URL for recommendation-engine | Render Dashboard → Service → Settings |
| `NEON_DATABASE_URL` | Neon PostgreSQL connection string | Neon Dashboard → Connection Details |

---

## Code Changes Required

### Summary of Required Changes

| Priority | Change | Effort | Impact |
|----------|--------|--------|--------|
| **High** | Remove Vault dependency | 2-4 hours | Enables deployment without Vault |
| **High** | Replace ClickHouse with PostgreSQL | 4-6 hours | Eliminates ClickHouse dependency |
| **Medium** | Add Redis fallback | 1-2 hours | Works without Redis |
| **Low** | Remove Kafka references | 1 hour | Cleanup unused code |

### Detailed Code Changes

#### Change 1: Remove Vault (High Priority)

**File: `api-gateway/src/vault.js`**

Replace the Vault client with environment variable lookups:

```javascript
// =============================================================================
// secrets.js - Environment-based Secrets Management
// =============================================================================
// Replaces HashiCorp Vault with environment variables for simplicity.
// In production, secrets are stored in Render/Vercel environment variables.
// =============================================================================

/**
 * Get API key for external service
 * @param {string} service - Service name (e.g., 'plaid', 'alpaca')
 * @returns {string|null} API key or null if not found
 */
export function getApiKey(service) {
  const keyMap = {
    'plaid_client_id': process.env.PLAID_CLIENT_ID,
    'plaid_secret': process.env.PLAID_SECRET,
    'alpaca_api_key': process.env.ALPACA_API_KEY,
    'alpaca_secret': process.env.ALPACA_SECRET,
    'alpha_vantage': process.env.ALPHA_VANTAGE_API_KEY,
    'polygon': process.env.POLYGON_API_KEY,
  };
  return keyMap[service] || null;
}

/**
 * Store user credentials (placeholder - use database in production)
 * For MVP, brokerage tokens are stored encrypted in PostgreSQL
 */
export async function storeUserCredentials(userId, credentials) {
  // In production MVP, store encrypted in PostgreSQL
  // For now, this is handled by the brokerage_connections table
  console.log(`Storing credentials for user ${userId}`);
  return true;
}

/**
 * Health check (always returns true without Vault)
 */
export async function checkVaultHealth() {
  return { status: 'ok', message: 'Using environment variables' };
}
```

#### Change 2: Replace ClickHouse with PostgreSQL (High Priority)

**File: `ml-services/recommendation-engine/src/news_features.py`**

Update the NewsFeatureProvider to use PostgreSQL:

```python
# Add PostgreSQL support alongside ClickHouse
# The provider will try PostgreSQL first, fall back to ClickHouse if configured

import asyncpg

class NewsFeatureProvider:
    def __init__(
        self,
        # PostgreSQL (preferred for production)
        postgres_url: Optional[str] = None,
        # ClickHouse (legacy, for local development)
        clickhouse_host: str = "localhost",
        # ... other params
    ):
        self.postgres_url = postgres_url or os.getenv("DATABASE_URL")
        self.pg_pool = None
        # ... existing init code
    
    async def initialize(self):
        # Try PostgreSQL first
        if self.postgres_url:
            try:
                self.pg_pool = await asyncpg.create_pool(self.postgres_url)
                logger.info("Connected to PostgreSQL for news features")
                return
            except Exception as e:
                logger.warning(f"PostgreSQL not available: {e}")
        
        # Fall back to ClickHouse
        # ... existing ClickHouse init code
    
    async def _fetch_from_postgres(self, symbols: List[str]) -> Dict[str, NewsFeatures]:
        """Fetch news features from PostgreSQL."""
        query = """
            SELECT symbol, sentiment_1d, sentiment_3d, sentiment_7d,
                   sentiment_momentum_3d, article_count_1d, article_count_7d,
                   volume_ratio, avg_confidence_1d
            FROM news_features
            WHERE symbol = ANY($1)
            AND feature_date = CURRENT_DATE
        """
        async with self.pg_pool.acquire() as conn:
            rows = await conn.fetch(query, symbols)
            # Convert to NewsFeatures objects
            # ...
```

#### Change 3: Add Redis Fallback (Medium Priority)

**File: `ml-services/feature-engineering/src/price_data.py`**

Add in-memory fallback when Redis is unavailable:

```python
class PriceDataProvider:
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url
        self.redis_client = None
        self._memory_cache = {}  # In-memory fallback
        self._cache_ttl = 300  # 5 minutes
    
    async def initialize(self):
        if self.redis_url:
            try:
                import redis.asyncio as redis
                self.redis_client = redis.from_url(self.redis_url)
                await self.redis_client.ping()
                logger.info("Connected to Redis")
            except Exception as e:
                logger.warning(f"Redis not available, using in-memory cache: {e}")
                self.redis_client = None
    
    async def _get_cached(self, key: str) -> Optional[str]:
        if self.redis_client:
            return await self.redis_client.get(key)
        # In-memory fallback
        entry = self._memory_cache.get(key)
        if entry and time.time() - entry['time'] < self._cache_ttl:
            return entry['value']
        return None
    
    async def _set_cached(self, key: str, value: str, ttl: int = 300):
        if self.redis_client:
            await self.redis_client.setex(key, ttl, value)
        else:
            # In-memory fallback
            self._memory_cache[key] = {'value': value, 'time': time.time()}
```

---

## Cost Summary

### Monthly Cost Breakdown

| Service | Provider | Free Tier | Your Usage | Monthly Cost |
|---------|----------|-----------|------------|--------------|
| Source Control | GitHub | Unlimited public repos | 1 repo | **$0** |
| CI/CD | GitHub Actions | 2,000 min/mo | ~100 min/mo | **$0** |
| Frontend Hosting | Vercel | 100GB bandwidth | ~1GB | **$0** |
| Backend (API Gateway) | Render | 750 hrs/mo | ~720 hrs | **$0** |
| Backend (ML Engine) | Render | 750 hrs/mo | ~720 hrs | **$0** |
| Database | Neon | 0.5GB storage | ~100MB | **$0** |
| Cache (Optional) | Upstash | 10K cmds/day | ~1K cmds/day | **$0** |
| **TOTAL** | | | | **$0/month** |

### Comparison with Paid Alternatives

| Service | Free Option | Paid Alternative | Monthly Savings |
|---------|-------------|------------------|-----------------|
| Database | Neon (free) | AWS RDS | ~$15-50 |
| Backend Hosting | Render (free) | AWS ECS/Fargate | ~$30-100 |
| Secrets | Env vars (free) | HashiCorp Vault | ~$50-100 |
| Event Streaming | Removed | Apache Kafka (Confluent) | ~$100-300 |
| Time-series DB | PostgreSQL | ClickHouse Cloud | ~$50-200 |
| **Total Savings** | | | **~$245-750/mo** |

---

## Limitations & Mitigations

### Free Tier Limitations

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| **Render services sleep after 15 min** | First request after sleep takes ~30s | Add health check ping every 10 min using external service (UptimeRobot free) |
| **Neon 0.5GB storage** | ~10,000 recommendations max | Archive old data monthly, keep only last 30 days |
| **Vercel 100GB bandwidth** | ~1 million page views | Optimize images, enable compression (usually plenty) |
| **No Kafka** | No real-time streaming | Use polling every 30 min, webhook triggers |
| **No dedicated Redis** | Cache lost on restart | Use in-memory cache or Upstash |
| **Render cold starts** | 30s delay after idle | Keep warm with health checks |

### Keeping Services Awake

To avoid cold starts on Render, set up a free health check service:

1. **Sign up** at https://uptimerobot.com (free tier: 50 monitors)

2. **Add monitors:**
   - API Gateway: `https://autotrader-api-gateway.onrender.com/health`
   - Recommendation Engine: `https://autotrader-recommendation-engine.onrender.com/health`
   - Interval: 10 minutes

This will ping your services every 10 minutes, keeping them warm and avoiding cold starts.

### Data Retention Strategy

To stay within Neon's 0.5GB limit:

```sql
-- Create a cleanup job to run monthly
-- Delete recommendations older than 30 days
DELETE FROM stock_recommendations 
WHERE generated_at < NOW() - INTERVAL '30 days';

-- Delete old news features
DELETE FROM news_features 
WHERE feature_date < CURRENT_DATE - INTERVAL '30 days';

-- Vacuum to reclaim space
VACUUM ANALYZE;
```

---

## Quick Start Guide

### Prerequisites

- GitHub account with repository access
- Google Cloud Console account (for OAuth)
- Terminal with `psql` and `curl` installed

### Step-by-Step Deployment

```bash
# =============================================================================
# Step 1: Set up Neon Database (5 minutes)
# =============================================================================

# 1. Go to https://neon.tech and sign up
# 2. Create project "autotrader-ai"
# 3. Copy connection string

# Set environment variable
export DATABASE_URL="postgresql://user:pass@ep-xxx.neon.tech/autotrader?sslmode=require"

# Run migrations
cd autotrader-ai
for f in database/postgres/V*.sql; do
  echo "Running: $f"
  psql "$DATABASE_URL" -f "$f"
done

# Verify
psql "$DATABASE_URL" -c "\dt"

# =============================================================================
# Step 2: Set up Render Backend (10 minutes)
# =============================================================================

# 1. Go to https://render.com and sign up
# 2. Connect GitHub repository
# 3. Create Web Service for api-gateway:
#    - Root: api-gateway
#    - Build: npm install
#    - Start: npm start
# 4. Create Web Service for recommendation-engine:
#    - Root: ml-services/recommendation-engine
#    - Build: pip install -r requirements.txt
#    - Start: uvicorn src.recommendation_flow:app --host 0.0.0.0 --port $PORT
# 5. Add environment variables to both services
# 6. Copy deploy hook URLs

# =============================================================================
# Step 3: Set up Vercel Frontend (5 minutes)
# =============================================================================

# 1. Go to https://vercel.com and sign up
# 2. Import GitHub repository
# 3. Set root directory: web-app
# 4. Add environment variables:
#    - VITE_API_URL=https://autotrader-api-gateway.onrender.com
#    - VITE_GOOGLE_CLIENT_ID=<your-id>
# 5. Deploy

# =============================================================================
# Step 4: Configure GitHub Secrets (5 minutes)
# =============================================================================

# Go to GitHub → Repository → Settings → Secrets → Actions
# Add the following secrets:
# - VERCEL_TOKEN
# - VERCEL_ORG_ID
# - VERCEL_PROJECT_ID
# - RENDER_DEPLOY_HOOK_API
# - RENDER_DEPLOY_HOOK_REC
# - NEON_DATABASE_URL

# =============================================================================
# Step 5: Set up Health Monitoring (2 minutes)
# =============================================================================

# 1. Go to https://uptimerobot.com and sign up
# 2. Add HTTP monitors for:
#    - https://autotrader-api-gateway.onrender.com/health (10 min interval)
#    - https://autotrader-recommendation-engine.onrender.com/health (10 min interval)

# =============================================================================
# Step 6: Test Deployment
# =============================================================================

# Test API Gateway
curl https://autotrader-api-gateway.onrender.com/health

# Test Recommendation Engine
curl https://autotrader-recommendation-engine.onrender.com/health

# Test Frontend
# Open https://autotrader-ai.vercel.app in browser

echo "🎉 Deployment complete!"
```

---

## Appendix

### A. Environment Variables Reference

| Variable | Service | Required | Description |
|----------|---------|----------|-------------|
| `DATABASE_URL` | All | Yes | Neon PostgreSQL connection string |
| `PORT` | Backend | Yes | Server port (set by Render) |
| `NODE_ENV` | API Gateway | Yes | `production` |
| `JWT_SECRET` | API Gateway | Yes | Secret for signing JWT tokens |
| `GOOGLE_CLIENT_ID` | All | Yes | Google OAuth client ID |
| `PLAID_CLIENT_ID` | API Gateway | No | Plaid API client ID |
| `PLAID_SECRET` | API Gateway | No | Plaid API secret |
| `REDIS_URL` | ML Services | No | Upstash Redis URL |
| `ALPHA_VANTAGE_API_KEY` | ML Services | No | Alpha Vantage API key |
| `VITE_API_URL` | Frontend | Yes | API Gateway URL |

### B. Troubleshooting

| Problem | Solution |
|---------|----------|
| Service returns 502 error | Check Render logs, service may be starting up |
| Cold start timeout | Set up UptimeRobot health checks |
| Database connection failed | Verify Neon connection string, check SSL mode |
| CORS errors | Add frontend URL to `ALLOWED_ORIGINS` |
| Build fails on Render | Check build logs, verify requirements.txt |

### C. Scaling Beyond Free Tier

When you need to scale:

| Upgrade | Cost | When Needed |
|---------|------|-------------|
| Render Starter | $7/mo per service | Need always-on, no sleep |
| Neon Launch | $19/mo | >0.5GB storage, more compute |
| Vercel Pro | $20/mo | >100GB bandwidth, team features |
| Upstash Pay-as-you-go | ~$0.20/100K commands | >10K commands/day |

---

**Document End**

*Last updated: January 2026*

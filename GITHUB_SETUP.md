# AutoTrader AI - GitHub Setup Guide

## Prerequisites

1. GitHub account
2. Git installed locally
3. SSH key configured (or use HTTPS with token)

## Step-by-Step Setup

### 1. Create Repository on GitHub

1. Go to https://github.com/new
2. Repository name: `autotrader-ai`
3. Description: `AI-Powered Trading Intelligence Platform`
4. Choose public or private
5. DO NOT initialize with README (we have one)
6. Click "Create repository"

### 2. Add Remote and Push

```bash
cd ~/autotrader-ai

# Add remote repository
git remote add origin https://github.com/YOUR_USERNAME/autotrader-ai.git
# OR with SSH:
git remote add origin git@github.com:YOUR_USERNAME/autotrader-ai.git

# Verify remote
git remote -v

# Push to GitHub
git push -u origin main
```

### 3. Configure Branch Protection (Recommended)

On GitHub:
1. Go to Settings → Branches
2. Add rule for `main` branch
3. Enable:
   - Require pull request reviews (1 approval)
   - Require status checks to pass
   - Include administrators
4. Save changes

### 4. Set Up GitHub Secrets

For CI/CD to work, add these secrets in Settings → Secrets and variables:

```
DOCKER_USERNAME      - Docker Hub username
DOCKER_PASSWORD      - Docker Hub token
GOOGLE_CLIENT_ID     - OAuth 2.0 client ID
GOOGLE_CLIENT_SECRET - OAuth 2.0 client secret
JWT_SECRET           - JWT signing secret (min 32 chars)
```

### 5. Configure GitHub Actions

Actions are already configured in `.github/workflows/`:
- `build.yml` - Runs on every push/PR
- `deploy.yml` - Runs on main branch push

## Local Development Workflow

```bash
# Start development
make start

# Create feature branch
git checkout -b feature/your-feature-name

# Make changes and test
make test

# Commit changes
git add .
git commit -m "feat: your feature description"

# Push to GitHub
git push origin feature/your-feature-name

# Create Pull Request on GitHub
# Wait for CI checks to pass
# Request review from team
```

## Command Reference

```bash
# View git status
git status

# View commit history
git log --oneline

# View remote configuration
git remote -v

# Update remote URL
git remote set-url origin NEW_URL
```

## Troubleshooting

### Authentication Issues
```bash
# Using SSH
ssh -T git@github.com

# Using HTTPS with token
git config --global credential.helper store
```

### Push Rejected
```bash
# If branch is out of sync
git pull origin main
git push origin main
```

### Large Files
If you need to commit large files, consider using Git LFS:
```bash
git lfs install
git lfs track "*.bin"
```

## Repository Structure Reference

```
autotrader-ai/
├── services/              # Java/Spring Boot microservices
├── web-app/               # React TypeScript frontend
├── ml-services/           # Python ML services
├── infrastructure/        # Docker, Kubernetes, Terraform
├── database/              # Database schemas
├── .github/              # GitHub workflows and configs
├── docs/                 # Documentation
└── scripts/              # Utility scripts
```

## Next Steps

1. ✅ Repository initialized locally
2. ⏭️  Create repository on GitHub
3. ⏭️  Push to GitHub
4. ⏭️  Configure branch protection
5. ⏭️  Add GitHub secrets
6. ⏭️  Start developing!

## Additional Resources

- [GitHub Docs](https://docs.github.com)
- [Git Documentation](https://git-scm.com/doc)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)

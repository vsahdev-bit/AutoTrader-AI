# Contributing to AutoTrader AI

## Code Style

### Java/Spring Boot
- Follow Google Java Style Guide
- Use meaningful variable names
- Write unit tests for all public methods
- Use `mvn verify` to check code quality

### TypeScript/React
- Use ESLint configuration provided
- Follow 2-space indentation
- Use functional components and hooks
- Write tests for components

### Python
- Follow PEP 8
- Use type hints
- Write docstrings for all functions
- Run `black` formatter

## Git Workflow

1. Create a feature branch from `develop`
2. Make atomic commits with clear messages
3. Push to your fork
4. Create a Pull Request to `develop`
5. Address review comments
6. Merge after approval

## Commit Message Format

```
type(scope): subject

body

footer
```

Types: feat, fix, docs, style, refactor, test, chore

## Running Tests

```bash
make test
```

## Local Development

```bash
make start
```

## Security

- Never commit secrets or credentials
- Use `.env` files (not committed)
- Report security issues privately

# Changelog

## v1.0.0 (2026-05-07)

### Added
- Production-ready backend with FastAPI, SQLAlchemy 2.0, and Pydantic v2
- Repository pattern for clean data access
- Auth middleware with JWT validation via Logto
- Multi-model AI support: Ollama (local) + OpenRouter (cloud)
- PII shield integration before cloud API calls
- Comprehensive test suite: 17 tests (unit + integration)
- Health check endpoints (`/health`, `/health/detailed`)
- Real documentation for all sections
- Production Helm chart with HPA, TLS, and CloudNativePG

### Changed
- Restructured backend to standard DClaw layout (`app/core/`, `app/models/`, `app/schemas/`, `app/repositories/`, `app/services/`, `app/api/v1/`)
- Updated pyproject.toml to v1.0.0 with proper hatchling config
- Migrated from deprecated Pydantic `class Config` to `ConfigDict`

### Fixed
- All integration tests now pass with auth override
- Ollama model availability check now references correct constant

## v0.1.0 (2026-05-01)

### Added
- Initial scaffold with Next.js frontend and FastAPI backend
- Basic conversation and message models
- Mock API endpoints
- Helm chart skeleton
- Tauri desktop wrapper

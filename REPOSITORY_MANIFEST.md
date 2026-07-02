# Repository Manifest

## Purpose

This manifest documents the StageFlow repository structure, repository-level files, and ownership by Engineering Directive.

## Directories

| Path | Purpose | Owning Engineering Directive | Notes |
| --- | --- | --- | --- |
| `.` | Repository root for StageFlow governance, specifications, and future implementation. | ED-0001 | Contains root-level project and governance documents. |
| `.github/` | GitHub repository governance and future automation metadata. | ED-0001 | Workflows are reserved for future directives. |
| `.github/workflows/` | Reserved location for GitHub Actions workflows. | ED-0001 | No workflows are created by ED-0001. |
| `architecture/` | Implementation-facing architecture support material. | ED-0001 | Complements, but does not replace, canonical architecture docs. |
| `assets/` | Versioned static assets for documentation, examples, or future product surfaces. | ED-0001 | Runtime media remains excluded by `.gitignore`. |
| `backend/` | Python FastAPI backend workspace. | ED-0002 | Managed with `uv`; contains no StageFlow business logic in ED-0002. |
| `backend/app/` | Backend application package root. | ED-0002 | Contains API, context, shared, core, and bootstrap packages. |
| `backend/app/api/` | HTTP interface layer. | ED-0002 | Exposes only the versioned health endpoint in ED-0002. |
| `backend/app/api/v1/` | Version 1 API routes. | ED-0002 | Contains `GET /api/v1/health`. |
| `backend/app/bootstrap/` | Reserved backend composition package. | ED-0002 | No bootstrap behavior beyond app creation in ED-0002. |
| `backend/app/contexts/` | StageFlow bounded context package root. | ED-0002 | Context package boundaries only; no domain behavior. |
| `backend/app/contexts/editorial/` | Editorial context package boundary. | ED-0002 | Empty package boundary. |
| `backend/app/contexts/events/` | Event Management context package boundary. | ED-0002 | Empty package boundary. |
| `backend/app/contexts/identity/` | Identity & Access context package boundary. | ED-0002 | Empty package boundary. |
| `backend/app/contexts/integration/` | Integration context package boundary. | ED-0002 | Empty package boundary. |
| `backend/app/contexts/packaging/` | Packaging & Delivery context package boundary. | ED-0002 | Empty package boundary. |
| `backend/app/contexts/production/` | Production context package boundary. | ED-0002 | Empty package boundary. |
| `backend/app/contexts/publishing/` | Publishing & Analytics context package boundary. | ED-0002 | Empty package boundary. |
| `backend/app/contexts/rendering/` | Media Rendering context package boundary. | ED-0002 | Empty package boundary. |
| `backend/app/contexts/simulation/` | Simulation context package boundary. | ED-0002 | Empty package boundary. |
| `backend/app/core/` | Backend process concerns below domain layers. | ED-0002 | Contains config, health, lifecycle, and logging packages. |
| `backend/app/core/config/` | Backend configuration loading. | ED-0002 | Minimal service metadata only. |
| `backend/app/core/health/` | Minimal health response support. | ED-0002 | No dependency checks. |
| `backend/app/core/lifecycle/` | FastAPI lifecycle hook. | ED-0002 | No external resource initialization. |
| `backend/app/core/logging/` | Minimal logging setup. | ED-0002 | Standard logging only. |
| `backend/app/shared/` | Domain-neutral shared primitives package root. | ED-0002 | Package boundaries only. |
| `backend/app/shared/domain_events/` | Reserved domain event primitives package. | ED-0002 | No event behavior. |
| `backend/app/shared/errors/` | Reserved shared errors package. | ED-0002 | No error primitives yet. |
| `backend/app/shared/ids/` | Reserved shared identifiers package. | ED-0002 | No ID primitives yet. |
| `backend/app/shared/result/` | Reserved shared result package. | ED-0002 | No result primitives yet. |
| `backend/app/shared/time/` | Reserved shared time package. | ED-0002 | No time helpers yet. |
| `backend/tests/` | Backend test suite. | ED-0002 | Contains minimal health endpoint coverage. |
| `docs/` | Canonical and supporting architecture documentation. | Existing architecture work | Preserved by ED-0001. |
| `examples/` | Future examples that demonstrate approved implementation patterns. | ED-0001 | No application examples are created by ED-0001. |
| `mock_data/` | Future safe synthetic fixtures and mock data. | ED-0001 | Real production or event data does not belong here. |
| `reference/` | Future non-authoritative reference material. | ED-0001 | Canonical specifications remain in root files and `docs/`. |
| `scripts/` | Future repository maintenance and developer utility scripts. | ED-0001 | No scripts are created by ED-0001. |
| `tests/` | Future automated tests. | ED-0001 | No tests or test runner configuration are created by ED-0001. |

## Repository-Level Files

| Path | Purpose | Owning Engineering Directive | Notes |
| --- | --- | --- | --- |
| `.editorconfig` | Shared editor formatting defaults. | ED-0001 | Covers common Python, TypeScript, Markdown, YAML, and JSON conventions. |
| `.env.example` | Example environment file. | Existing repository work | Preserved by ED-0001. |
| `.gitattributes` | Git text and binary file handling rules. | Existing repository work | Preserved by ED-0001. |
| `.gitignore` | Ignored local, generated, runtime, and dependency files. | Existing repository work | Preserved by ED-0001. |
| `ARCHITECTURE_DECISIONS.md` | Architecture Decision Record index. | ED-0001 | Initialized with ADR-0001 through ADR-0005. |
| `CHANGELOG.md` | Future release and change history. | Existing repository work | Preserved by ED-0001. |
| `CONTRIBUTING.md` | Initial contributor guide and engineering process expectations. | ED-0001 | Establishes specification-first contribution rules. |
| `ENGINEERING_DIRECTIVES.md` | Engineering Directive index. | ED-0001 | Registers ED-0001 and reserves ED-0002 through ED-0005. |
| `IMPLEMENTATION_PLAN.md` | High-level staged implementation plan. | ED-0001 | Governance only; no implementation detail. |
| `LICENSE` | Repository license. | ED-0001 | MIT License. |
| `PRODUCT_CONSTITUTION.md` | Canonical product constitution. | Existing architecture work | Preserved by ED-0001. |
| `README.md` | Repository introduction. | Existing repository work | Preserved by ED-0001. |
| `REPOSITORY_MANIFEST.md` | Repository structure and ownership manifest. | ED-0001 | Created by ED-0001. |
| `ROADMAP.md` | Future roadmap document. | Existing repository work | Preserved by ED-0001. |

## Backend Files

| Path | Purpose | Owning Engineering Directive | Notes |
| --- | --- | --- | --- |
| `backend/.python-version` | Declares the backend Python version. | ED-0002 | Uses Python 3.13. |
| `backend/README.md` | Backend workspace guide. | ED-0002 | Documents local setup, health route, and quality commands. |
| `backend/pyproject.toml` | Backend Python project and tooling configuration. | ED-0002 | Defines FastAPI, Pydantic, Ruff, Pyright, and Pytest setup managed by `uv`. |
| `backend/uv.lock` | Locked backend dependency graph. | ED-0002 | Generated by `uv sync --dev`. |
| `backend/app/__init__.py` | Backend application package marker. | ED-0002 | No business logic. |
| `backend/app/main.py` | Minimal FastAPI app factory and app instance. | ED-0002 | Registers only the API v1 router. |
| `backend/app/api/__init__.py` | API package marker. | ED-0002 | No business logic. |
| `backend/app/api/README.md` | API package guide. | ED-0002 | Documents HTTP interface boundary. |
| `backend/app/api/v1/__init__.py` | API v1 package marker. | ED-0002 | No business logic. |
| `backend/app/api/v1/README.md` | API v1 package guide. | ED-0002 | Documents the ED-0002 health-only scope. |
| `backend/app/api/v1/health.py` | Health route. | ED-0002 | Exposes `GET /api/v1/health`. |
| `backend/app/api/v1/router.py` | API v1 router composition. | ED-0002 | Includes only the health router. |
| `backend/app/bootstrap/__init__.py` | Bootstrap package marker. | ED-0002 | Reserved for future composition. |
| `backend/app/bootstrap/README.md` | Bootstrap package guide. | ED-0002 | Documents reserved scope. |
| `backend/app/core/config/settings.py` | Minimal configuration loader. | ED-0002 | Loads service metadata only. |
| `backend/app/core/health/service.py` | Minimal health response model and function. | ED-0002 | No dependency checks. |
| `backend/app/core/lifecycle/lifespan.py` | FastAPI lifespan hook. | ED-0002 | Sets process readiness only. |
| `backend/app/core/logging/configure.py` | Minimal logging configuration. | ED-0002 | Standard logging only. |
| `backend/tests/README.md` | Backend test suite guide. | ED-0002 | Documents health-only coverage. |
| `backend/tests/test_health.py` | Health endpoint test. | ED-0002 | Verifies startup through FastAPI TestClient. |

## Documentation Files

| Path | Purpose | Owning Engineering Directive | Notes |
| --- | --- | --- | --- |
| `docs/00_Glossary.md` | Shared terminology. | Existing architecture work | Preserved by ED-0001. |
| `docs/00.5_Domain_Model.md` | StageFlow domain model. | Existing architecture work | Preserved by ED-0001. |
| `docs/03.5_Technology_Selections.md` | Technology selections specification. | Existing architecture work | Empty at ED-0002 implementation time; preserved by ED-0002. |
| `docs/03.6_Architecture_Layers.md` | Architecture Layers specification. | Existing architecture work | Preserved by ED-0001. |
| `docs/04.5_Bounded_Contexts.md` | Bounded Contexts specification. | Existing architecture work | Preserved by ED-0001. |
| `docs/04.6_Integration_Architecture.md` | Integration Architecture specification. | Existing architecture work | Preserved by ED-0001. |

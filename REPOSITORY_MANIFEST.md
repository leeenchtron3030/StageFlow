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
| `backend/app/shared/` | Domain-neutral shared primitives package root. | ED-0002 / ED-0004 | ED-0004 populates generic shared contracts. |
| `backend/app/shared/domain_events/` | Base domain event contract package. | ED-0004 | Contains only generic event primitives. |
| `backend/app/shared/errors/` | Structured shared error package. | ED-0004 | Contains generic error categories only. |
| `backend/app/shared/ids/` | Shared identifier package. | ED-0004 | Contains generic entity and correlation IDs only. |
| `backend/app/shared/result/` | Shared result package. | ED-0004 | Contains explicit success/failure result contract. |
| `backend/app/shared/time/` | Shared time package. | ED-0004 | Contains clocks, timestamp alias, and time range. |
| `backend/tests/` | Backend test suite. | ED-0002 / ED-0004 | Contains health endpoint and shared contract coverage. |
| `docs/` | Canonical and supporting architecture documentation. | Existing architecture work | Preserved by ED-0001. |
| `examples/` | Future examples that demonstrate approved implementation patterns. | ED-0001 | No application examples are created by ED-0001. |
| `frontend/` | Next.js frontend workspace. | ED-0003 | Contains no backend communication or business logic in ED-0003. |
| `frontend/app/` | Next.js App Router root. | ED-0003 | Contains only the root layout, root page, and global styles. |
| `frontend/src/` | Frontend source package root. | ED-0003 | Organized around frontend foundations and future workflows. |
| `frontend/src/components/` | Shared frontend component package. | ED-0003 | No components generated in ED-0003. |
| `frontend/src/core/` | Frontend application-wide foundations. | ED-0003 | Reserved for future providers and configuration. |
| `frontend/src/layouts/` | Reusable layout package. | ED-0003 | Reserved for future workflow layouts. |
| `frontend/src/routes/` | Route metadata and route support package. | ED-0003 | No additional routes in ED-0003. |
| `frontend/src/shared/` | Shared frontend utilities and contract package. | ED-0003 / ED-0004 | ED-0004 populates generic shared contracts. |
| `frontend/src/shared/domain-events/` | Frontend base domain event contract package. | ED-0004 | Contains only generic event types. |
| `frontend/src/shared/errors/` | Frontend structured error package. | ED-0004 | Contains generic error categories only. |
| `frontend/src/shared/ids/` | Frontend shared identifier package. | ED-0004 | Contains generic entity and correlation IDs only. |
| `frontend/src/shared/result/` | Frontend shared result package. | ED-0004 | Contains explicit success/failure result type. |
| `frontend/src/shared/time/` | Frontend shared time package. | ED-0004 | Contains clock and time range contracts. |
| `frontend/src/styles/` | Frontend styling foundation package. | ED-0003 | Contains initial design token module. |
| `frontend/src/themes/` | Theme architecture package. | ED-0003 | Reserved for future white-label theme work. |
| `frontend/src/workflows/` | Workflow-oriented frontend package root. | ED-0003 | Package boundaries only; no workflow implementation. |
| `frontend/src/workflows/content_lead/` | Content Lead workflow package boundary. | ED-0003 | Empty boundary with README only. |
| `frontend/src/workflows/package_delivery/` | Package Delivery workflow package boundary. | ED-0003 | Empty boundary with README only. |
| `frontend/src/workflows/reviewer/` | Reviewer workflow package boundary. | ED-0003 | Empty boundary with README only. |
| `frontend/src/workflows/simulation/` | Simulation workflow package boundary. | ED-0003 | Empty boundary with README only. |
| `frontend/src/workflows/technical_director/` | Technical Director workflow package boundary. | ED-0003 | Empty boundary with README only. |
| `frontend/tests/` | Frontend test package. | ED-0003 | No test runner added in ED-0003. |
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
| `.gitignore` | Ignored local, generated, runtime, and dependency files. | Existing repository work / ED-0003 | ED-0003 adds TypeScript build cache ignore coverage. |
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
| `backend/app/shared/domain_events/domain_event.py` | Base domain event contract. | ED-0004 | Generic event ID, type, timestamp, correlation, actor, and metadata. |
| `backend/app/shared/errors/errors.py` | Structured error contracts. | ED-0004 | Generic error categories only. |
| `backend/app/shared/ids/correlation_id.py` | Correlation ID contract. | ED-0004 | Generic UUID-compatible workflow tracing ID. |
| `backend/app/shared/ids/entity_id.py` | Entity ID contract. | ED-0004 | Generic UUID-compatible entity ID. |
| `backend/app/shared/result/result.py` | Result contract. | ED-0004 | Explicit success/failure result. |
| `backend/app/shared/time/clock.py` | Clock contracts. | ED-0004 | System and fixed clocks with UTC timestamps. |
| `backend/app/shared/time/time_range.py` | Time range contract. | ED-0004 | Immutable start/end/duration range. |
| `backend/tests/README.md` | Backend test suite guide. | ED-0002 | Documents health-only coverage. |
| `backend/tests/test_health.py` | Health endpoint test. | ED-0002 | Verifies startup through FastAPI TestClient. |
| `backend/tests/test_shared_contracts.py` | Shared contract tests. | ED-0004 | Covers backend contract primitives. |

## Frontend Files

| Path | Purpose | Owning Engineering Directive | Notes |
| --- | --- | --- | --- |
| `frontend/README.md` | Frontend workspace guide. | ED-0003 | Documents setup, commands, and frontend boundaries. |
| `frontend/package.json` | Frontend package scripts and dependencies. | ED-0003 | Defines Next.js, TypeScript, Tailwind, shadcn, TanStack Query, React Hook Form, and Zod dependencies. |
| `frontend/package-lock.json` | Locked frontend dependency graph. | ED-0003 | Generated by `npm install`. |
| `frontend/next.config.ts` | Next.js configuration. | ED-0003 | Minimal configuration. |
| `frontend/tsconfig.json` | TypeScript configuration. | ED-0003 | Strict TypeScript with Next.js plugin. |
| `frontend/postcss.config.mjs` | PostCSS configuration. | ED-0003 | Enables Tailwind CSS v4 PostCSS plugin. |
| `frontend/eslint.config.mjs` | ESLint flat configuration. | ED-0003 | Uses Next.js core web vitals and TypeScript configs. |
| `frontend/components.json` | shadcn/ui configuration. | ED-0003 | Initializes shadcn aliases and CSS variable mode without generating UI components. |
| `frontend/next-env.d.ts` | Next.js TypeScript environment declarations. | ED-0003 | Generated by Next.js. |
| `frontend/app/layout.tsx` | Root application layout. | ED-0003 | Minimal metadata and global style import. |
| `frontend/app/page.tsx` | Root page. | ED-0003 | Displays required ED-0003 placeholder information only. |
| `frontend/app/globals.css` | Global Tailwind and CSS variable foundation. | ED-0003 | Tailwind v4 CSS-first setup with semantic roles. |
| `frontend/src/shared/domain-events/domain-event.ts` | Frontend base domain event type. | ED-0004 | Generic event shape only. |
| `frontend/src/shared/errors/errors.ts` | Frontend structured error types and helpers. | ED-0004 | Generic error categories only. |
| `frontend/src/shared/ids/correlation-id.ts` | Frontend correlation ID type and helpers. | ED-0004 | Branded UUID-compatible string. |
| `frontend/src/shared/ids/entity-id.ts` | Frontend entity ID type and helpers. | ED-0004 | Branded UUID-compatible string. |
| `frontend/src/shared/result/result.ts` | Frontend result type and helpers. | ED-0004 | Explicit success/failure union. |
| `frontend/src/shared/time/clock.ts` | Frontend clock and timestamp contracts. | ED-0004 | System and fixed clock helpers. |
| `frontend/src/shared/time/time-range.ts` | Frontend time range type and helper. | ED-0004 | Immutable parseable timestamp range. |
| `frontend/src/styles/design_tokens.ts` | Initial design token module. | ED-0003 | Placeholder tokens for future theming and design system work. |

## Documentation Files

| Path | Purpose | Owning Engineering Directive | Notes |
| --- | --- | --- | --- |
| `docs/00_Glossary.md` | Shared terminology. | Existing architecture work | Preserved by ED-0001. |
| `docs/00.5_Domain_Model.md` | StageFlow domain model. | Existing architecture work | Preserved by ED-0001. |
| `docs/03.5_Technology_Selections.md` | Technology selections specification. | Existing architecture work | Empty at ED-0002 implementation time; preserved by ED-0002. |
| `docs/03.6_Architecture_Layers.md` | Architecture Layers specification. | Existing architecture work | Preserved by ED-0001. |
| `docs/04.5_Bounded_Contexts.md` | Bounded Contexts specification. | Existing architecture work | Preserved by ED-0001. |
| `docs/04.6_Integration_Architecture.md` | Integration Architecture specification. | Existing architecture work | Preserved by ED-0001. |

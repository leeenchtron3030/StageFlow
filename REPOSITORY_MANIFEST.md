# Repository Manifest

## Purpose

This manifest documents the StageFlow repository structure, repository-level files, and ownership by Engineering Directive.

## Architecture Releases

### AR-1.4 — Complete Reasoning Architecture

This Architecture Release completes the StageFlow reasoning architecture.

It formally establishes:

- Timeline
- Observation
- Evidence
- Hypothesis
- Finding
- Verification Decision

Operational Products are defined as downstream outputs of verified reasoning.

ED-0012 adds the first specialized Operational Product: the Session Window Product.

Subsequent Engineering Directives build on this completed reasoning model and specialized product foundation rather than extending the reasoning layer.

## Architecture Release AR-1.5

Clarifies terminology between reasoning-layer timeline artifacts and execution-layer operational products.

Introduces the concept:

Timeline Window Candidate

Clarifies that:

Session Window Product

is a specialized Operational Product produced after verification.

ED-0013 adds Production Events as the provider-agnostic runtime boundary before Observations.

ED-0014 adds Production Event Interpreters as the translation boundary from Production Events into Observations without extending into reasoning.

ED-0015 adds Production Event Dispatchers as the in-memory routing boundary from Production Events to matching Interpreters.

ED-0016 adds Recording System Adapter contracts as the first adapter-facing boundary that emits generic Production Events.

ED-0017 adds Media Artifact Adapter contracts for reporting artifact availability separately from recording activity and media ingestion.

ED-0018 adds Schedule Source Adapter contracts for planned activities, preserving separation between planned reality and observed reality.

ED-0019 adds Runtime Clock contracts as a time-boundary ingress source that emits generic Production Events without scheduling work.

ED-0020 adds Transcript Source Adapter contracts for transcript availability reporting, preserving the separation between words becoming available and later text meaning.

ED-0021 adds Vision Source Adapter contracts for visual detection reporting, preserving the separation between visual phenomena becoming available and later semantic meaning.

ED-0022 adds Operator Source Adapter contracts for intentional human input, preserving that human-supplied information enters the same reasoning pipeline as every other source.

ED-0023 adds explicit Observation Interpreter contracts for translating one or more Production Events into objective Observations without creating later reasoning artifacts.

## Architecture Release AR-2.0

AR-2.0 formalizes StageFlow as an observational intelligence system for live event media.

It documents the complete ingress architecture:

Observable Reality -> Production Events -> Dispatcher -> Interpreters -> Observations

It establishes Production Events as the universal ingress language across recording, media artifact, schedule, runtime clock, transcript, vision, and operator sources.

It also marks the transition from foundational architecture to observational intelligence: StageFlow observes recorded reality, incorporates supporting production signals, reasons transparently, and produces explainable operational products.

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
| `backend/app/contexts/production/` | Production context package. | ED-0002 / ED-0005 / ED-0012 / ED-0013 / ED-0014 / ED-0015 / ED-0016 / ED-0017 / ED-0018 / ED-0019 / ED-0020 / ED-0021 / ED-0022 / ED-0023 | ED-0005 adds production timeline contracts; ED-0012 adds the first specialized operational product; ED-0013 adds runtime input events; ED-0014 adds event interpreter contracts; ED-0015 adds event dispatcher contracts; ED-0016 adds recording adapter contracts; ED-0017 adds media artifact adapter contracts; ED-0018 adds schedule adapter contracts; ED-0019 adds runtime clock contracts; ED-0020 adds transcript adapter contracts; ED-0021 adds vision adapter contracts; ED-0022 adds operator adapter contracts; ED-0023 adds observation interpreter contracts. |
| `backend/app/contexts/production/dispatcher/` | Production event dispatcher contract package. | ED-0015 | Backend-only in-memory routing boundary from Production Events to matching interpreters; no interpretation, reasoning, infrastructure, persistence, APIs, adapters, or frontend behavior. |
| `backend/app/contexts/production/evidence/` | Production evidence contract package. | ED-0007 | Backend-only evidence primitives; no reasoning, proposals, or scoring policy. |
| `backend/app/contexts/production/finding/` | Production finding contract package. | ED-0009 | Backend-only human-reviewable reasoning artifacts; no verification or workflow behavior. |
| `backend/app/contexts/production/hypothesis/` | Production hypothesis contract package. | ED-0008 | Backend-only hypothesis primitives; no proposals, verification, or action behavior. |
| `backend/app/contexts/production/interpreter/` | Production event interpreter contract package. | ED-0014 | Backend-only translation boundary from Production Events to Observations; no adapters, reasoning, persistence, APIs, queues, workers, or frontend behavior. |
| `backend/app/contexts/production/media_artifact_adapter/` | Production media artifact adapter contract package. | ED-0017 | Backend-only adapter-facing artifact availability contracts that emit generic Production Events; no filesystem watching, ingestion, validation, chunk registration, persistence, APIs, queues, workers, or frontend behavior. |
| `backend/app/contexts/production/observation/` | Production observation contract package. | ED-0006 | Backend-only observation primitives; no reasoning or detection logic. |
| `backend/app/contexts/production/observation_interpreter/` | Production observation interpreter contract package. | ED-0023 | Backend-only AR-2.0 interpreter contracts for translating Production Events into objective Observations; no Evidence, Hypotheses, Findings, Verification Decisions, Operational Products, persistence, APIs, queues, workers, adapters, or frontend behavior. |
| `backend/app/contexts/production/operator_adapter/` | Production operator source adapter contract package. | ED-0022 | Backend-only intentional human input contracts that emit generic Production Events; no UI, authentication, permissions, workflows, review systems, correctness determination, reasoning, persistence, APIs, queues, workers, or frontend behavior. |
| `backend/app/contexts/production/operational_product/` | Production operational product contract package. | ED-0011 | Backend-only generic execution-layer primitives; no specialized products, persistence, APIs, queues, or workers. |
| `backend/app/contexts/production/production_event/` | Production event contract package. | ED-0013 | Backend-only provider-agnostic runtime input primitives; no adapters, observation generation, persistence, APIs, queues, workers, or frontend behavior. |
| `backend/app/contexts/production/recording_adapter/` | Production recording system adapter contract package. | ED-0016 | Backend-only adapter-facing recording activity contracts that emit generic Production Events; no provider integrations, media ingestion, persistence, APIs, queues, workers, or frontend behavior. |
| `backend/app/contexts/production/runtime_clock/` | Production runtime clock contract package. | ED-0019 | Backend-only time-boundary ingress contracts that emit generic Production Events; no scheduling infrastructure, retry execution, reconciliation, persistence, APIs, queues, workers, or frontend behavior. |
| `backend/app/contexts/production/schedule_adapter/` | Production schedule source adapter contract package. | ED-0018 | Backend-only planned-activity contracts that emit generic Production Events; no provider integrations, Sessions, Observations, reasoning, persistence, APIs, queues, workers, or frontend behavior. |
| `backend/app/contexts/production/session_window_product/` | Production session window product contract package. | ED-0012 | Backend-only specialized operational product connecting schedule references to verified timeline ranges; no Session aggregate, media storage, packages, persistence, APIs, or frontend behavior. |
| `backend/app/contexts/production/timeline/` | Production timeline contract package. | ED-0005 | Backend-only continuous recording and session window primitives. |
| `backend/app/contexts/production/transcript_adapter/` | Production transcript source adapter contract package. | ED-0020 | Backend-only transcript availability contracts that emit generic Production Events; no transcription execution, audio processing, model calls, text interpretation, persistence, APIs, queues, workers, or frontend behavior. |
| `backend/app/contexts/production/verification/` | Production verification protocol package. | ED-0010 | Backend-only append-only judgment records; no workflow or operational product behavior. |
| `backend/app/contexts/production/vision_adapter/` | Production vision source adapter contract package. | ED-0021 | Backend-only visual detection contracts that emit generic Production Events; no OCR, computer vision execution, model calls, semantic interpretation, persistence, APIs, queues, workers, or frontend behavior. |
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
| `backend/app/contexts/production/evidence/__init__.py` | Production evidence package exports. | ED-0007 | Exports evidence contracts. |
| `backend/app/contexts/production/evidence/evidence_item.py` | Evidence item contract. | ED-0007 | References an observation ID without embedding Observation objects. |
| `backend/app/contexts/production/evidence/evidence_purpose.py` | Evidence purpose categories. | ED-0007 | Potential future support purposes only. |
| `backend/app/contexts/production/evidence/evidence_set.py` | Evidence set contract. | ED-0007 | Groups one or more evidence items. |
| `backend/app/contexts/production/evidence/evidence_strength.py` | Evidence strength categories. | ED-0007 | Includes contradictory support as first-class evidence. |
| `backend/app/contexts/production/evidence/evidence_summary.py` | Evidence summary contract. | ED-0007 | Summarizes counts without final confidence. |
| `backend/app/contexts/production/dispatcher/__init__.py` | Production event dispatcher package exports. | ED-0015 | Exports dispatcher contracts. |
| `backend/app/contexts/production/dispatcher/README.md` | Production event dispatcher package guide. | ED-0015 | Documents routing responsibility and infrastructure exclusions. |
| `backend/app/contexts/production/dispatcher/dispatch_context.py` | Dispatch context contract. | ED-0015 | Lightweight routing context convertible to interpreter context. |
| `backend/app/contexts/production/dispatcher/dispatch_result.py` | Dispatch result contract. | ED-0015 | Aggregates invoked interpreter IDs and InterpreterResults unchanged. |
| `backend/app/contexts/production/dispatcher/dispatch_rule.py` | Dispatch rule contract. | ED-0015 | Declarative routing intent without execution or discovery. |
| `backend/app/contexts/production/dispatcher/dispatch_summary.py` | Dispatch summary contract. | ED-0015 | Lightweight diagnostics summary without dispatch execution or provider details. |
| `backend/app/contexts/production/dispatcher/production_event_dispatcher.py` | Production event dispatcher contract. | ED-0015 | Small in-memory router from Production Events to matching interpreters. |
| `backend/app/contexts/production/finding/__init__.py` | Production finding package exports. | ED-0009 | Exports finding contracts. |
| `backend/app/contexts/production/finding/finding.py` | Finding contract. | ED-0009 | Human-reviewable reasoning artifact referencing hypothesis IDs only. |
| `backend/app/contexts/production/finding/finding_confidence.py` | Finding confidence contract. | ED-0009 | Numeric confidence from `0.0` to `1.0`. |
| `backend/app/contexts/production/finding/finding_location.py` | Finding location contract. | ED-0009 | Point or range on the production timeline. |
| `backend/app/contexts/production/finding/finding_origin.py` | Finding origin categories. | ED-0009 | Generic reasoning pathways only. |
| `backend/app/contexts/production/finding/finding_summary.py` | Finding summary contract. | ED-0009 | Lightweight review-surface representation without workflow state. |
| `backend/app/contexts/production/finding/finding_support.py` | Finding support contract. | ED-0009 | References supporting, contradicting, and neutral hypothesis IDs. |
| `backend/app/contexts/production/finding/finding_type.py` | Finding type categories. | ED-0009 | Generic finding categories only. |
| `backend/app/contexts/production/hypothesis/__init__.py` | Production hypothesis package exports. | ED-0008 | Exports hypothesis contracts. |
| `backend/app/contexts/production/hypothesis/hypothesis.py` | Hypothesis contract. | ED-0008 | Represents a possible interpretation of evidence. |
| `backend/app/contexts/production/hypothesis/hypothesis_confidence.py` | Hypothesis confidence contract. | ED-0008 | Numeric confidence from `0.0` to `1.0`. |
| `backend/app/contexts/production/hypothesis/hypothesis_status.py` | Hypothesis status categories. | ED-0008 | Tentative lifecycle states only; not verification. |
| `backend/app/contexts/production/hypothesis/hypothesis_support.py` | Hypothesis support contract. | ED-0008 | References supporting, contradicting, and neutral evidence-set IDs. |
| `backend/app/contexts/production/hypothesis/hypothesis_type.py` | Hypothesis type categories. | ED-0008 | Tentative possible-meaning categories only. |
| `backend/app/contexts/production/interpreter/__init__.py` | Production event interpreter package exports. | ED-0014 | Exports interpreter contracts. |
| `backend/app/contexts/production/interpreter/README.md` | Production event interpreter package guide. | ED-0014 | Documents translation boundary scope and exclusions. |
| `backend/app/contexts/production/interpreter/interpreter_context.py` | Interpreter context contract. | ED-0014 | Lightweight interpretation context without adapter or persistence objects. |
| `backend/app/contexts/production/interpreter/interpreter_result.py` | Interpreter result contract. | ED-0014 | Traceable result containing zero or more Observations only. |
| `backend/app/contexts/production/interpreter/interpreter_rule.py` | Interpreter rule contract. | ED-0014 | Declarative event/source to intended Observation type description without executable logic. |
| `backend/app/contexts/production/interpreter/interpreter_status.py` | Interpreter status categories. | ED-0014 | Availability values for interpreters only. |
| `backend/app/contexts/production/interpreter/interpreter_summary.py` | Interpreter summary contract. | ED-0014 | Lightweight diagnostics summary without execution or provider internals. |
| `backend/app/contexts/production/interpreter/production_event_interpreter.py` | Production event interpreter contract. | ED-0014 | Generic matching and no-op interpretation contract from Production Events to InterpreterResults. |
| `backend/app/contexts/production/media_artifact_adapter/__init__.py` | Media artifact adapter package exports. | ED-0017 | Exports media artifact adapter contracts. |
| `backend/app/contexts/production/media_artifact_adapter/README.md` | Media artifact adapter package guide. | ED-0017 | Documents artifact reporting scope, generic Production Event mapping, and exclusions. |
| `backend/app/contexts/production/media_artifact_adapter/media_artifact_adapter.py` | Media artifact adapter contract. | ED-0017 | Generic adapter contract that emits Production Events only. |
| `backend/app/contexts/production/media_artifact_adapter/media_artifact_capability.py` | Media artifact adapter capability categories. | ED-0017 | Describes what artifact activity an adapter can report without implementing behavior. |
| `backend/app/contexts/production/media_artifact_adapter/media_artifact_event.py` | Media artifact event contract. | ED-0017 | Adapter-level artifact availability event with generic Production Event mapping helper. |
| `backend/app/contexts/production/media_artifact_adapter/media_artifact_identity.py` | Media artifact adapter identity contract. | ED-0017 | Provider-agnostic adapter identity and kind values. |
| `backend/app/contexts/production/media_artifact_adapter/media_artifact_status.py` | Media artifact status categories. | ED-0017 | Generic artifact availability values, not ingestion or validation state. |
| `backend/app/contexts/production/media_artifact_adapter/media_artifact_summary.py` | Media artifact adapter summary contract. | ED-0017 | Lightweight diagnostics summary without event creation or media inspection. |
| `backend/app/contexts/production/media_artifact_adapter/media_artifact_type.py` | Media artifact type categories. | ED-0017 | Broad artifact families without codec or provider-specific types. |
| `backend/app/contexts/production/timeline/__init__.py` | Production timeline package exports. | ED-0005 | Exports timeline contracts and statuses. |
| `backend/app/contexts/production/observation/__init__.py` | Production observation package exports. | ED-0006 | Exports observation contracts. |
| `backend/app/contexts/production/observation/observation.py` | Observation contract. | ED-0006 | Timestamped statement about something noticed on a recording timeline. |
| `backend/app/contexts/production/observation/observation_confidence.py` | Observation confidence contract. | ED-0006 | Numeric confidence from `0.0` to `1.0`. |
| `backend/app/contexts/production/observation/observation_location.py` | Observation location contract. | ED-0006 | Point or range on a production timeline. |
| `backend/app/contexts/production/observation/observation_source.py` | Observation source categories. | ED-0006 | Generic source categories only. |
| `backend/app/contexts/production/observation/observation_type.py` | Observation type categories. | ED-0006 | Generic observation types only; no conclusions. |
| `backend/app/contexts/production/observation_interpreter/__init__.py` | Observation interpreter package exports. | ED-0023 | Exports Observation Interpreter contracts. |
| `backend/app/contexts/production/observation_interpreter/README.md` | Observation interpreter package guide. | ED-0023 | Documents the Production Event to Observation boundary and relationship to ED-0014. |
| `backend/app/contexts/production/observation_interpreter/observation_interpreter.py` | Observation interpreter contract. | ED-0023 | Generic contract for translating one or more Production Events into objective Observations. |
| `backend/app/contexts/production/observation_interpreter/observation_interpreter_context.py` | Observation interpreter context contract. | ED-0023 | Lightweight context without adapter, persistence, or session aggregate objects. |
| `backend/app/contexts/production/observation_interpreter/observation_interpreter_policy.py` | Observation interpreter policy contract. | ED-0023 | Small policy settings without scoring, reasoning, or workflow behavior. |
| `backend/app/contexts/production/observation_interpreter/observation_interpreter_result.py` | Observation interpreter result contract. | ED-0023 | Traceable result containing source Production Event IDs and Observations only. |
| `backend/app/contexts/production/observation_interpreter/observation_interpreter_rule.py` | Observation interpreter rule contract. | ED-0023 | Declarative interpretation intent without execution or Observation creation. |
| `backend/app/contexts/production/observation_interpreter/observation_interpreter_summary.py` | Observation interpreter summary contract. | ED-0023 | Lightweight diagnostics summary without interpretation or provider details. |
| `backend/app/contexts/production/operator_adapter/__init__.py` | Operator source adapter package exports. | ED-0022 | Exports operator adapter contracts. |
| `backend/app/contexts/production/operator_adapter/README.md` | Operator source adapter package guide. | ED-0022 | Documents intentional human input reporting, Production Event mapping, and exclusions. |
| `backend/app/contexts/production/operator_adapter/operator_adapter_capability.py` | Operator adapter capability categories. | ED-0022 | Describes what operator input an adapter can report without implementing behavior. |
| `backend/app/contexts/production/operator_adapter/operator_adapter_identity.py` | Operator adapter identity contract. | ED-0022 | Generic adapter identity and kind values without provider names or UI assumptions. |
| `backend/app/contexts/production/operator_adapter/operator_adapter_summary.py` | Operator adapter summary contract. | ED-0022 | Lightweight diagnostics summary without workflow, event dispatch, or interpretation. |
| `backend/app/contexts/production/operator_adapter/operator_event.py` | Operator event contract. | ED-0022 | Adapter-level intentional human input event with generic Production Event mapping helper. |
| `backend/app/contexts/production/operator_adapter/operator_event_status.py` | Operator event status categories. | ED-0022 | Operator event lifecycle status values, not correctness states. |
| `backend/app/contexts/production/operator_adapter/operator_event_type.py` | Operator event type categories. | ED-0022 | Generic operator action categories without production conclusions. |
| `backend/app/contexts/production/operator_adapter/operator_source_adapter.py` | Operator source adapter contract. | ED-0022 | Generic operator adapter contract that emits Production Events only. |
| `backend/app/contexts/production/operational_product/__init__.py` | Production operational product package exports. | ED-0011 | Exports operational product contracts. |
| `backend/app/contexts/production/operational_product/operational_product.py` | Operational product contract. | ED-0011 | Generic downstream output of verified reasoning. |
| `backend/app/contexts/production/operational_product/operational_product_origin.py` | Operational product origin categories. | ED-0011 | Provider-agnostic execution-layer origins. |
| `backend/app/contexts/production/operational_product/operational_product_reference.py` | Operational product reference contract. | ED-0011 | Loose ID references to related objects. |
| `backend/app/contexts/production/operational_product/operational_product_status.py` | Operational product status categories. | ED-0011 | Execution lifecycle status for products only. |
| `backend/app/contexts/production/operational_product/operational_product_summary.py` | Operational product summary contract. | ED-0011 | Lightweight queue/dashboard summary without workflow policy. |
| `backend/app/contexts/production/operational_product/operational_product_type.py` | Operational product type categories. | ED-0011 | Broad product family categories only. |
| `backend/app/contexts/production/production_event/__init__.py` | Production event package exports. | ED-0013 | Exports production event contracts. |
| `backend/app/contexts/production/production_event/README.md` | Production event package guide. | ED-0013 | Documents runtime boundary scope and exclusions. |
| `backend/app/contexts/production/production_event/production_event.py` | Production event contract. | ED-0013 | Source-agnostic runtime input with occurred and received timestamps. |
| `backend/app/contexts/production/production_event/production_event_payload.py` | Production event payload contract. | ED-0013 | Immutable JSON-compatible runtime input data without provider-specific schema. |
| `backend/app/contexts/production/production_event/production_event_reference.py` | Production event reference contract. | ED-0013 | Lightweight ID or external string references without embedded target objects. |
| `backend/app/contexts/production/production_event/production_event_source.py` | Production event source categories. | ED-0013 | Provider-agnostic source categories only. |
| `backend/app/contexts/production/production_event/production_event_summary.py` | Production event summary contract. | ED-0013 | Lightweight log and diagnostics summary without reasoning or workflow triggers. |
| `backend/app/contexts/production/production_event/production_event_type.py` | Production event type categories. | ED-0013 / ED-0021 / ED-0022 | Generic happened-event types without conclusion-oriented names; ED-0021 adds `visual_detection_available`; ED-0022 adds `operator_input_received`. |
| `backend/app/contexts/production/recording_adapter/__init__.py` | Recording system adapter package exports. | ED-0016 | Exports recording adapter contracts. |
| `backend/app/contexts/production/recording_adapter/README.md` | Recording system adapter package guide. | ED-0016 | Documents adapter scope, generic Production Event mapping, and exclusions. |
| `backend/app/contexts/production/recording_adapter/recording_adapter_capability.py` | Recording adapter capability categories. | ED-0016 | Describes what a recording adapter can report without implementing behavior. |
| `backend/app/contexts/production/recording_adapter/recording_adapter_identity.py` | Recording adapter identity contract. | ED-0016 | Provider-agnostic adapter identity and kind values. |
| `backend/app/contexts/production/recording_adapter/recording_adapter_summary.py` | Recording adapter summary contract. | ED-0016 | Lightweight diagnostics summary without event creation or media inspection. |
| `backend/app/contexts/production/recording_adapter/recording_session_event.py` | Recording session event contract. | ED-0016 | Adapter-level recording activity event with generic Production Event mapping helper. |
| `backend/app/contexts/production/recording_adapter/recording_system_adapter.py` | Recording system adapter contract. | ED-0016 | Generic adapter contract that emits Production Events only. |
| `backend/app/contexts/production/recording_adapter/recording_system_status.py` | Recording system status categories. | ED-0016 | Generic recording system or adapter status values. |
| `backend/app/contexts/production/runtime_clock/__init__.py` | Runtime clock package exports. | ED-0019 | Exports runtime clock contracts. |
| `backend/app/contexts/production/runtime_clock/README.md` | Runtime clock package guide. | ED-0019 | Documents time-boundary ingress scope and scheduling exclusions. |
| `backend/app/contexts/production/runtime_clock/clock_capability.py` | Clock capability categories. | ED-0019 | Describes what the clock can report without implementing behavior. |
| `backend/app/contexts/production/runtime_clock/clock_event.py` | Clock event contract. | ED-0019 | Clock-level boundary event with generic Production Event mapping helper. |
| `backend/app/contexts/production/runtime_clock/clock_summary.py` | Clock summary contract. | ED-0019 | Lightweight diagnostics summary without time evaluation or event emission. |
| `backend/app/contexts/production/runtime_clock/runtime_clock.py` | Runtime clock contract. | ED-0019 | Generic immutable boundary evaluator and Production Event emitter contract. |
| `backend/app/contexts/production/runtime_clock/time_boundary.py` | Time boundary contract. | ED-0019 | Meaningful temporal boundary without workflow action or production outcome semantics. |
| `backend/app/contexts/production/runtime_clock/time_boundary_status.py` | Time boundary status categories. | ED-0019 | Boundary lifecycle values, not production outcome values. |
| `backend/app/contexts/production/runtime_clock/time_boundary_type.py` | Time boundary type categories. | ED-0019 | Generic temporal boundary categories without workflow actions. |
| `backend/app/contexts/production/schedule_adapter/__init__.py` | Schedule source adapter package exports. | ED-0018 | Exports schedule adapter contracts. |
| `backend/app/contexts/production/schedule_adapter/README.md` | Schedule source adapter package guide. | ED-0018 | Documents planned-world scope, generic Production Event mapping, and exclusions. |
| `backend/app/contexts/production/schedule_adapter/schedule_adapter_capability.py` | Schedule adapter capability categories. | ED-0018 | Describes what schedule changes an adapter can report without implementing behavior. |
| `backend/app/contexts/production/schedule_adapter/schedule_adapter_summary.py` | Schedule adapter summary contract. | ED-0018 | Lightweight diagnostics summary without scheduling, event creation, or observation generation. |
| `backend/app/contexts/production/schedule_adapter/schedule_source_adapter.py` | Schedule source adapter contract. | ED-0018 | Generic planned-activity adapter contract that emits Production Events only. |
| `backend/app/contexts/production/schedule_adapter/scheduled_activity.py` | Scheduled activity contract. | ED-0018 | Planned activity information without media, RecordingBlock, Session, or Observation ownership. |
| `backend/app/contexts/production/schedule_adapter/scheduled_activity_identity.py` | Scheduled activity identity contract. | ED-0018 | Descriptive planned-activity identity without runtime state. |
| `backend/app/contexts/production/schedule_adapter/scheduled_activity_status.py` | Scheduled activity status categories. | ED-0018 | Schedule-source state values, not production execution state. |
| `backend/app/contexts/production/schedule_adapter/scheduled_activity_type.py` | Scheduled activity type categories. | ED-0018 | Generic planned activity types without provider-specific assumptions. |
| `backend/app/contexts/production/session_window_product/__init__.py` | Production session window product package exports. | ED-0012 | Exports specialized session window product contracts. |
| `backend/app/contexts/production/session_window_product/README.md` | Session window product package guide. | ED-0012 | Documents scope, lineage, boundary confidence, and relationship to ED-0005 `SessionWindow`. |
| `backend/app/contexts/production/session_window_product/session_window_product.py` | Session window product contract. | ED-0012 | Verified media window for scheduled session information; references Operational Product by ID only. |
| `backend/app/contexts/production/session_window_product/session_window_product_boundary.py` | Session window product boundary contract. | ED-0012 | Start and end boundary confidence from `0.0` through `1.0`. |
| `backend/app/contexts/production/session_window_product/session_window_product_lineage.py` | Session window product lineage contract. | ED-0012 | ID-only traceability to Findings, Verification Decisions, and originating Operational Product. |
| `backend/app/contexts/production/session_window_product/session_window_product_status.py` | Session window product status categories. | ED-0012 | Specialized product lifecycle values, separate from verification and generic Operational Product status. |
| `backend/app/contexts/production/session_window_product/session_window_product_summary.py` | Session window product summary contract. | ED-0012 | Lightweight dashboard/package-workflow summary without package creation or media rendering. |
| `backend/app/contexts/production/timeline/recording_block.py` | Continuous recording block contract. | ED-0005 | Represents recording periods, not sessions. |
| `backend/app/contexts/production/timeline/schedule_reference.py` | External schedule reference contract. | ED-0005 | Uses generic external schedule language. |
| `backend/app/contexts/production/timeline/session_window.py` | Session window contract. | ED-0005 | Connects schedule reference to verified or proposed media range. |
| `backend/app/contexts/production/timeline/timeline_position.py` | Timeline position contract. | ED-0005 | Offset within a recording block. |
| `backend/app/contexts/production/timeline/timeline_range.py` | Timeline range contract. | ED-0005 | Span within one recording block. |
| `backend/app/contexts/production/transcript_adapter/__init__.py` | Transcript source adapter package exports. | ED-0020 | Exports transcript adapter contracts. |
| `backend/app/contexts/production/transcript_adapter/README.md` | Transcript source adapter package guide. | ED-0020 | Documents transcript availability reporting, Production Event mapping, and exclusions. |
| `backend/app/contexts/production/transcript_adapter/transcript_adapter_capability.py` | Transcript adapter capability categories. | ED-0020 | Describes what transcript information an adapter can report without implementing behavior. |
| `backend/app/contexts/production/transcript_adapter/transcript_adapter_identity.py` | Transcript adapter identity contract. | ED-0020 | Generic adapter identity and kind values without source-specific names. |
| `backend/app/contexts/production/transcript_adapter/transcript_adapter_summary.py` | Transcript adapter summary contract. | ED-0020 | Lightweight diagnostics summary without event dispatch or interpretation. |
| `backend/app/contexts/production/transcript_adapter/transcript_artifact_type.py` | Transcript artifact type categories. | ED-0020 | Generic transcript artifact categories without source-specific assumptions. |
| `backend/app/contexts/production/transcript_adapter/transcript_segment_event.py` | Transcript segment event contract. | ED-0020 | Adapter-level transcript activity event with generic Production Event mapping helper. |
| `backend/app/contexts/production/transcript_adapter/transcript_segment_status.py` | Transcript segment status categories. | ED-0020 | Transcript artifact availability status values, not correctness or approval states. |
| `backend/app/contexts/production/transcript_adapter/transcript_source_adapter.py` | Transcript source adapter contract. | ED-0020 | Generic transcript adapter contract that emits Production Events only. |
| `backend/app/contexts/production/verification/__init__.py` | Production verification package exports. | ED-0010 | Exports verification protocol contracts. |
| `backend/app/contexts/production/verification/verification_action.py` | Verification action categories. | ED-0010 | Judgment action values; not workflow states. |
| `backend/app/contexts/production/verification/verification_actor.py` | Verification actor contract. | ED-0010 | References decision actor IDs without user/auth behavior. |
| `backend/app/contexts/production/verification/verification_adjustment.py` | Verification adjustment contract. | ED-0010 | Describes adjustments without applying them. |
| `backend/app/contexts/production/verification/verification_decision.py` | Verification decision contract. | ED-0010 | Immutable judgment record referencing a finding ID. |
| `backend/app/contexts/production/verification/verification_note.py` | Verification note contract. | ED-0010 | Explanatory note attached to a decision. |
| `backend/app/contexts/production/verification/verification_reason.py` | Verification reason categories. | ED-0010 | Provider-agnostic reason values. |
| `backend/app/contexts/production/verification/verification_summary.py` | Verification summary contract. | ED-0010 | Summarizes decision history without final policy. |
| `backend/app/contexts/production/vision_adapter/__init__.py` | Vision source adapter package exports. | ED-0021 | Exports vision adapter contracts. |
| `backend/app/contexts/production/vision_adapter/README.md` | Vision source adapter package guide. | ED-0021 | Documents visual detection reporting, Production Event mapping, and exclusions. |
| `backend/app/contexts/production/vision_adapter/vision_adapter_capability.py` | Vision adapter capability categories. | ED-0021 | Describes what visual phenomena an adapter can report without implementing behavior. |
| `backend/app/contexts/production/vision_adapter/vision_adapter_identity.py` | Vision adapter identity contract. | ED-0021 | Generic adapter identity and kind values without source-specific names. |
| `backend/app/contexts/production/vision_adapter/vision_adapter_summary.py` | Vision adapter summary contract. | ED-0021 | Lightweight diagnostics summary without event dispatch or interpretation. |
| `backend/app/contexts/production/vision_adapter/vision_source_adapter.py` | Vision source adapter contract. | ED-0021 | Generic vision adapter contract that emits Production Events only. |
| `backend/app/contexts/production/vision_adapter/visual_detection_event.py` | Visual detection event contract. | ED-0021 | Adapter-level visual detection activity event with generic Production Event mapping helper. |
| `backend/app/contexts/production/vision_adapter/visual_detection_status.py` | Visual detection status categories. | ED-0021 | Visual detection availability status values. |
| `backend/app/contexts/production/vision_adapter/visual_detection_type.py` | Visual detection type categories. | ED-0021 | Generic observable visual phenomena categories without semantic meaning. |
| `backend/app/shared/domain_events/domain_event.py` | Base domain event contract. | ED-0004 | Generic event ID, type, timestamp, correlation, actor, and metadata. |
| `backend/app/shared/errors/errors.py` | Structured error contracts. | ED-0004 | Generic error categories only. |
| `backend/app/shared/ids/correlation_id.py` | Correlation ID contract. | ED-0004 | Generic UUID-compatible workflow tracing ID. |
| `backend/app/shared/ids/entity_id.py` | Entity ID contract. | ED-0004 | Generic UUID-compatible entity ID. |
| `backend/app/shared/result/result.py` | Result contract. | ED-0004 | Explicit success/failure result. |
| `backend/app/shared/time/clock.py` | Clock contracts. | ED-0004 | System and fixed clocks with UTC timestamps. |
| `backend/app/shared/time/time_range.py` | Time range contract. | ED-0004 | Immutable start/end/duration range. |
| `backend/tests/README.md` | Backend test suite guide. | ED-0002 | Documents health-only coverage. |
| `backend/tests/test_health.py` | Health endpoint test. | ED-0002 | Verifies startup through FastAPI TestClient. |
| `backend/tests/test_media_artifact_adapter_contracts.py` | Media artifact adapter contract tests. | ED-0017 | Covers adapter identity, artifact events, types, statuses, capabilities, Production Event mapping, summaries, and excluded behaviors. |
| `backend/tests/test_observation_interpreter_contracts.py` | Observation interpreter contract tests. | ED-0023 | Covers interpreter creation, support declarations, single and multi-event interpretation, result traceability, policy, summaries, and excluded behaviors. |
| `backend/tests/test_operator_source_adapter_contracts.py` | Operator source adapter contract tests. | ED-0022 | Covers adapter identity, operator events, types, statuses, capabilities, Production Event mapping, summaries, and excluded behaviors. |
| `backend/tests/test_production_dispatcher_contracts.py` | Production event dispatcher contract tests. | ED-0015 | Covers dispatch routing, contexts, rules, summaries, unchanged interpreter results, and excluded infrastructure behaviors. |
| `backend/tests/test_production_evidence_contracts.py` | Production evidence contract tests. | ED-0007 | Covers evidence primitives and boundary rules. |
| `backend/tests/test_production_finding_contracts.py` | Production finding contract tests. | ED-0009 | Covers finding primitives and boundary rules. |
| `backend/tests/test_production_hypothesis_contracts.py` | Production hypothesis contract tests. | ED-0008 | Covers hypothesis primitives and boundary rules. |
| `backend/tests/test_production_interpreter_contracts.py` | Production event interpreter contract tests. | ED-0014 | Covers interpreter matching, results, context, rules, summaries, and excluded behaviors. |
| `backend/tests/test_production_observation_contracts.py` | Production observation contract tests. | ED-0006 | Covers observation primitives and boundary rules. |
| `backend/tests/test_production_operational_product_contracts.py` | Production operational product contract tests. | ED-0011 | Covers generic product primitives and boundary rules. |
| `backend/tests/test_production_event_contracts.py` | Production event contract tests. | ED-0013 | Covers runtime event primitives, payload immutability, references, summaries, and excluded behaviors. |
| `backend/tests/test_production_session_window_product_contracts.py` | Production session window product contract tests. | ED-0012 | Covers specialized product primitives, lineage, boundary confidence, summaries, and excluded behaviors. |
| `backend/tests/test_production_timeline_contracts.py` | Production timeline contract tests. | ED-0005 | Tests are placed under `backend/tests/` per existing convention. |
| `backend/tests/test_production_verification_contracts.py` | Production verification contract tests. | ED-0010 | Covers append-only verification primitives and boundary rules. |
| `backend/tests/test_recording_system_adapter_contracts.py` | Recording system adapter contract tests. | ED-0016 | Covers adapter identity, status, capabilities, session events, Production Event mapping, summaries, and excluded behaviors. |
| `backend/tests/test_runtime_clock_contracts.py` | Runtime clock contract tests. | ED-0019 | Covers clock contracts, time boundaries, boundary evaluation, Production Event mapping, summaries, and excluded behaviors. |
| `backend/tests/test_schedule_source_adapter_contracts.py` | Schedule source adapter contract tests. | ED-0018 | Covers planned activity contracts, schedule adapter capabilities, Production Event mapping, summaries, and excluded behaviors. |
| `backend/tests/test_shared_contracts.py` | Shared contract tests. | ED-0004 | Covers backend contract primitives. |
| `backend/tests/test_transcript_source_adapter_contracts.py` | Transcript source adapter contract tests. | ED-0020 | Covers adapter identity, segment events, artifact types, statuses, capabilities, Production Event mapping, summaries, and excluded behaviors. |
| `backend/tests/test_vision_source_adapter_contracts.py` | Vision source adapter contract tests. | ED-0021 | Covers adapter identity, visual detection events, types, statuses, capabilities, Production Event mapping, summaries, and excluded behaviors. |

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
| `docs/05_Reasoning_Model.md` | Reasoning Model architecture reference. | AR-1.4 / AR-2.0 | AR-2.0 updates this as a primary reference for ingress, Observations, reasoning, and Operational Products. |

# Contributing to StageFlow

## Repository Philosophy

StageFlow is built specification-first. The repository should remain understandable, intentional, and aligned with the Product Constitution and architecture documents before implementation detail is added.

## Specification-First Workflow

- Read the relevant specification before implementing.
- Preserve canonical architecture documents.
- Keep implementation within the approved bounded context and architecture layer.
- Do not introduce business logic, workflows, APIs, schemas, or integrations without an approved Engineering Directive.

## Engineering Directive Process

- Engineering work must be authorized by an approved Engineering Directive.
- Directives define scope, dependencies, acceptance criteria, and out-of-scope items.
- If implementation reveals missing architecture or scope conflicts, stop and report the dependency.
- Reserved directives are not implementation approval.

## Branch Naming Convention

Use short, directive-oriented branch names:

```text
ed/<directive-number>-short-description
```

Examples:

```text
ed/0001-repository-scaffold
ed/0002-backend-foundation
```

## Pull Request Expectations

- Reference the governing Engineering Directive.
- Summarize files created, files modified, and scope boundaries.
- Call out any architecture assumptions or ambiguities.
- Include tests when implementation code exists.
- Confirm that out-of-scope items were not introduced.

## Architecture Review Requirement

Changes that affect domain behavior, bounded contexts, architecture layers, integrations, data ownership, or production workflow require architecture review before merge.

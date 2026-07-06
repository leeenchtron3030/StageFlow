# StageFlow Frontend

## Purpose

This directory contains the StageFlow frontend workspace created by ED-0003.

The frontend is a workflow-oriented Next.js application shell. It is intentionally not organized around backend entities or database tables.

## Technology Stack

- Next.js
- TypeScript
- Tailwind CSS
- shadcn/ui
- TanStack Query
- React Hook Form
- Zod

## Current Scope

ED-0003 implements only the minimum application shell required to verify startup and build behavior.

The root page displays:

- StageFlow
- Architecture Release: AR-1.2
- Engineering Directive: ED-0003
- Backend Status: Not Connected

No backend communication is implemented.

## Local Setup

```bash
cd frontend
npm install
```

## Run the Frontend

```bash
cd frontend
npm run dev
```

## Verification Commands

```bash
cd frontend
npm run build
npm run lint
npm run typecheck
```

## What Belongs Here

- Frontend application shell and future workflow-oriented UI.
- Shared frontend components and layouts.
- Design tokens and theme foundations.
- Frontend tests after a future directive defines the test runner.

## What Does Not Belong Here

- Backend communication before a future directive approves it.
- Authentication or authorization.
- Operational dashboards or workflow screens.
- Database-entity-oriented feature folders.
- Docker or CI configuration.

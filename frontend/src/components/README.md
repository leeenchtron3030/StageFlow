# Components

## Purpose

`components` contains reusable operational shell, Mission Control, and role-specific
view composition used by the first Producer UI milestone.

## What Belongs Here

- Shared UI components.
- Shared shell, Stage/Attention/Infrastructure presentation, and operational views.
- Future shadcn/ui components added by approved directives when a concrete need exists.
- Component primitives used across workflow surfaces.

## What Does Not Belong Here

- Route definitions.
- Workflow-specific page composition.
- Backend communication logic.

Backend communication and policy mapping remain in `src/experience/`; components consume
the provider-neutral presentation model.

# .github

## Purpose

This directory contains GitHub repository governance assets for StageFlow.

## What Belongs Here

- Pull request templates.
- Issue templates.
- Repository-level GitHub metadata.
- Validation workflow definitions authorized by the accepted architecture-baseline
  disposition.

## What Does Not Belong Here

- Application code.
- Architecture source documents.
- Secrets or environment-specific configuration.
- Deployment or release workflows without specific authority.

## Current automation

The quality-matrix workflow runs the repository's verified backend and frontend checks.
It is development validation only and does not demonstrate event-operational readiness,
deploy software, or publish artifacts.

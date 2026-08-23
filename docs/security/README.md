# Security and dependency evidence

This directory contains bounded security, dependency, and software-composition evidence.
Artifacts are point-in-time repository evidence, not legal advice, a vulnerability
attestation, or a production-readiness claim.

## Current records

- [Dependency license and SBOM refresh — 2026-08-21](dependency-license-sbom-2026-08-21.md)
- [Backend CycloneDX 1.5 SBOM](sbom/backend.cdx.json)
- [Backend installed-license inventory](sbom/backend-licenses.json)
- [Frontend CycloneDX 1.6 SBOM](sbom/frontend.cdx.json)

Regenerate these artifacts from the checked-in lockfiles after an accepted dependency
change. Review generated diffs and unresolved scanner warnings; do not treat successful
JSON generation as legal clearance.

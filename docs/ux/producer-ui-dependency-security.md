# Producer UI dependency-security triage

## Scope and evidence

Diagnostic review performed 2026-08-12 against `frontend/package-lock.json` with npm 11.
No forced audit fix, major framework change, dependency replacement, or install-script
approval was performed. Application imports were searched for affected tooling and
image-processing paths.

The compatible Next.js patch was updated from 16.2.10 to 16.2.11. This removes the
framework's own listed 16.2.10 advisories. npm still reports `next` as affected because
its dependency graph contains vulnerable PostCSS and Sharp versions.

## Findings

| Package/path | Directness and deployment role | Actual StageFlow relevance | First fixed version from advisory range | Change class | Disposition |
| --- | --- | --- | --- | --- | --- |
| `next` | Direct runtime framework | Production server/rendering surface | `16.2.11` for the direct advisories | Patch | Applied and validated; transitive findings remain below |
| `postcss` via Next/Tailwind | Transitive build/runtime framework dependency | Affected behavior requires attacker-controlled CSS/source-map input; StageFlow compiles repository-owned CSS and accepts no CSS upload | `8.5.23` | Patch, but Next pins its own older line | Residual; do not override framework internals without a separate compatibility validation |
| `sharp` via Next | Optional transitive image-processing runtime | No StageFlow source imports `next/image` or processes operator-supplied images | `0.35.0` | Minor | Residual; framework-managed dependency and no reachable current image path |
| `nanoid` via PostCSS | Transitive build dependency | No direct use; exposure follows repository-owned CSS processing | `3.3.17` | Patch | Residual with parent PostCSS/Next path |
| `brace-expansion` via ESLint/config | Transitive development tooling | Lint-time glob expansion only; no runtime request path | `1.1.18` / `5.0.9` | Patch | Residual development risk; await parent tooling update |
| `js-yaml` via ESLint/shadcn | Transitive development tooling | Repository configuration parsing only; no runtime YAML input | `4.3.1` | Patch | Residual development risk; await parent tooling update |
| `@modelcontextprotocol/sdk`, `@hono/node-server`, `hono` via `shadcn` | Transitive development CLI/server stack | `shadcn` is a code-generation tool and is not imported by StageFlow runtime code | `1.30.0`, `2.0.5`, `4.12.34` | Minor/major at transitive boundaries | Residual development risk; do not change codegen/runtime semantics solely to lower audit count |
| `fast-uri`, `ip-address`, `undici` via `shadcn` | Transitive development CLI networking/validation | No application import; reachable only when the developer invokes the CLI | `3.1.5`, `>10.3.0` (current `10.5.0`), `7.29.0` | Patch | Residual development risk; do not invoke the CLI on untrusted input or networks until parent update |

## Install-script notices

npm reported unapproved install scripts for `sharp@0.34.5` and
`unrs-resolver@1.12.2`. They were not approved by this workstream. StageFlow should keep
install-script approval explicit and review the exact package/version before enabling it.

## Residual posture

The post-patch audit still reports 12 package-level findings (3 moderate, 9 high) because
npm severity propagates through parent dependency paths. Current reachable production
risk is bounded by the absence of user-controlled CSS/source maps, Next image processing,
Server Actions, custom rewrites, and direct imports of the affected development CLI
stack. This is a deployment-surface assessment, not a claim that vulnerable packages are
safe. Re-audit at the next dependency-maintenance milestone and prefer parent-package
updates over lockfile overrides.

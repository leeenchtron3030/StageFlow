# Dependency license and SBOM refresh — 2026-08-21

## Status and scope

**Status:** Completed evidence pass under ED-0066; dependency decision still required.

This pass inventories the checked-in backend and frontend dependency graphs, records
declared license metadata, and preserves machine-readable CycloneDX artifacts. It makes
no dependency, lockfile, build, runtime-configuration, distribution, or legal decision.
The findings are engineering due-diligence input and are not legal advice.

Baseline: `main` at `271f0b7` plus the in-progress ED-0063–ED-0066 working tree.

## Generated artifacts

| Artifact | Scope | Result | SHA-256 |
| --- | --- | --- | --- |
| [`backend.cdx.json`](sbom/backend.cdx.json) | `backend/uv.lock`, default + `dev` + `transcription` groups | CycloneDX 1.5; 50 components plus the StageFlow root component | `6FB617864C0622468F44231F3D0FD8CBB7764270458BCAA38E425363473CD9F0` |
| [`backend-licenses.json`](sbom/backend-licenses.json) | Installed Windows resolution of the same locked groups | 49 package license records; platform-excluded packages are absent | `C42B2123365E8686D892CE04AF675A9F139E893F0E2A603C32CC98E307B049A2` |
| [`frontend.cdx.json`](sbom/frontend.cdx.json) | `frontend/package-lock.json`, including dev and optional packages | CycloneDX 1.6; 582 top-level/665 total nested components with declared license evidence and 666 dependency nodes | `5F97577B190897D9101C91B70AE955B5AC11246542B577E216866EBE1DAD496D` |

The frontend lockfile contains 665 non-root package entries across every platform. The
CycloneDX document represents 582 at top level and nests the remaining path-specific
components, for 665 total component objects; the checked-in lockfile remains the package
source of truth.

## Method and limitations

Backend inventory used `uv 0.12.3` to export all locked groups and `pip-licenses` against
the synchronized `.venv`. The `uv` CycloneDX exporter is experimental and does not embed
license metadata, so the separate `pip-licenses` JSON is retained beside it. The scan
reads Python distribution metadata; it does not prove how a native wheel was compiled,
which optional codecs were enabled, or what license applies to every bundled shared
library.

Frontend inventory first used npm 11.17.0's built-in `npm sbom --package-lock-only`.
That command failed with `ESBOMPROBLEMS` because the checked-in graph contains:

- `@tailwindcss/oxide-wasm32-wasi@4.3.2` requiring `@emnapi/core ^1.11.1`, while the
  lockfile selects `@emnapi/core@1.10.0`; and
- the same package requiring `@emnapi/wasi-threads ^1.2.2`, while the lockfile selects
  `@emnapi/wasi-threads@1.2.1`.

Both mismatches are optional, development-only WASI packages with MIT metadata, but they
remain a lock-graph integrity warning. ED-0066 does not authorize rewriting the lockfile.
An ephemeral `@cyclonedx/cyclonedx-npm` scan was therefore run with
`--package-lock-only --ignore-npm-errors`; it reported the npm errors, generated the
artifact, and validated the resulting CycloneDX document. The ephemeral scanner and its
cache dependencies were not added to `package.json` or `package-lock.json`.

## Copyleft and attribution findings

### Backend

| Package | Locked version | Declared license | Classification and current use |
| --- | --- | --- | --- |
| `psycopg` | 3.3.4 | LGPL-3.0-only | Direct runtime dependency and PostgreSQL adapter API |
| `psycopg-binary` | 3.3.4 | LGPL-3.0-only | Selected binary extra on CPython; native distribution obligations require review |
| `certifi` | 2026.6.17 | MPL-2.0 | Transitive runtime CA bundle |
| `tqdm` | 4.70.0 | MPL-2.0 AND MIT | Transitive transcription-group dependency |
| `av` (PyAV) | 18.1.0 | BSD-3-Clause package metadata | Transitive `faster-whisper` media binding; native FFmpeg build provenance is not described by this metadata |
| `faster-whisper` | 1.2.1 | MIT | Explicit transcription group |
| `ctranslate2` | 4.8.1 | MIT | Explicit transcription group |

The installed PyAV wheel reports `av 18.1.0` and loads FFmpeg-family libraries
`libavutil 60.26.102`, `libavcodec 62.28.102`, `libavformat 62.12.102`,
`libavdevice 62.3.102`, `libavfilter 11.14.102`, `libswscale 9.5.102`, and
`libswresample 6.3.102`. Package metadata reports BSD-3-Clause for PyAV and MIT for
`faster-whisper`, but that evidence does not disclose the wheel's FFmpeg configuration
or settle the earlier audit's potential GPL-2.0-compatible codec/build exposure.

Treat any distributed backend bundle that includes the transcription group as
**license review pending** until the FFmpeg/PyAV binary provenance is established and
counsel confirms the obligations. Passing `pip-licenses` is not clearance for the
native wheel.

### Frontend

The package lock declares these license families among 665 non-root entries:

| Declared license | Count | Notable packages |
| --- | ---: | --- |
| MIT | 546 | Most application and tool dependencies |
| Apache-2.0 | 34 | Multiple runtime/tool packages |
| ISC | 32 | Transitive packages |
| BSD-2-Clause / BSD-3-Clause / 0BSD | 21 | Transitive packages |
| MPL-2.0 | 13 | `lightningcss` plus 10 platform packages; `axe-core` |
| LGPL-3.0-or-later | 10 | Platform-specific `@img/sharp-libvips-*` packages |
| Apache-2.0 AND LGPL-3.0-or-later | 3 | Optional Windows `@img/sharp-*` native packages |
| Apache-2.0 AND LGPL-3.0-or-later AND MIT | 1 | Optional `@img/sharp-wasm32` package |
| CC-BY-4.0 | 1 | `caniuse-lite` data |

The `sharp`/libvips packages are optional runtime platform artifacts pulled through the
Next.js graph. Distribution packaging must determine which platform artifact is actually
shipped and preserve applicable LGPL notices/source or relinking obligations as advised
by counsel. `lightningcss@1.32.0` and its platform packages plus `axe-core@4.12.1` are
development-only in this lockfile; MPL-2.0 is file-level copyleft, but notices and source
availability for any distributed covered files still require normal compliance.

No dependency with GPL or AGPL declared package metadata appears in the Python or npm
scanner output. That does not eliminate the unresolved PyAV/FFmpeg binary question.

## Decision options for the PyAV/FFmpeg exposure

ED-0066 records options but does not select one:

1. **Own an auditable LGPL-only FFmpeg/PyAV build.** Pin the build inputs and configure
   only LGPL-compatible codecs/features. This gives the clearest provenance and can
   reduce GPL exposure, but StageFlow would own native builds, security updates,
   reproducibility, platform qualification, and distribution compliance.
2. **Accept the current wheel only after counsel and provenance review.** Establish the
   exact upstream wheel build configuration, identify every bundled native license, and
   implement the notices/source/relinking or other obligations counsel requires. This is
   operationally simpler but may be unacceptable for the intended distribution model.
3. **Do not distribute the transcription group while review is pending.** Keep the core
   backend dependency set separable and omit the optional local transcription runtime
   from distributable artifacts. This avoids making an uninformed distribution claim but
   delays the accepted local transcription capability in those artifacts.

Selecting a build/dependency change is outside ED-0066 and requires a bounded plan with
license, security-patching, offline, platform, lockfile, and qualification consequences.

## Required follow-up

- Product/legal owner: decide the intended distribution model and review LGPL/MPL/
  attribution obligations.
- Backend owner: establish PyAV wheel/FFmpeg build provenance before distributing the
  transcription group; choose one option above through an approved plan.
- Frontend owner: completed by ED-0069 on 2026-08-23. The repaired npm lock graph now
  passes npm's own SBOM command after the authorized audit remediation.
- Release owner: retain notices/source-offer/relinking materials required for the exact
  platform artifacts actually distributed.
- Engineering: regenerate and diff these artifacts after every accepted dependency or
  lockfile change.

## ED-0069 frontend remediation closure

ED-0069 ran `npm audit fix` without `--force`, staying within the existing
`next ^16.2.11` declaration. The lockfile now resolves Next.js 16.3.2 and its remediated
transitive dependency set; `npm audit` reports zero vulnerabilities.

The optional WASI graph now hoists `@emnapi/core@1.11.1` and
`@emnapi/wasi-threads@1.2.2` for `@tailwindcss/oxide-wasm32-wasi`, while retaining
`@unrs/resolver-binding-wasm32-wasi`'s exact older requirements in its nested lockfile
scope. `npm sbom --package-lock-only --sbom-format cyclonedx` completes without
`ESBOMPROBLEMS`. The checked-in reproducible
`docs/security/sbom/frontend.cdx.json` was regenerated and validated from the repaired
lockfile.

`unrs-resolver@1.12.2` and all packages examined by `npm audit signatures` have
verified registry signatures; npm reported 586 verified packages and 117 attestations.
Its postinstall remains deliberately unapproved. The reviewed script delegates to
`napi-postinstall`, which may run a nested npm install or download a native binding when
the platform binding is absent. The supported Windows binding is already present and the
clean install plus full quality suite passes without granting that extra network-capable
fallback. This is a package-specific decision, not a blanket script policy.

## Commands executed

```powershell
cd backend
uv sync --all-groups
uv export --all-groups --format cyclonedx1.5 --output-file ../docs/security/sbom/backend.cdx.json
uvx --from pip-licenses pip-licenses --python .venv/Scripts/python.exe --format=json --with-system --with-urls --with-description --output-file ../docs/security/sbom/backend-licenses.json

cd ../frontend
npm.cmd sbom --package-lock-only --sbom-format cyclonedx --sbom-type application
npx.cmd --yes @cyclonedx/cyclonedx-npm --package-lock-only --ignore-npm-errors --sv 1.6 --output-format JSON --output-reproducible --validate --output-file ../docs/security/sbom/frontend.cdx.json
```

The npm command failed with the two recorded invalid-version findings. The independent
CycloneDX command completed with those warnings. No package manifest or lockfile changed.

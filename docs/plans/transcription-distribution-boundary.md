# Transcription distribution boundary

## Status

Approved

## Execution authority

- Classification: Green autonomous — documentation and a non-destructive guard over an
  already-existing dependency boundary.
- Authority evidence: the repository owner's 2026-08-28 selection of option 3 in
  [the ED-0066 dependency license and SBOM report](../security/dependency-license-sbom-2026-08-21.md)
  ("do not distribute the transcription group while review is pending"); the confirmed GPL
  provenance of the bundled FFmpeg build recorded in that same report;
  [ADR-0029](../adr/ADR-0029-nvenc-rendering-and-gpu-worker-requirement.md), which
  deliberately avoids extending that exposure to the rendering path.
- Implementation-ready: Yes.
- Required escalation or approval, if any: none. Stop and escalate if closing this
  boundary appears to require changing, removing, or vendoring any dependency, or
  altering how transcription executes — none of which is in scope.

## Related findings or ADRs

- Finding: the installed `av` (PyAV) 18.1.0 wheel bundles `libx264` and `libx265`,
  confirming a GPL-configured FFmpeg build. StageFlow is MIT-licensed. Running a local
  copy is not distribution, so nothing is wrong today; shipping a packaged artifact that
  includes the group would be.
- ADR: ADR-0029 (rendering avoids a second `libx264` dependency by using NVENC).
- Engineering Directive: ED-0075. Follows ED-0066.

## Problem statement

The transcription dependency group carries a confirmed GPL FFmpeg build. It is already
optional — `backend/pyproject.toml` declares it under `[dependency-groups]`, so a default
`uv sync` does not install it — but nothing in the repository states that this separation
is *deliberate and load-bearing*. A future contributor could reasonably promote
`faster-whisper` to a default dependency, or a future packaging step could run
`--all-groups`, silently converting a documented non-issue into a real licensing problem.
The boundary exists by accident of convenience and needs to exist on purpose.

## Verified current behavior

- `backend/pyproject.toml` `[dependency-groups]` declares `transcription = ["ctranslate2==4.8.1", "faster-whisper==1.2.1"]`.
- `av` (PyAV) is a transitive dependency of `faster-whisper`, not a direct declaration.
- A default `uv sync` installs neither; `uv sync --group transcription` and
  `uv sync --all-groups` install both.
- The SBOM generation commands recorded in the ED-0066 report deliberately use
  `--all-groups`, which is correct for inventory purposes and is not a distribution path.
- No packaging, container, or release artifact definition currently exists in the
  repository, so there is nothing today that incorrectly bundles the group.

## Desired behavior

The transcription group's exclusion from any distributable artifact is explicit, documented
where a contributor will encounter it, and guarded well enough that reversing it requires a
deliberate decision rather than an accident.

## In scope

- Document the boundary in `backend/README.md` and the root `README.md` where dependency
  installation is described: local transcription is an operator-installed optional
  capability, and why.
- Add an explicit note to `backend/pyproject.toml` (comment) beside the `transcription`
  group recording that its exclusion from distribution is a licensing decision, referencing
  ED-0075 and the SBOM report.
- Record the boundary in `AGENTS.md` alongside the existing dependency guidance, so an
  implementing agent encounters it before proposing a dependency promotion.
- Add a bounded check — a focused test or documented release-checklist item — asserting
  that `transcription` remains a non-default dependency group.
- Cross-reference the decision from the SBOM report to the new documentation.

## Out of scope

- Changing, removing, pinning differently, or vendoring any dependency.
- Building an LGPL-only FFmpeg/PyAV wheel. That is the recommended future direction for
  the first genuinely distributed artifact and needs its own plan when that time comes.
- Any change to how transcription executes, its provider/model selection, or the accepted
  worker substrate.
- Creating packaging, container, or release tooling. None exists; this plan documents a
  constraint that such tooling must later honor, rather than building it.
- Legal interpretation. The decision recorded here is a distribution-scope choice, not
  legal advice or clearance.

## Constraints

- Non-destructive: no dependency resolution, lockfile, or installed environment changes.
  A developer who currently has the transcription group installed keeps working unchanged.
- Honesty: the documentation must state that this defers rather than resolves the
  licensing question, and must not imply legal clearance.
- Proportionality: this is a small guard over an existing boundary, not a packaging
  redesign.

## Implementation approach

1. Add the `pyproject.toml` comment beside the `transcription` group.
2. Document the boundary and its rationale in `backend/README.md` and the root
   `README.md` installation sections.
3. Add the constraint to `AGENTS.md` dependency guidance.
4. Add the bounded check that `transcription` is not a default group.
5. Cross-link the SBOM report to the new documentation.

## Files or modules expected to change

| Path or module | Expected change |
| --- | --- |
| `backend/pyproject.toml` | Comment recording the licensing rationale (no dependency change) |
| `backend/README.md` | Document optional-transcription installation and why |
| `README.md` | Same note at repository level |
| `AGENTS.md` | Dependency guidance records the boundary |
| `backend/tests/` | Bounded check that `transcription` remains non-default |
| `docs/security/dependency-license-sbom-2026-08-21.md` | Cross-link |

## Data or migration considerations

None.

## Failure and recovery considerations

If the bounded check cannot read `pyproject.toml` deterministically across supported
environments, prefer a documented release-checklist item over a brittle test. A guard that
fails spuriously is worse than a clearly documented constraint.

## Observability requirements

Not applicable.

## Test strategy

- The bounded non-default-group check.
- Full backend suite to confirm no regression, Ruff, Pyright.
- `git diff --check`; verify no lockfile or dependency resolution changed.

## Acceptance criteria

- [ ] `backend/pyproject.toml` records the licensing rationale beside the `transcription`
  group without changing any dependency.
- [ ] `backend/README.md` and root `README.md` document local transcription as an
  operator-installed optional capability and say why.
- [ ] `AGENTS.md` records the constraint where dependency guidance already lives.
- [ ] A bounded check or documented release-checklist item asserts `transcription` remains
  a non-default group.
- [ ] The documentation states plainly that this defers rather than resolves the licensing
  question and is not legal clearance.
- [ ] No dependency, lockfile, resolution, or execution behavior changed.
- [ ] Full backend suite, Ruff, and Pyright pass.

## Rollback or reversal

Documentation and one check; directly revertible with no dependency or runtime effect.

## Open questions

- Does the owner want the same note surfaced in `CONTRIBUTING.md`, or is `AGENTS.md` plus
  the READMEs sufficient reach?

## Completion record

_(To be filled in by whoever implements this plan.)_

# Repository reviews

## Purpose

Reviews record evidence about the repository at a stated point in time. They may identify
defects, risks, strengths, gaps, or decisions, but a review is not architecture or
implementation authority by itself.

## Naming

Use a descriptive lowercase kebab-case name for a repository-wide review:

```text
<subject>-review.md
<subject>-disposition.md
```

Existing Engineering Directive review artifacts retain their published names. Do not
rename historical records merely for consistency.

## Evidence requirements

A review should record:

- review date, repository revision, branch, and scope;
- files, configuration, and documentation inspected;
- commands and tests actually run, including failures and omissions;
- observed facts separately from inference, intended direction, and recommendations;
- confidence, affected boundaries, concrete scenarios, and unavailable evidence;
- confirmation of whether the review modified any implementation.

Sensitive media, credentials, customer data, and large copied source payloads do not
belong in review artifacts.

## Review versus decision

A review analyzes. A disposition decides what to accept, qualify, defer, reject, protect,
or leave open. Recommendations from a review must not be implemented until an approved
disposition, ADR, Engineering Directive, or other explicit authority permits the work.

Every architecture-significant review requires a disposition document, even when the
disposition rejects all recommendations. The disposition should link the source review
and baseline commit, address every material finding, and identify unresolved decisions.

## Index

| Review | Disposition | Role |
| --- | --- | --- |
| [Architecture baseline and consistency review](architecture-baseline-review.md) | [Architecture baseline disposition](architecture-baseline-disposition.md) | Current repository-wide baseline; review is evidence and disposition is decision authority |
| [ED-0041 architecture/codebase review](ED-0041_ARCHITECTURE_CODEBASE_REVIEW.md) | Findings were addressed through the related roadmap, directives, and later baseline disposition | Historical architecture review |
| [ED-0041 findings register](ED-0041_FINDINGS_REGISTER.md) | [ED-0041 directive roadmap](ED-0041_DIRECTIVE_ROADMAP.md) | Historical findings and remediation roadmap |

## Supersession and preservation

Do not overwrite a review to match later code. A later review may supersede its findings
by linking the older review, stating the new baseline, and explaining what changed. Keep
the original evidence and its disposition available. Mark supersession in the index and
in the newer document; never imply that historical conclusions were current forever.

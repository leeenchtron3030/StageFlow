# StageFlow Reasoning Model

**Document:** docs/05_Reasoning_Model.md  
**Architecture Release:** AR-1.3  
**Status:** Approved  
**Depends On:** PRODUCT_CONSTITUTION.md, docs/00.5_Domain_Model.md, docs/04.5_Bounded_Contexts.md  
**Referenced By:** Production Context, Editorial Context, Integration Architecture, Future Review Interfaces

---

# Purpose

This document defines the reasoning model used by StageFlow.

The reasoning model explains how StageFlow moves from raw production reality to explainable human-reviewable findings.

---

# Core Model

StageFlow separates operational reasoning into distinct layers:

```text
Reality
↓
Timeline
↓
Observation
↓
Evidence
↓
Hypothesis
↓
Finding
↓
Verification
↓
Operational Product
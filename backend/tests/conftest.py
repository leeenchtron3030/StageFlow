from __future__ import annotations

import os

# Synthetic test-only request-boundary credential. Production startup still fails closed
# when the operator has not supplied STAGEFLOW_API_SHARED_SECRET.
os.environ.setdefault(
    "STAGEFLOW_API_SHARED_SECRET",
    "stageflow-test-only-shared-secret-0123456789",
)

from __future__ import annotations

from dataclasses import dataclass

from app.contexts.production.dispatcher import (
    DispatchContext,
    DispatchResult,
    ProductionEventDispatcher,
)
from app.contexts.production.ingress.contracts import (
    IngressRegistrationRequest,
    IngressRegistrationResult,
    IngressRepository,
)


@dataclass(frozen=True, slots=True)
class IngressDispatchResult:
    registration: IngressRegistrationResult
    dispatch: DispatchResult | None


@dataclass(frozen=True, slots=True)
class DurableIngressDispatcher:
    repository: IngressRepository
    dispatcher: ProductionEventDispatcher

    def register_and_dispatch(
        self,
        request: IngressRegistrationRequest,
        context: DispatchContext,
    ) -> IngressDispatchResult:
        registration = self.repository.register(request)
        if not registration.should_dispatch or registration.record is None:
            return IngressDispatchResult(registration, None)
        return IngressDispatchResult(
            registration,
            self.dispatcher.dispatch(registration.record.to_production_event(), context),
        )

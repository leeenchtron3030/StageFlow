"""Media timing view of the shared operation journal; no evidence write boundary."""

from app.contexts.work_execution import MediaTimingOperationInput

from .transcription_work_repository import PostgresWorkExecutionRepository


class PostgresMediaTimingWorkRepository(
    PostgresWorkExecutionRepository[MediaTimingOperationInput],
):
    def __init__(self, dsn: str) -> None:
        super().__init__(dsn, input_types=(MediaTimingOperationInput,))

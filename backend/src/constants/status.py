from enum import StrEnum


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    RECOVERING = "recovering"
    COMPLETED = "completed"
    FAILED = "failed"


class RunPhase(StrEnum):
    """User-facing view of a run, derived from status plus recovery counters."""
    WAITING = "waiting"
    RECOVERING = "recovering"
    CALCULATING = "calculating"
    COMPLETED = "completed"
    FAILED = "failed"

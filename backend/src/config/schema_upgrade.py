"""Idempotent upgrade for the run-recovery columns.

``Base.metadata.create_all`` only creates missing tables; it does not add
columns to an existing deployment. This adds the recovery bookkeeping columns
with safe defaults so an old volume keeps working and orphaned runs can be
recovered after the restart.
"""
from sqlalchemy import inspect,text

_NEW_COLUMNS={
    "attempt":"INTEGER DEFAULT 0",
    "attempt_token":"VARCHAR DEFAULT ''",
    "worker_id":"VARCHAR DEFAULT ''",
    "lease_at":"VARCHAR DEFAULT ''",
    "queued_at":"VARCHAR DEFAULT ''",
    "recovery_count":"INTEGER DEFAULT 0",
    "started_at":"VARCHAR DEFAULT ''",
    "finished_at":"VARCHAR DEFAULT ''",
}

def upgrade_schema(engine):
    inspector=inspect(engine)
    if "bayes_runs" not in inspector.get_table_names():return
    existing={column["name"] for column in inspector.get_columns("bayes_runs")}
    missing={name:ddl for name,ddl in _NEW_COLUMNS.items() if name not in existing}
    if not missing:return
    with engine.begin() as connection:
        for name,ddl in missing.items():connection.execute(text(f"ALTER TABLE bayes_runs ADD COLUMN {name} {ddl}"))
        connection.execute(text("UPDATE bayes_runs SET attempt=COALESCE(attempt,0), recovery_count=COALESCE(recovery_count,0)"))
        connection.execute(text("UPDATE bayes_runs SET attempt_token=COALESCE(attempt_token,''), worker_id=COALESCE(worker_id,''), lease_at=COALESCE(lease_at,''), started_at=COALESCE(started_at,''), finished_at=COALESCE(finished_at,'')"))
        # Runs queued before the upgrade get their durable queue timestamp.
        connection.execute(text("UPDATE bayes_runs SET queued_at=COALESCE(NULLIF(queued_at,''),created_at) WHERE status='queued'"))

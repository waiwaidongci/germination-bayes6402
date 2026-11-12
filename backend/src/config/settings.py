import os
DATABASE_URL=os.environ.get("DATABASE_URL","postgresql+psycopg://germination:germination@db/germination")
REDIS_URL=os.environ.get("REDIS_URL","redis://redis:6379/0")
JWT_SECRET=os.environ.get("JWT_SECRET","local-germination-bayes-change-this-key")
SEED_DEMO=os.environ.get("SEED_DEMO","true").lower()=="true"
ARTIFACT_DIR=os.environ.get("ARTIFACT_DIR","/artifacts")
# Recovery knobs (seconds); overridden in tests for determinism.
QUEUE_STALE_SECONDS=int(os.environ.get("QUEUE_STALE_SECONDS","45"))
RUNNING_STALE_SECONDS=int(os.environ.get("RUNNING_STALE_SECONDS","90"))
MAX_RECOVERIES=int(os.environ.get("MAX_RECOVERIES","3"))

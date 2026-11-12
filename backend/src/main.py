import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from .config.database import Base,engine
from .config.settings import SEED_DEMO
from . import models
from .routes import auth,studies,lots,counts,runs,notes,audits
from .middlewares.errors import ErrorMiddleware
from .middlewares.rate_limit import RateLimitMiddleware
from .services.run_service import queue_client
from .config.schema_upgrade import upgrade_schema
@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    upgrade_schema(engine)
    if SEED_DEMO:
        try:
            from scripts.seed_demo import seed
            seed()
        except Exception:logging.exception("demo seed failed")
    yield
app=FastAPI(title="铎岑种子萌发批次概率册",lifespan=lifespan)
@app.exception_handler(RequestValidationError)
async def validation_error(request,exc):
    details=[{"loc":[str(v) for v in e["loc"]],"msg":e["msg"]} for e in exc.errors()]
    return JSONResponse(status_code=422,content={"detail":"；".join("/".join(e["loc"])+": "+e["msg"] for e in details)})
app.add_middleware(ErrorMiddleware);app.add_middleware(RateLimitMiddleware)
for module in [auth,studies,lots,counts,runs,notes,audits]:app.include_router(module.router)
@app.get("/health")
def health():
    with engine.connect() as c:c.execute(text("select 1"))
    queue_client().ping();return {"status":"healthy","service":"germination-bayes"}

import json,time,traceback
from pathlib import Path
from .config.database import Base,engine,SessionLocal
from .models import BayesRun
from .constants.status import RunStatus
from .services.run_service import queue
from .services.analysis_service import analyze_germination
from .services.audit_service import log
Base.metadata.create_all(engine);Path("/artifacts").mkdir(exist_ok=True)
while True:
    Path("/artifacts/heartbeat").write_text(str(time.time()))
    job=queue.blpop("germination:jobs",timeout=2)
    if not job:continue
    with SessionLocal() as db:
        run=db.get(BayesRun,int(job[1]))
        if not run or run.status!=RunStatus.QUEUED:continue
        run.status=RunStatus.RUNNING;db.commit()
        try:
            run.result=analyze_germination(run.input_snapshot,run.threshold,run.future_n);run.status=RunStatus.COMPLETED
            Path(f"/artifacts/run-{run.id}.json").write_text(json.dumps(run.result,ensure_ascii=False));log(db,"worker","bayes.completed",run.id)
        except Exception as e:run.status=RunStatus.FAILED;run.error=str(e);traceback.print_exc()
        db.commit()

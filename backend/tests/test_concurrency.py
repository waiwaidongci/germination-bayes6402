"""Concurrency: two workers racing on the same run and the same wake-up."""
import threading
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.config.database import Base
from src.models import GerminationStudy,BayesRun
from src.services.run_queue import claim,complete,reset_for_queue
from tests.fakes import CountingCalculator


def _engine_with_run(tmp_path):
    engine=create_engine(f"sqlite:///{tmp_path/'race.db'}",
        connect_args={"check_same_thread":False,"timeout":30})
    Base.metadata.create_all(engine)
    Session=sessionmaker(bind=engine,expire_on_commit=False)
    with Session() as db:
        study=GerminationStudy(code="RACE",name="并发",description="",source="test")
        db.add(study);db.commit()
        run=BayesRun(name="并发研究",study_id=study.id,threshold=.7,future_n=10,
                     input_snapshot={"study":{"id":study.id},"lots":[],"counts":[]},
                     owner="许禾",result={})
        reset_for_queue(run);db.add(run);db.commit()
        return engine,Session,run.id


def test_simultaneous_claims_produce_one_winner_and_one_result(tmp_path):
    """Both workers are handed the same wake-up; only one claim and one result."""
    from src.worker import process
    engine,Session,run_id=_engine_with_run(tmp_path)
    calc=CountingCalculator()
    barrier=threading.Barrier(2)
    winners=[];outcomes={}
    def worker(name):
        with Session() as db:
            barrier.wait()
            run=process(db,run_id,name,calc)
            outcomes[name]=run is not None
    threads=[threading.Thread(target=worker,args=(f"w{i}",)) for i in (1,2)]
    for t in threads:t.start()
    for t in threads:t.join()
    assert sum(outcomes.values())==1,outcomes
    assert len(calc.calls)==1
    with Session() as db:
        row=db.get(BayesRun,run_id)
        assert row.status=="completed"
        assert row.result["marker"]==1
        assert row.attempt==1

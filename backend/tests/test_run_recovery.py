"""Run recovery, single-owner claims, and late-write rejection."""
import pytest
from src.constants.status import RunPhase,RunStatus
from src.models import BayesRun,SamplingNote
from src.services import run_queue
from src.services.run_queue import (
    QUEUE_STALE_SECONDS,claim,complete,expire,fail,heartbeat,phase_of,
    requeue_all_queued,requeue_recovering,reset_for_queue,sweep,
)


def make_run(db,study,fake_redis,name="研究",result=None):
    run=BayesRun(name=name,study_id=study.id,threshold=.7,future_n=50,
                 input_snapshot={"study":{"id":study.id},"lots":[],"counts":[]},
                 owner="许禾",result=result or {})
    reset_for_queue(run)
    db.add(run);db.commit();db.refresh(run)
    fake_redis.rpush(run_queue.JOBS_KEY,run.id)
    return run


def refresh(db,run):
    db.expire_all()
    return db.get(BayesRun,run.id)


def test_interrupted_running_run_is_requeued_with_original_snapshot(db,study,fake_redis,calculator,monkeypatch):
    """A worker that dies mid-fit leaves the run recoverable, not stuck running."""
    from src.worker import process
    run=make_run(db,study,fake_redis)
    claimed=claim(db,run.id,"dead-worker")
    assert claimed.status==RunStatus.RUNNING
    snapshot=claimed.input_snapshot
    # Simulate the worker dying: no heartbeat and no completion.
    db.expire_all()
    monkeypatch.setattr(run_queue,"_age_seconds",lambda ts:10**6)
    handled=sweep(db,fake_redis)
    assert ("expired",run.id) in handled
    current=refresh(db,run)
    assert current.status==RunStatus.QUEUED
    assert current.recovery_count==1
    assert current.attempt_token==""
    assert current.result=={}
    assert current.input_snapshot==snapshot
    assert run.id in fake_redis.queued_ids()
    assert phase_of(current)==RunPhase.RECOVERING
    # Retry computes from the same persisted counts/threshold/future_n.
    from src.worker import process as worker_process
    rerun=worker_process(db,run.id,"fresh-worker",calculator)
    assert rerun is not None and rerun.attempt==2
    assert current.threshold==.7 and current.future_n==50
    assert calculator.calls[0]["snapshot"]==snapshot
    assert calculator.calls[0]["threshold"]==.7
    current=refresh(db,run)
    assert current.status==RunStatus.COMPLETED
    assert current.result["marker"]==1


def test_restart_requeues_waiting_and_recovers_running_then_completes(db,study,fake_redis,calculator):
    """A worker restart must not leave runs waiting or showing 计算中 forever."""
    from src.worker import process,recover_after_restart
    waiting=make_run(db,study,fake_redis,name="等待")
    running=make_run(db,study,fake_redis,name="计算中")
    claim(db,running.id,"old-worker")
    fake_redis.jobs.clear()
    recovered=recover_after_restart(db,fake_redis)
    restored=refresh(db,running)
    assert restored.status==RunStatus.QUEUED
    assert restored.recovery_count==1
    assert set(fake_redis.queued_ids())=={waiting.id,running.id}
    run_ids=sorted(fake_redis.queued_ids())
    assert process(db,run_ids[0],"new-worker",calculator).id==waiting.id
    assert process(db,run_ids[1],"new-worker",calculator).id==running.id
    assert refresh(db,running).result["marker"]==2  # second fit call, single accepted write


def test_concurrent_claims_only_one_worker_wins(db,study,fake_redis,calculator):
    """Two workers handed the same run: one claim wins, the loser does nothing."""
    from src.worker import process
    run=make_run(db,study,fake_redis)
    winner=claim(db,run.id,"worker-a")
    assert winner is not None
    loser=claim(db,run.id,"worker-b")
    assert loser is None
    db.expire_all()
    current=refresh(db,run)
    assert current.status==RunStatus.RUNNING
    assert current.worker_id=="worker-a"
    stale=process(db,run.id,"worker-b",calculator)
    assert stale is None


def test_late_write_from_superseded_attempt_is_rejected(db,study,fake_redis):
    """The original worker finishing after a takeover must not overwrite."""
    run=make_run(db,study,fake_redis)
    first=claim(db,run.id,"worker-a")
    token_a=first.attempt_token
    db.expire_all()
    expire(db,run.id,run.attempt_token)
    requeue_recovering(db,run.id,fake_redis)
    second=claim(db,run.id,"worker-b")
    assert second.attempt_token!=token_a
    assert complete(db,run.id,second.attempt_token,{"marker":"b","value":2})
    # A late write with the old token is refused.
    assert complete(db,run.id,token_a,{"marker":"a","value":1}) is False
    current=refresh(db,run)
    assert current.status==RunStatus.COMPLETED
    assert current.result["marker"]=="b"
    assert current.result["value"]==2


def test_late_failure_write_is_rejected(db,study,fake_redis):
    run=make_run(db,study,fake_redis)
    first=claim(db,run.id,"worker-a");token_a=first.attempt_token
    expire(db,run.id,token_a);requeue_recovering(db,run.id,fake_redis)
    second=claim(db,run.id,"worker-b")
    assert complete(db,run.id,second.attempt_token,{"marker":"accepted"})
    assert fail(db,run.id,token_a,"late crash") is False
    current=refresh(db,run)
    assert current.status==RunStatus.COMPLETED
    assert current.error==""
    assert current.result["marker"]=="accepted"


def test_repeated_interruptions_stop_before_infinite_retry(db,study,fake_redis,monkeypatch):
    run=make_run(db,study,fake_redis)
    for attempt in range(1,6):
        claimed=claim(db,run.id,f"worker-{attempt}")
        assert claimed is not None
        expired=expire(db,run.id,claimed.attempt_token)
        assert expired is not None
        if expired.status==RunStatus.FAILED:
            assert expired.recovery_count==run_queue.MAX_RECOVERIES+1
            assert phase_of(expired)==RunPhase.FAILED
            return
        requeue_recovering(db,run.id,fake_redis)
    pytest.fail("interruption loop never reached the failure cap")


def test_completed_and_approved_research_stays_unchanged(db,study,fake_redis,calculator):
    """An approved/research result is never rewritten by recovery sweeps."""
    from src.worker import process
    run=make_run(db,study,fake_redis)
    assert process(db,run.id,"worker",calculator) is not None
    completed=refresh(db,run)
    approved=SamplingNote(run_id=run.id,title="归档",interpretation="解释"*4,
                          proposal="补种"*4,status="approved",owner="许禾",
                          reviewer="陆岑",review_note="批准"*4)
    db.add(approved);db.commit()
    before=completed.result;before_at=completed.finished_at
    sweep(db,fake_redis)
    requeue_all_queued(db,fake_redis)
    from src.worker import process as process_again
    assert process_again(db,run.id,"worker",calculator) is None  # completed rows are not claimable
    current=refresh(db,run)
    assert current.status==RunStatus.COMPLETED
    assert current.result==before
    assert current.finished_at==before_at
    assert db.get(SamplingNote,approved.id).status=="approved"
    assert len(calculator.calls)==1


def test_phase_distinguishes_waiting_recovering_calculating_failed(db,study,fake_redis):
    waiting=make_run(db,study,fake_redis,name="w")
    assert phase_of(waiting)==RunPhase.WAITING
    claimed=claim(db,waiting.id,"worker")
    assert phase_of(refresh(db,waiting))==RunPhase.CALCULATING
    expire(db,waiting.id,claimed.attempt_token)
    assert phase_of(refresh(db,waiting))==RunPhase.RECOVERING
    requeue_recovering(db,waiting.id,fake_redis)
    assert phase_of(refresh(db,waiting))==RunPhase.RECOVERING
    claimed2=claim(db,waiting.id,"worker")
    assert phase_of(refresh(db,waiting))==RunPhase.RECOVERING
    fail(db,waiting.id,claimed2.attempt_token,"计算失败")
    assert phase_of(refresh(db,waiting))==RunPhase.FAILED

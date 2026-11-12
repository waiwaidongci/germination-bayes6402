"""API-level guarantees: half results are hidden, review/export stay blocked."""
import pytest
from fastapi.testclient import TestClient
from src.constants.status import RunPhase,RunStatus
from src.models import SamplingNote
from src.services.run_queue import claim,expire,requeue_recovering,reset_for_queue
from src.worker import process


@pytest.fixture
def client(monkeypatch):
    from src.services import run_service
    from tests.fakes import FakeRedis
    fake=FakeRedis()
    monkeypatch.setattr(run_service,"queue_client",lambda:fake)
    from src.main import app
    with TestClient(app) as c:
        c.fake_redis=fake
        yield c


def _login(client,email):
    response=client.post("/auth/login",json={"email":email,"password":"Duocen2026!"})
    assert response.status_code==200,response.text
    return {"Authorization":"Bearer "+response.json()["token"]}


def _run_with_partial_result(db,study,fake_redis,name="半份结果"):
    run=__import__("src.models",fromlist=["BayesRun"]).BayesRun(
        name=name,study_id=study.id,threshold=.7,future_n=50,
        input_snapshot={"study":{"id":study.id},"lots":[],"counts":[]},
        owner="许禾（占位）",result={"fit":{"alpha":9},"lots":[{"lot":{"code":"半份"}}]})
    reset_for_queue(run);db.add(run);db.commit();db.refresh(run)
    return run


def test_list_and_show_hide_results_unless_completed(db,study,client):
    headers=_login(client,"viewer@duocen.demo")
    run=_run_with_partial_result(db,study,client.fake_redis)
    listed=client.get("/runs",headers=headers)
    assert listed.status_code==200,listed.text
    row=next(x for x in listed.json() if x["id"]==run.id)
    assert row["result"]=={}
    assert row["phase"]==RunPhase.WAITING
    assert row["recoverable"] is True
    assert "attempt_token" not in row
    shown=client.get(f"/runs/{run.id}",headers=headers).json()
    assert shown["result"]=={}
    assert shown["phase"]==RunPhase.WAITING


def test_notes_and_export_blocked_while_recovering(db,study,client,calculator):
    headers_analyst=_login(client,"analyst@duocen.demo")
    headers_admin=_login(client,"admin@duocen.demo")
    run=_run_with_partial_result(db,study,client.fake_redis)
    claimed=claim(db,run.id,"worker")
    expire(db,run.id,claimed.attempt_token)
    requeue_recovering(db,run.id,client.fake_redis)
    phase=client.get(f"/runs/{run.id}",headers=headers_analyst).json()
    assert phase["phase"]==RunPhase.RECOVERING
    assert phase["result"]=={}
    note=client.post("/notes",headers=headers_analyst,json={"run_id":run.id,"title":"补种建议",
        "interpretation":"条件EB解释与贴边说明，仍需独立验证。","proposal":"同批下一轮独立试种，按n/k口径。"})
    assert note.status_code==409
    export=client.get(f"/runs/{run.id}/export",headers=headers_admin)
    assert export.status_code==403
    assert client.get(f"/runs/{run.id}/export?kind=predictive",headers=headers_admin).status_code==403


def test_failed_run_is_not_offered_for_review_or_download(db,study,client):
    headers=_login(client,"admin@duocen.demo")
    run=_run_with_partial_result(db,study,client.fake_redis,name="失败")
    claimed=claim(db,run.id,"worker")
    db_add=_login(client,"analyst@duocen.demo")
    from src.services.run_queue import fail
    fail(db,run.id,claimed.attempt_token,"拟合失败")
    shown=client.get(f"/runs/{run.id}",headers=headers).json()
    assert shown["phase"]==RunPhase.FAILED
    assert shown["result"]=={}
    assert client.get(f"/runs/{run.id}/export",headers=headers).status_code==403
    note=client.post("/notes",headers=db_add,json={"run_id":run.id,"title":"失败建议",
        "interpretation":"即便失败也尝试提交，应被拒绝。","proposal":"下列补种方案不应通过。"})
    assert note.status_code==409


def test_recovery_resumes_to_completed_and_result_becomes_visible(db,study,client,calculator):
    """After recovery the same run completes and only then can be reviewed/downloaded."""
    headers_analyst=_login(client,"analyst@duocen.demo")
    headers_admin=_login(client,"admin@duocen.demo")
    run=_run_with_partial_result(db,study,client.fake_redis,name="接手研究")
    claimed=claim(db,run.id,"worker")
    expire(db,run.id,claimed.attempt_token)
    requeue_recovering(db,run.id,client.fake_redis)
    process(db,run.id,"worker-2",calculator)
    shown=client.get(f"/runs/{run.id}",headers=headers_analyst).json()
    assert shown["phase"]==RunPhase.COMPLETED
    assert shown["result"]["marker"]==1
    note=client.post("/notes",headers=headers_analyst,json={"run_id":run.id,"title":"独立补种建议",
        "interpretation":"条件EB解释与贴边说明，仍需独立验证。","proposal":"同批下一轮独立试种，按n/k口径。"})
    assert note.status_code==201,note.text
    approved=client.patch(f"/notes/{note.json()['id']}/review",headers=headers_admin,
        json={"status":"approved","review_note":"批准该独立补种研究归档。"})
    assert approved.status_code==200,approved.text
    export=client.get(f"/runs/{run.id}/export",headers=headers_admin)
    assert export.status_code==200
    assert "lot,n,k" in export.text

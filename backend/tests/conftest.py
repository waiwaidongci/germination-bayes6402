import os,sys

# Isolated DB/artifacts before importing the app modules.
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DATABASE_URL","sqlite:////tmp/germination-recovery-test.db")
os.environ.setdefault("REDIS_URL","redis://localhost:6399/15")
os.environ.setdefault("ARTIFACT_DIR","/tmp/germination-artifacts")
os.environ.setdefault("SEED_DEMO","false")

import pytest
from src.config.database import Base,engine,SessionLocal
from src.models import GerminationStudy,SeedLot,LotCount,BayesRun,SamplingNote

@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield

@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session

@pytest.fixture
def study(db):
    from src.models import User
    from src.utils.security import hash_password
    for role,name in [("admin","陆岑"),("analyst","许禾"),("viewer","温桥")]:
        email=role+"@duocen.demo"
        if not db.query(User).filter_by(email=email).first():
            db.add(User(email=email,name=name,role=role,password_hash=hash_password("Duocen2026!")))
    db.commit()
    s=GerminationStudy(code="TEST-01",name="测试研究",description="合成",source="test")
    db.add(s);db.commit()
    for i in range(8):
        lot=SeedLot(study_id=s.id,code=f"L{i+1:02}",name=f"批次{i+1}",origin="测试")
        db.add(lot);db.flush()
        db.add(LotCount(lot_id=lot.id,n=100,k=70+ (i%3),note="计数"))
    db.commit()
    return s

@pytest.fixture
def fake_redis():
    from tests.fakes import FakeRedis
    return FakeRedis()

@pytest.fixture
def calculator():
    from tests.fakes import CountingCalculator
    return CountingCalculator()

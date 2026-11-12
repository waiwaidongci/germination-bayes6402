"""In-memory stand-ins for Redis and the fit calculator."""
class FakeRedis:
    def __init__(self):
        self.jobs=[];self.kv={}
    def rpush(self,key,value):self.jobs.append((key,value))
    def blpop(self,key,timeout=1):
        for i,(k,v) in enumerate(self.jobs):
            if k==key:del self.jobs[i];return (k,v)
        return None
    def setex(self,key,ttl,value):self.kv[key]=(ttl,value)
    def exists(self,key):return 1 if key in self.kv else 0
    def delete(self,key):self.kv.pop(key,None)
    def queued_ids(self):return [v for k,v in self.jobs if k=="germination:jobs"]

class CountingCalculator:
    """Deterministic substitute for the SciPy fit; records every call."""
    def __init__(self):
        self.calls=[]
    def __call__(self,snapshot,threshold,future_n):
        self.calls.append({"snapshot":snapshot,"threshold":threshold,"future_n":future_n})
        return {"fit":{"alpha":2.0,"beta":2.0},"lots":[],"threshold":threshold,"future_n":future_n,"marker":len(self.calls),"input_snapshot":snapshot}

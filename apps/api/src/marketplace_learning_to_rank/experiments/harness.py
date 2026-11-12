from __future__ import annotations
import hashlib, math, random, sqlite3
from datetime import datetime, timezone
from pathlib import Path
from pydantic import BaseModel, Field,model_validator
from typing import Literal

class ExperimentConfig(BaseModel):
    experiment_id:str=Field(pattern=r"^[a-zA-Z0-9_-]{3,64}$")
    experiment_name:str=Field(min_length=3,max_length=120)
    control_strategy:Literal["rules","semantic","lambdamart"]="rules"
    treatment_strategy:Literal["rules","semantic","lambdamart"]="lambdamart"
    allocation_percentage:float=Field(default=50,gt=0,lt=100)
    randomization_unit:Literal["visitor"]="visitor"
    experiment_salt:str=Field(min_length=8,max_length=128)
    status:Literal["running","paused","completed"]="running"
    started_at:str|None=None
    ended_at:str|None=None

    @model_validator(mode="after")
    def strategies_must_differ(self):
        if self.control_strategy==self.treatment_strategy:raise ValueError("Control and treatment strategies must differ")
        return self
class Event(BaseModel):
    event_id:str=Field(min_length=8,max_length=128)
    experiment_id:str=Field(pattern=r"^[a-zA-Z0-9_-]{3,64}$")
    variant:Literal["control","treatment"]
    visitor_id:str=Field(min_length=1,max_length=128)
    request_id:str|None=Field(default=None,max_length=128)
    provider_id:str|None=Field(default=None,max_length=128)
    strategy:Literal["rules","semantic","lambdamart"]
    model_version:str|None=Field(default=None,max_length=128)
    position:int|None=Field(default=None,ge=1,le=100)
    event_type:Literal["search_performed","results_exposed","provider_clicked","provider_shortlisted","contact_initiated","booking_completed"]
    timestamp:str|None=Field(default=None,max_length=64)
    source:Literal["real","simulated"]="simulated"
class ExperimentStore:
    def __init__(self,path:Path):self.path=path;path.parent.mkdir(parents=True,exist_ok=True);self._init()
    def connect(self):return sqlite3.connect(self.path)
    def _init(self):
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS experiments (experiment_id TEXT PRIMARY KEY, config_json TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS assignments (experiment_id TEXT NOT NULL, unit_id TEXT NOT NULL, variant TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'real', PRIMARY KEY(experiment_id,unit_id))")
            assignment_columns={row[1] for row in db.execute("PRAGMA table_info(assignments)")}
            if "source" not in assignment_columns:db.execute("ALTER TABLE assignments ADD COLUMN source TEXT NOT NULL DEFAULT 'real'")
            db.execute("CREATE TABLE IF NOT EXISTS events (event_id TEXT PRIMARY KEY, experiment_id TEXT NOT NULL, variant TEXT NOT NULL, visitor_id TEXT NOT NULL, request_id TEXT, provider_id TEXT, strategy TEXT NOT NULL, model_version TEXT, position INTEGER, event_type TEXT NOT NULL, timestamp TEXT NOT NULL, source TEXT NOT NULL)")
    def create(self,c:ExperimentConfig):
        c.started_at=c.started_at or datetime.now(timezone.utc).isoformat()
        with self.connect() as db:db.execute("INSERT INTO experiments VALUES (?,?)",(c.experiment_id,c.model_dump_json()))
        return c
    def get(self,eid:str):
        with self.connect() as db:row=db.execute("SELECT config_json FROM experiments WHERE experiment_id=?",(eid,)).fetchone()
        return ExperimentConfig.model_validate_json(row[0]) if row else None
    def assignment(self,c:ExperimentConfig,unit:str,source:str="real"):
        with self.connect() as db:
            row=db.execute("SELECT variant,source FROM assignments WHERE experiment_id=? AND unit_id=?",(c.experiment_id,unit)).fetchone()
            if row:
                if source=="real" and row[1]!="real":db.execute("UPDATE assignments SET source='real' WHERE experiment_id=? AND unit_id=?",(c.experiment_id,unit))
                return row[0]
            number=int.from_bytes(hashlib.sha256(f"{c.experiment_salt}:{c.experiment_id}:{unit}".encode()).digest()[:8],"big")/2**64*100
            proposed="treatment" if number<c.allocation_percentage else "control"
            db.execute("INSERT OR IGNORE INTO assignments (experiment_id,unit_id,variant,source) VALUES (?,?,?,?)",(c.experiment_id,unit,proposed,source))
            return db.execute("SELECT variant FROM assignments WHERE experiment_id=? AND unit_id=?",(c.experiment_id,unit)).fetchone()[0]
    def event(self,event:Event):
        with self.connect() as db:
            cur=db.execute("INSERT OR IGNORE INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",(event.event_id,event.experiment_id,event.variant,event.visitor_id,event.request_id,event.provider_id,event.strategy,event.model_version,event.position,event.event_type,event.timestamp or datetime.now(timezone.utc).isoformat(),event.source))
            return cur.rowcount==1
    def reset_simulation(self,eid:str):
        with self.connect() as db:
            db.execute("DELETE FROM assignments WHERE experiment_id=? AND source='simulated'",(eid,))
            db.execute("DELETE FROM events WHERE experiment_id=? AND source='simulated'",(eid,))
    def events(self,eid:str,source:str|None=None):
        with self.connect() as db:
            sql="SELECT variant,visitor_id,event_type FROM events WHERE experiment_id=?";args=[eid]
            if source:sql+=" AND source=?";args.append(source)
            return db.execute(sql,args).fetchall()
    def timeline(self,eid:str,limit:int=100):
        with self.connect() as db:
            rows=db.execute("SELECT timestamp,event_type,variant,visitor_id FROM events WHERE experiment_id=? AND source='simulated' ORDER BY timestamp DESC LIMIT ?",(eid,limit)).fetchall()
        return [{"timestamp":row[0],"event_type":row[1],"variant":row[2],"visitor_id":row[3]} for row in reversed(rows)]
def simulate(store:ExperimentStore,config:ExperimentConfig,service,queries:list,judgments:dict,sessions:int,seed:int=42):
    if not 1<=sessions<=10000:raise ValueError("sessions must be between 1 and 10000")
    rng=random.Random(seed);events=0;visitor_preferences={}
    for session in range(sessions):
        visitor=f"sim-visitor-{session//2:06d}";variant=store.assignment(config,visitor,source="simulated")
        strategy=config.treatment_strategy if variant=="treatment" else config.control_strategy;q=queries[rng.randrange(len(queries))]
        if visitor not in visitor_preferences:visitor_preferences[visitor]=rng.choice([-.45,-.1,.15,.4])
        customer_preference=visitor_preferences[visitor]
        response=service.search(q,strategy,10);request=f"sim-request-{seed}-{session}"
        base={"experiment_id":config.experiment_id,"variant":variant,"visitor_id":visitor,"request_id":request,"strategy":strategy,"model_version":getattr(service,"model_version",None) if strategy=="lambdamart" else None,"source":"simulated"}
        events+=int(store.event(Event(event_id=request+"-search",event_type="search_performed",**base)))
        events+=int(store.event(Event(event_id=request+"-exposure",event_type="results_exposed",**base)))
        for result in response.results:
            pos=result.rank;label=judgments.get(q.query_id,{}).get(result.provider.provider_id,0)
            logit=-3.3+label*.9-math.log2(pos+1)*.45+customer_preference
            if rng.random()<1/(1+math.exp(-logit)):
                events+=int(store.event(Event(event_id=f"{request}-click-{pos}",event_type="provider_clicked",provider_id=result.provider.provider_id,position=pos,**base)))
                if rng.random()<min(.8,.15+label*.12):
                    events+=int(store.event(Event(event_id=f"{request}-shortlist-{pos}",event_type="provider_shortlisted",provider_id=result.provider.provider_id,position=pos,**base)))
                    if rng.random()<min(.65,.08+label*.1):
                        events+=int(store.event(Event(event_id=f"{request}-contact-{pos}",event_type="contact_initiated",provider_id=result.provider.provider_id,position=pos,**base)))
                        if rng.random()<min(.45,.03+label*.07):
                            events+=int(store.event(Event(event_id=f"{request}-booking-{pos}",event_type="booking_completed",provider_id=result.provider.provider_id,position=pos,**base)))
    return {"experiment_id":config.experiment_id,"sessions":sessions,"events_written":events,"source":"simulated","seed":seed}
def report(store:ExperimentStore,c:ExperimentConfig):
    rows=store.events(c.experiment_id,"simulated");visitors={"control":{},"treatment":{}};exposures={"control":set(),"treatment":set()};exposure_events={"control":0,"treatment":0}
    event_counts={}
    for variant,visitor,event in rows:
        event_counts[event]=event_counts.get(event,0)+1
        if variant not in visitors:continue
        if event=="results_exposed":exposures[variant].add(visitor);exposure_events[variant]+=1
        bucket=visitors[variant].setdefault(visitor,{"click":False,"shortlist":False,"contact":False,"booking":False})
        kind={"provider_clicked":"click","provider_shortlisted":"shortlist","contact_initiated":"contact","booking_completed":"booking"}.get(event)
        if kind:bucket[kind]=True
    counts={v:len(exposures[v]) for v in exposures};total=sum(counts.values());expected=total*c.allocation_percentage/100
    chi2=sum((counts[v]-n)**2/n for v,n in [("treatment",expected),("control",total-expected)]) if total and expected and expected<total else 0
    srm_p=math.erfc(math.sqrt(chi2/2)) if total else 1.0;metrics={}
    for kind in ("click","shortlist","contact","booking"):
        values={v:[float(d[kind]) for visitor,d in visitors[v].items() if visitor in exposures[v]] for v in visitors}
        rates={v:(sum(a)/len(a) if a else 0) for v,a in values.items()};diff=rates['treatment']-rates['control'];ci=None
        if all(values.values()):
            rng=random.Random(421);draws=[]
            for _ in range(1500):
                a=values['control'];b=values['treatment'];draws.append(sum(b[rng.randrange(len(b))] for _ in b)/len(b)-sum(a[rng.randrange(len(a))] for _ in a)/len(a))
            draws.sort();ci=[draws[37],draws[1462]]
        metrics[kind]={"control_rate_per_exposed_visitor":rates['control'],"treatment_rate_per_exposed_visitor":rates['treatment'],"difference":diff,"bootstrap_95_ci":ci,"control_visitors":len(values['control']),"treatment_visitors":len(values['treatment'])}
    return {"experiment_id":c.experiment_id,"control_strategy":c.control_strategy,"treatment_strategy":c.treatment_strategy,"allocation_percentage":c.allocation_percentage,"synthetic_traffic":True,"warning":"Simulated experiments validate instrumentation only; they do not demonstrate actual customer conversion improvements.","allocation_counts":counts,"exposure_event_counts":exposure_events,"event_counts":event_counts,"event_timeline":store.timeline(c.experiment_id),"sample_ratio_mismatch":{"chi_square":chi2,"p_value_approx":srm_p,"flagged":bool(total and srm_p<.001)},"metrics":metrics,"sample_size_planning":{"baseline_rate_assumption":.1,"minimum_detectable_absolute_effect":.03,"approx_users_per_arm":int(2*(1.96+.84)**2*.1*.9/(.03**2))},"event_count":len(rows)}

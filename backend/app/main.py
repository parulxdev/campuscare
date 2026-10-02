from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from .db import init_db,get_db
from .models import *
from .schemas import *
from .auth import *
from .services.routing_engine import process_request,check_sla

app=FastAPI(title='CampusCare API',version='1.0.0')
app.add_middleware(CORSMiddleware,allow_origins=['http://localhost:5173','http://127.0.0.1:5173'],allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
@app.on_event('startup')
def startup(): init_db()

def log(db,actor,req,action,old='',new='',reason=''):
    db.add(AuditLog(request_id=req.id if req else None,actor_id=actor.id if actor else None,action=action,old_value=str(old),new_value=str(new),reason=reason))

def allowed(user,req):
    if user.role in ('ADMIN','DEAN'): return True
    if user.role=='STUDENT': return req.student_id==user.id
    if user.role=='TRIAGE_AGENT': return True
    if user.role=='DEPARTMENT_STAFF': return req.primary_department_id==user.department_id or req.assigned_staff_id==user.id
    return False

@app.get('/health')
def health(): return {'status':'ok','service':'CampusCare'}

@app.post('/auth/register')
def register(x:RegisterIn,db:Session=Depends(get_db)):
    if db.query(User).filter(User.email==x.email).first(): raise HTTPException(400,'Email already exists')
    if x.role not in ('STUDENT','TRIAGE_AGENT','DEPARTMENT_STAFF','DEAN','ADMIN'): raise HTTPException(400,'Invalid role')
    u=User(name=x.name,email=x.email,password_hash=hash_password(x.password),role=x.role,department_id=x.department_id)
    db.add(u); db.commit(); db.refresh(u); return {'access_token':create_token(u),'token_type':'bearer','user':user_out(u)}

@app.post('/auth/login')
def login(x:LoginIn,db:Session=Depends(get_db)):
    u=db.query(User).filter(User.email==x.email).first()
    if not u or not verify_password(x.password,u.password_hash): raise HTTPException(401,'Invalid email or password')
    return {'access_token':create_token(u),'token_type':'bearer','user':user_out(u)}

def user_out(u): return {'id':u.id,'name':u.name,'email':u.email,'role':u.role,'department_id':u.department_id,'skill':u.skill}
@app.get('/auth/me')
def me(u=Depends(current_user)): return user_out(u)

@app.get('/departments')
def departments(db:Session=Depends(get_db),u=Depends(current_user)): return [{'id':d.id,'name':d.name,'capability':d.capability} for d in db.query(Department).all()]

@app.post('/requests')
def create_request(x:RequestIn,db:Session=Depends(get_db),u=Depends(require_roles('STUDENT'))):
    n=f'CAM{datetime.utcnow().strftime("%y%m%d")}{db.query(CampusSupportRequest).count()+1:04d}'
    req=CampusSupportRequest(request_number=n,student_id=u.id,title=x.title,description=x.description,privacy_mode=x.privacy_mode,anonymous=x.privacy_mode=='ANONYMOUS',status='NEW')
    db.add(req); db.flush(); analysis=process_request(db,req); log(db,u,req,'AI_TRIAGE',reason='Automated triage')
    db.commit(); db.refresh(req)
    return request_out(req,include_internal=False)

@app.get('/requests/my')
def my_requests(db:Session=Depends(get_db),u=Depends(require_roles('STUDENT'))): return [request_out(r,False) for r in db.query(CampusSupportRequest).filter(CampusSupportRequest.student_id==u.id).order_by(CampusSupportRequest.created_at.desc()).all()]

@app.get('/requests/{rid}')
def get_request(rid:int,db:Session=Depends(get_db),u=Depends(current_user)):
    r=db.get(CampusSupportRequest,rid)
    if not r or not allowed(u,r): raise HTTPException(404,'Request not found')
    return request_out(r,u.role!='STUDENT')

@app.post('/requests/{rid}/message')
def message(rid:int,x:NoteIn,db:Session=Depends(get_db),u=Depends(current_user)):
    r=db.get(CampusSupportRequest,rid)
    if not r or not allowed(u,r): raise HTTPException(404,'Request not found')
    r.updated_at=datetime.utcnow(); log(db,u,r,'FOLLOW_UP',reason=x.note); db.commit(); return {'ok':True}

@app.post('/requests/{rid}/reopen')
def reopen(rid:int,db:Session=Depends(get_db),u=Depends(require_roles('STUDENT'))):
    r=db.get(CampusSupportRequest,rid)
    if not r or r.student_id!=u.id: raise HTTPException(404,'Request not found')
    r.status='REOPENED'; r.reopen_requested=True; r.resolution_confirmed=False; log(db,u,r,'REOPEN'); db.commit(); return request_out(r,False)

@app.get('/staff/requests')
def staff_requests(db:Session=Depends(get_db),u=Depends(require_roles('TRIAGE_AGENT','DEPARTMENT_STAFF','DEAN','ADMIN'))):
    q=db.query(CampusSupportRequest)
    if u.role=='DEPARTMENT_STAFF': q=q.filter(CampusSupportRequest.primary_department_id==u.department_id)
    elif u.role=='DEAN': q=q.filter(CampusSupportRequest.escalation_level>0)
    for r in q.all(): check_sla(db,r)
    db.commit(); return [request_out(r,True,u) for r in q.order_by(CampusSupportRequest.created_at.desc()).all()]

@app.get('/staff/dashboard')
def staff_dashboard(db:Session=Depends(get_db),u=Depends(require_roles('TRIAGE_AGENT','DEPARTMENT_STAFF','DEAN','ADMIN'))):
    rs=db.query(CampusSupportRequest).all()
    for r in rs: check_sla(db,r)
    db.commit()
    visible=rs if u.role in ('TRIAGE_AGENT','ADMIN') else [r for r in rs if (u.role=='DEAN' and r.escalation_level>0) or (u.role=='DEPARTMENT_STAFF' and r.primary_department_id==u.department_id)]
    return {'total_open':sum(r.status not in ('RESOLVED','CLOSED') for r in visible),'human_review':sum(r.status=='AWAITING_HUMAN_REVIEW' for r in visible),'high_priority':sum(r.priority in ('HIGH','CRITICAL') for r in visible),'sla_breached':sum(r.status=='ESCALATED' for r in visible),'active_clusters':db.query(Cluster).filter(Cluster.sensitive==False).count(),'escalated':sum(r.escalation_level>0 for r in visible),'auto_route_rate':round(100*sum(r.ai_confidence>=.85 for r in visible)/max(1,len(visible)),1),'human_fallback_rate':round(100*sum(r.ai_confidence<.85 for r in visible)/max(1,len(visible)),1)}

@app.get('/staff/clusters')
def clusters(db:Session=Depends(get_db),u=Depends(require_roles('TRIAGE_AGENT','DEPARTMENT_STAFF','DEAN','ADMIN'))):
    return [{'id':c.id,'name':c.name,'category':c.category,'affected_count':c.affected_count,'batch_size':c.batch_size,'impact':round(100*c.affected_count/max(1,c.batch_size),1),'priority':c.priority,'status':c.status,'requests':[r.request_number for r in c.requests]} for c in db.query(Cluster).filter(Cluster.sensitive==False).all()]

@app.get('/staff/escalations')
def escalations(db:Session=Depends(get_db),u=Depends(require_roles('TRIAGE_AGENT','DEPARTMENT_STAFF','DEAN','ADMIN'))):
    es=db.query(Escalation).filter(Escalation.closed==False).all(); out=[]
    for e in es:
        r=db.get(CampusSupportRequest,e.request_id)
        if u.role=='DEPARTMENT_STAFF' and r.primary_department_id!=u.department_id: continue
        out.append({'id':e.id,'request':r.request_number,'department':r.department.name if r.department else '—','level':e.level,'reason':e.reason,'next_authority':e.next_authority,'created_at':e.created_at.isoformat()})
    return out

@app.post('/triage/{rid}/override')
def override(rid:int,x:OverrideIn,db:Session=Depends(get_db),u=Depends(require_roles('TRIAGE_AGENT','ADMIN'))):
    r=db.get(CampusSupportRequest,rid)
    if not r: raise HTTPException(404,'Not found')
    old={'category':r.category,'priority':r.priority,'department':r.primary_department_id}
    if x.category: r.category=x.category
    if x.subcategory: r.subcategory=x.subcategory
    if x.priority: r.priority=x.priority
    if x.sensitivity_level: r.sensitivity_level=x.sensitivity_level
    if x.primary_department_id: r.primary_department_id=x.primary_department_id
    r.status='ASSIGNED'; r.reassignment_count+=1
    log(db,u,r,'TRIAGE_OVERRIDE',old,new_value={'category':r.category,'priority':r.priority,'department':r.primary_department_id},reason=x.reason); db.commit(); return request_out(r,True)

@app.post('/routing/{rid}/assign')
def assign(rid:int,db:Session=Depends(get_db),u=Depends(require_roles('TRIAGE_AGENT','ADMIN','DEAN'))):
    r=db.get(CampusSupportRequest,rid)
    if not r: raise HTTPException(404,'Not found')
    from .services.routing_engine import assign_staff
    s=assign_staff(db,r)
    if s: r.status='ASSIGNED'; log(db,u,r,'ASSIGN',new=s.name,reason='Required skill + lowest active workload')
    db.commit(); return request_out(r,True)

@app.post('/requests/{rid}/escalate')
def escalate(rid:int,db:Session=Depends(get_db),u=Depends(require_roles('TRIAGE_AGENT','DEPARTMENT_STAFF','DEAN','ADMIN'))):
    r=db.get(CampusSupportRequest,rid)
    if not r or not allowed(u,r): raise HTTPException(404,'Not found')
    r.escalation_level=min(4,(r.escalation_level or 0)+1); r.status='ESCALATED'; r.escalated_at=datetime.utcnow(); nxt={1:'Department Lead / Supervisor',2:'Dean / Department Authority',3:'Central Student Administration',4:'Senior Authority'}.get(r.escalation_level)
    db.add(Escalation(request_id=r.id,level=r.escalation_level,reason='Manual escalation',next_authority=nxt)); log(db,u,r,'ESCALATE',reason='Manual escalation'); db.commit(); return request_out(r,True)

@app.patch('/requests/{rid}/status')
def update_status(rid:int,x:StatusIn,db:Session=Depends(get_db),u=Depends(require_roles('DEPARTMENT_STAFF','TRIAGE_AGENT','DEAN','ADMIN'))):
    r=db.get(CampusSupportRequest,rid)
    if not r or not allowed(u,r): raise HTTPException(404,'Not found')
    old=r.status; r.status=x.status; r.updated_at=datetime.utcnow()
    if x.status=='RESOLVED': r.resolved_at=datetime.utcnow()
    log(db,u,r,'STATUS_CHANGE',old,x.status); db.commit(); return request_out(r,True)

@app.post('/requests/{rid}/note')
def add_note(rid:int,x:NoteIn,db:Session=Depends(get_db),u=Depends(require_roles('TRIAGE_AGENT','DEPARTMENT_STAFF','DEAN','ADMIN'))):
    r=db.get(CampusSupportRequest,rid)
    if not r or not allowed(u,r): raise HTTPException(404,'Not found')
    db.add(InternalNote(request_id=rid,author_id=u.id,note=x.note)); db.commit(); return {'ok':True}

@app.get('/admin/users')
def admin_users(db:Session=Depends(get_db),u=Depends(require_roles('ADMIN'))): return [user_out(x) for x in db.query(User).all()]
@app.get('/admin/departments')
def admin_depts(db:Session=Depends(get_db),u=Depends(require_roles('ADMIN'))): return [{'id':d.id,'name':d.name} for d in db.query(Department).all()]
@app.get('/admin/audit-logs')
def audit(db:Session=Depends(get_db),u=Depends(require_roles('ADMIN'))): return [{'id':a.id,'request_id':a.request_id,'actor_id':a.actor_id,'action':a.action,'reason':a.reason,'timestamp':a.timestamp.isoformat()} for a in db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(200).all()]

def request_out(r,internal=False,u=None):
    if not internal:
        return {'id':r.id,'request_number':r.request_number,'title':r.title,'description':r.description,'category':r.category,'subcategory':r.subcategory,'priority':r.priority,'sensitivity':r.sensitivity_level,'privacy_mode':r.privacy_mode,'scope':r.scope,'affected_count':r.affected_count,'ai_confidence':r.ai_confidence,'primary_department':r.department.name if r.department else None,'secondary_departments':[x for x in r.secondary_departments.split(',') if x],'status':r.status,'sla_due_at':r.sla_due_at.isoformat() if r.sla_due_at else None,'created_at':r.created_at.isoformat(),'ai_routing_reason':r.ai_routing_reason,'reopen_requested':r.reopen_requested}
    return {'id':r.id,'request_number':r.request_number,'title':r.title,'description':('[IDENTITY HIDDEN — ANONYMOUS]' if r.anonymous and u and u.role=='DEPARTMENT_STAFF' else r.description),'category':r.category,'subcategory':r.subcategory,'priority':r.priority,'sensitivity':r.sensitivity_level,'privacy_mode':r.privacy_mode,'scope':r.scope,'affected_count':r.affected_count,'ai_confidence':r.ai_confidence,'primary_department':r.department.name if r.department else None,'secondary_departments':[x for x in r.secondary_departments.split(',') if x],'assigned_staff':None if r.anonymous and u and u.role=='DEPARTMENT_STAFF' else (r.assigned_staff.name if r.assigned_staff else None),'status':r.status,'sla_due_at':r.sla_due_at.isoformat() if r.sla_due_at else None,'created_at':r.created_at.isoformat(),'ai_routing_reason':r.ai_routing_reason,'escalation_level':r.escalation_level,'cluster':None if r.sensitivity_level=='HIGH' else (r.cluster.name if r.cluster else None),'internal_access':True}

import os,re,json
from datetime import datetime,timedelta
from sqlalchemy.orm import Session
from ..models import *

DEPARTMENTS=['IT Services','Mental Health / Counselling','Academics','Finance / Scholarship','Medical','Hostel','Placement','Disability Support','Campus Safety']
KEYWORDS={
 'IT Services':['portal','login','password','wifi','internet','lms','technical','website','payment portal','access'],
 'Mental Health / Counselling':['counselling','counseling','anxiety','depressed','mental health','stress','suicidal','panic','therapy'],
 'Academics':['course','registration','exam','attendance','faculty','grade','subject','timetable','enrollment'],
 'Finance / Scholarship':['fee','fees','payment','scholarship','refund','tuition','financial aid'],
 'Medical':['doctor','medical','clinic','appointment','fever','pain','injury','chest','sick'],
 'Hostel':['hostel','room','mess','maintenance','warden','water','electricity'],
 'Placement':['placement','job','company','internship','career','campus hiring'],
 'Disability Support':['accessibility','disability','accommodation','wheelchair','assistive'],
 'Campus Safety':['safety','harassment','threat','security','unsafe','emergency','stalking']}

def _dept(db,name): return db.query(Department).filter(Department.name==name).first()

def classify_request(title,description,privacy_mode='NORMAL',db=None):
    text=(title+' '+description).lower()
    scores={d:sum(1 for k in kws if k in text) for d,kws in KEYWORDS.items()}
    best=max(scores,key=scores.get)
    hits=scores[best]
    sensitive=privacy_mode in ('CONFIDENTIAL','ANONYMOUS') or best=='Mental Health / Counselling' or any(k in text for k in KEYWORDS['Mental Health / Counselling'])
    if sensitive: best='Mental Health / Counselling'
    if hits==0:
        confidence=0.43
    else:
        confidence=min(0.96,0.76+0.06*hits)
    if 'cannot' in text or 'unable' in text or 'issue' in text: confidence=min(.98,confidence+.03)
    scope='INDIVIDUAL'
    if re.search(r'\b(all|everyone|campus|nobody|entire campus)\b',text): scope='CAMPUS'
    elif re.search(r'\b(department|dept)\b',text): scope='DEPARTMENT'
    elif re.search(r'\b(batch|2027|2028|2029)\b',text): scope='BATCH'
    elif re.search(r'\b(class|section|cse|ece|students)\b',text): scope='CLASS'
    affected=1
    if scope=='BATCH': affected=10
    elif scope=='CLASS': affected=5
    elif scope=='DEPARTMENT': affected=25
    elif scope=='CAMPUS': affected=100
    deadline_tomorrow='tomorrow' in text or 'deadline' in text
    priority='MEDIUM'
    if sensitive or any(k in text for k in ['emergency','threat','chest pain','suicidal']): priority='CRITICAL'
    elif deadline_tomorrow or affected>=20: priority='HIGH'
    elif affected>=5: priority='MEDIUM'
    sub='General Support'
    mapping={'Finance / Scholarship':'Fee Payment','IT Services':'Portal / Access','Academics':'Course Registration','Mental Health / Counselling':'Counselling','Medical':'Medical Appointment','Hostel':'Maintenance','Placement':'Placement Registration','Disability Support':'Accommodation','Campus Safety':'Safety Concern'}
    sub=mapping[best]
    secondary=[]
    if best=='Finance / Scholarship' and ('portal' in text or 'registration' in text): secondary=['IT Services']
    if best=='Academics' and 'payment' in text: secondary=['Finance / Scholarship','IT Services']
    if best=='IT Services' and ('fee' in text or 'payment' in text): secondary=['Finance / Scholarship']
    skill=sub
    reason=f"Routed to {best} because the issue matches {sub.lower()}."
    if affected>1: reason+=f" {affected} affected students are indicated by the detected {scope.lower()} scope."
    if deadline_tomorrow: reason+=' Priority increased because a deadline is tomorrow.'
    if sensitive: reason='Sensitive case detected; restricted routing to Mental Health / Counselling and no normal clustering.'
    return {'category':best,'subcategory':sub,'primary_department':best,'secondary_departments':secondary,'priority':priority,'sensitivity':'HIGH' if sensitive else 'NORMAL','scope':scope,'affected_count':affected,'required_skill':skill,'confidence':round(confidence,2),'human_review_required':confidence<.85 or confidence<.6,'routing_reason':reason}

def similar_cluster(db,req,analysis):
    if analysis['sensitivity']=='HIGH' or req.privacy_mode in ('CONFIDENTIAL','ANONYMOUS'): return None
    candidates=db.query(CampusSupportRequest).filter(CampusSupportRequest.id!=req.id,CampusSupportRequest.category==analysis['category'],CampusSupportRequest.sensitivity_level=='NORMAL').all()
    words=set(re.findall(r'\w+', (req.title+' '+req.description).lower()))
    best=None; bestscore=0
    for c in candidates:
        cw=set(re.findall(r'\w+', (c.title+' '+c.description).lower()))
        score=len(words&cw)/max(1,len(words|cw))
        if c.subcategory==analysis['subcategory']: score+=.35
        if score>bestscore: bestscore=score; best=c
    if best and bestscore>=.30: return best.cluster or create_cluster(db,best,analysis)
    return create_cluster(db,req,analysis)

def create_cluster(db,req,analysis):
    if analysis['sensitivity']=='HIGH': return None
    names={'Finance / Scholarship':'Fee Payment Failure','IT Services':'Student Portal Access','Academics':'Course Registration','Hostel':'Hostel Maintenance'}
    cl=Cluster(name=names.get(analysis['category'],analysis['subcategory']),category=analysis['category'],affected_count=0,batch_size=100,priority=analysis['priority'],sensitive=False)
    db.add(cl); db.flush(); return cl

def calculate_sla(priority):
    mins={'CRITICAL':30,'HIGH':120,'MEDIUM':480,'LOW':1440}.get(priority,480)
    return datetime.utcnow()+timedelta(minutes=mins),mins

def assign_staff(db,req):
    if not req.primary_department_id or req.sensitivity_level=='HIGH': return None
    staff=db.query(User).filter(User.role=='DEPARTMENT_STAFF',User.department_id==req.primary_department_id,User.available==True).all()
    if not staff: return None
    staff.sort(key=lambda u:(u.active_cases, 0 if req.required_skill.lower() in (u.skill or '').lower() else 1))
    chosen=staff[0]; chosen.active_cases+=1; req.assigned_staff_id=chosen.id
    req.assigned_staff=chosen
    return chosen

def process_request(db,req):
    a=classify_request(req.title,req.description,req.privacy_mode,db)
    req.category=a['category']; req.subcategory=a['subcategory']; req.priority=a['priority']; req.sensitivity_level=a['sensitivity']; req.scope=a['scope']; req.affected_count=a['affected_count']; req.ai_confidence=a['confidence']; req.ai_routing_reason=a['routing_reason']; req.required_skill=a['required_skill']; req.secondary_departments=','.join(a['secondary_departments']); req.last_ai_analysis=json.dumps(a)
    d=_dept(db,a['primary_department']); req.primary_department_id=d.id if d else None
    if a['human_review_required']: req.status='AWAITING_HUMAN_REVIEW'
    else: req.status='ASSIGNED'
    due,_=calculate_sla(req.priority); req.sla_due_at=due
    cl=similar_cluster(db,req,a)
    if cl:
        req.cluster_id=cl.id
        cl.affected_count=(cl.affected_count or 0)+1
        cl.priority='HIGH' if req.priority in ('HIGH','CRITICAL') else cl.priority
    if not a['human_review_required']: assign_staff(db,req)
    return a

def check_sla(db,req):
    if req.status in ('RESOLVED','CLOSED'): return False
    if req.sla_due_at and datetime.utcnow()>req.sla_due_at:
        req.status='ESCALATED'; req.escalation_level=max(req.escalation_level or 0,1); req.escalated_at=datetime.utcnow()
        next_auth={1:'Department Lead / Supervisor',2:'Dean / Department Authority',3:'Central Student Administration'}.get(req.escalation_level,'Central Student Administration')
        db.add(Escalation(request_id=req.id,level=req.escalation_level,reason='SLA breached',next_authority=next_auth))
        return True
    return False

from app.db import init_db,SessionLocal
from app.models import *
from app.auth import hash_password
from app.services.routing_engine import process_request

def seed():
 init_db(); db=SessionLocal()
 if db.query(User).count(): print('Seed already exists'); return
 deps=[('IT Services','Portal, authentication and technical support'),('Mental Health / Counselling','Restricted counselling and wellbeing'),('Academics','Courses, registration and exams'),('Finance / Scholarship','Fees, payments and scholarships'),('Medical','Health and appointments'),('Hostel','Accommodation and maintenance'),('Placement','Career and placement services'),('Disability Support','Accessibility and accommodations'),('Campus Safety','Safety and security')]
 for n,c in deps: db.add(Department(name=n,capability=c))
 db.flush(); dm={d.name:d for d in db.query(Department).all()}
 users=[]
 def add(name,email,role,dept=None,skill='General Support',active=0):
  u=User(name=name,email=email,password_hash=hash_password('Pass@123'),role=role,department_id=dm[dept].id if dept else None,skill=skill,active_cases=active,available=True); db.add(u); db.flush(); users.append(u); return u
 add('Aarav Student','student@campuscare.local','STUDENT')
 add('Isha Student','student2@campuscare.local','STUDENT')
 add('Triage Lead','triage@campuscare.local','TRIAGE_AGENT',None,'Triage',2)
 add('IT Resolver','it@campuscare.local','DEPARTMENT_STAFF','IT Services','Portal / Access',8)
 add('Finance Resolver','finance@campuscare.local','DEPARTMENT_STAFF','Finance / Scholarship','Fee Payment',3)
 add('Academic Resolver','academics@campuscare.local','DEPARTMENT_STAFF','Academics','Course Registration',5)
 add('Counselling Specialist','counselling@campuscare.local','DEPARTMENT_STAFF','Mental Health / Counselling','Counselling',1)
 add('Medical Resolver','medical@campuscare.local','DEPARTMENT_STAFF','Medical','Medical Appointment',2)
 add('Hostel Resolver','hostel@campuscare.local','DEPARTMENT_STAFF','Hostel','Maintenance',4)
 add('Placement Resolver','placement@campuscare.local','DEPARTMENT_STAFF','Placement','Placement Registration',2)
 add('Disability Resolver','disability@campuscare.local','DEPARTMENT_STAFF','Disability Support','Accommodation',1)
 add('Safety Resolver','safety@campuscare.local','DEPARTMENT_STAFF','Campus Safety','Safety Concern',1)
 add('Dean Authority','dean@campuscare.local','DEAN')
 add('System Admin','admin@campuscare.local','ADMIN')
 student=users[0]
 examples=[
 ('Fee payment failed','I cannot pay my semester fee through the portal.'),('Scholarship application issue','My scholarship application has not updated.'),('Course registration problem','I cannot register for my courses.'),('Student portal login issue','I cannot access the student portal.'),('Hostel maintenance issue','My hostel room water supply needs maintenance.'),('Placement registration issue','I cannot complete placement registration.'),('Medical appointment request','I need a medical appointment.'),('Disability accommodation request','I need accessibility accommodation for exams.'),('Campus safety complaint','There is a safety concern near the hostel.'),('Mental health counselling request','I would like to request counselling support.'),('Anonymous sensitive request','I need private counselling and do not want my identity exposed.'),('Batch-wide fee issue','Many students in our 2027 batch cannot pay fees and the deadline is tomorrow.'),('IT request 1','Student portal login is failing for me.'),('IT request 2','Unable to access the student portal.'),('IT request 3','Portal access error when I sign in.'),('Ambiguous request','I have a problem and I do not know where to report it.'),('Old SLA case','My urgent issue is still unresolved.')]
 for i,(t,d) in enumerate(examples):
  r=CampusSupportRequest(request_number=f'CAMSEED{i+1:04d}',student_id=student.id,title=t,description=d,privacy_mode='ANONYMOUS' if 'Anonymous' in t else 'NORMAL')
  db.add(r); db.flush(); process_request(db,r)
  if t=='Old SLA case':
   from datetime import datetime,timedelta
   r.sla_due_at=datetime.utcnow()-timedelta(hours=2); r.status='ASSIGNED'
 # add extra similar cases to ensure a visible 10+ cluster
 for i in range(10):
  r=CampusSupportRequest(request_number=f'CAMFEE{i+1:04d}',student_id=student.id,title=f'Fee portal failure {i+1}',description='Semester fee payment portal failure for registration.',privacy_mode='NORMAL')
  db.add(r); db.flush(); process_request(db,r)
 db.commit(); print('Seed complete')
 print('All demo passwords: Pass@123')

if __name__=='__main__': seed()

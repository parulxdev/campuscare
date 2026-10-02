from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

class User(Base):
    __tablename__='users'
    id=Column(Integer, primary_key=True)
    name=Column(String(120), nullable=False)
    email=Column(String(180), unique=True, nullable=False)
    password_hash=Column(String(255), nullable=False)
    role=Column(String(40), nullable=False, default='STUDENT')
    department_id=Column(Integer, ForeignKey('departments.id'), nullable=True)
    active_cases=Column(Integer, default=0)
    available=Column(Boolean, default=True)
    skill=Column(String(120), default='General Support')
    department=relationship('Department', back_populates='users')

class Department(Base):
    __tablename__='departments'
    id=Column(Integer, primary_key=True)
    name=Column(String(120), unique=True, nullable=False)
    capability=Column(String(255), default='General student support')
    users=relationship('User', back_populates='department')

class CampusSupportRequest(Base):
    __tablename__='requests'
    id=Column(Integer, primary_key=True)
    request_number=Column(String(30), unique=True, nullable=False)
    student_id=Column(Integer, ForeignKey('users.id'), nullable=False)
    title=Column(String(255), nullable=False)
    description=Column(Text, nullable=False)
    category=Column(String(80))
    subcategory=Column(String(120))
    priority=Column(String(20), default='MEDIUM')
    sensitivity_level=Column(String(20), default='NORMAL')
    privacy_mode=Column(String(20), default='NORMAL')
    anonymous=Column(Boolean, default=False)
    scope=Column(String(30), default='INDIVIDUAL')
    affected_count=Column(Integer, default=1)
    batch_size=Column(Integer, default=100)
    cluster_id=Column(Integer, ForeignKey('clusters.id'), nullable=True)
    ai_confidence=Column(Float, default=0.0)
    ai_routing_reason=Column(Text, default='')
    required_skill=Column(String(120), default='General Support')
    primary_department_id=Column(Integer, ForeignKey('departments.id'), nullable=True)
    secondary_departments=Column(String(255), default='')
    assigned_staff_id=Column(Integer, ForeignKey('users.id'), nullable=True)
    status=Column(String(40), default='NEW')
    sla_due_at=Column(DateTime)
    created_at=Column(DateTime, default=datetime.utcnow)
    updated_at=Column(DateTime, default=datetime.utcnow)
    resolved_at=Column(DateTime, nullable=True)
    resolution_confirmed=Column(Boolean, default=False)
    reopen_requested=Column(Boolean, default=False)
    escalation_level=Column(Integer, default=0)
    escalated_at=Column(DateTime, nullable=True)
    last_ai_analysis=Column(Text, default='')
    reassignment_count=Column(Integer, default=0)
    student=relationship('User', foreign_keys=[student_id])
    department=relationship('Department', foreign_keys=[primary_department_id])
    assigned_staff=relationship('User', foreign_keys=[assigned_staff_id])
    cluster=relationship('Cluster', back_populates='requests')

class Cluster(Base):
    __tablename__='clusters'
    id=Column(Integer, primary_key=True)
    name=Column(String(160), nullable=False)
    category=Column(String(80))
    affected_count=Column(Integer, default=0)
    batch_size=Column(Integer, default=100)
    priority=Column(String(20), default='MEDIUM')
    sensitive=Column(Boolean, default=False)
    status=Column(String(40), default='Investigating')
    created_at=Column(DateTime, default=datetime.utcnow)
    requests=relationship('CampusSupportRequest', back_populates='cluster')

class SLARecord(Base):
    __tablename__='sla_records'
    id=Column(Integer, primary_key=True)
    request_id=Column(Integer, ForeignKey('requests.id'), nullable=False)
    due_at=Column(DateTime, nullable=False)
    status=Column(String(30), default='WITHIN_SLA')
    time_remaining_minutes=Column(Integer, default=0)

class Escalation(Base):
    __tablename__='escalations'
    id=Column(Integer, primary_key=True)
    request_id=Column(Integer, ForeignKey('requests.id'), nullable=False)
    level=Column(Integer, default=1)
    reason=Column(String(255))
    next_authority=Column(String(120))
    created_at=Column(DateTime, default=datetime.utcnow)
    closed=Column(Boolean, default=False)

class AuditLog(Base):
    __tablename__='audit_logs'
    id=Column(Integer, primary_key=True)
    request_id=Column(Integer, ForeignKey('requests.id'), nullable=True)
    actor_id=Column(Integer, ForeignKey('users.id'), nullable=True)
    action=Column(String(120), nullable=False)
    old_value=Column(Text, default='')
    new_value=Column(Text, default='')
    reason=Column(Text, default='')
    timestamp=Column(DateTime, default=datetime.utcnow)

class Notification(Base):
    __tablename__='notifications'
    id=Column(Integer, primary_key=True)
    user_id=Column(Integer, ForeignKey('users.id'), nullable=False)
    message=Column(Text, nullable=False)
    read=Column(Boolean, default=False)
    created_at=Column(DateTime, default=datetime.utcnow)

class InternalNote(Base):
    __tablename__='internal_notes'
    id=Column(Integer, primary_key=True)
    request_id=Column(Integer, ForeignKey('requests.id'), nullable=False)
    author_id=Column(Integer, ForeignKey('users.id'), nullable=False)
    note=Column(Text, nullable=False)
    created_at=Column(DateTime, default=datetime.utcnow)

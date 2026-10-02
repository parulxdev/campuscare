# CampusCare

**AI-Powered Student Triage & Intelligent Support Routing**

A demo-ready prototype for Student Triage & Routing. The design follows the supplied challenge brief: the central feature is intelligent triage, routing, escalation and privacy-aware handling rather than a generic helpdesk.

## Stack
- Frontend: React + Vite + Tailwind CSS + Recharts
- Backend: FastAPI + SQLAlchemy
- Database: SQLite
- AI: deterministic classifier by default; API-ready integration point in `backend/app/services/routing_engine.py`
- Auth: JWT + bcrypt password hashing

## Run locally

### 1. Backend
```bash
cd backend
python -m venv .venv
# Windows
.venv\\Scripts\\activate
# macOS/Linux
source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env  # Windows
# cp .env.example .env # macOS/Linux
python seed.py
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend
Open another terminal:
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:5173

## Demo credentials
All passwords: `Pass@123`

| Role | Email |
|---|---|
| Student | student@campuscare.local |
| Triage Agent | triage@campuscare.local |
| Department Staff | finance@campuscare.local |
| Dean | dean@campuscare.local |
| Admin | admin@campuscare.local |

## Main demo flow
1. Login as student.
2. Submit: `Our CSE 2027 batch is unable to complete fee payment for course registration. The payment portal keeps failing and the registration deadline is tomorrow.`
3. Observe AI category, primary Finance routing, IT support, batch scope, high priority and confidence.
4. Login as Triage Agent and open Command Center / Request Queue.
5. Show non-sensitive Fee Payment Failure clustering and impact.
6. Show an anonymous mental-health request: it bypasses normal clustering and uses restricted routing.
7. Show the ambiguous request: low confidence sends it to Human Review.
8. Show Escalations to demonstrate SLA/authority hierarchy.

## Routing architecture
`Request -> classify -> sensitivity/scope -> impact/priority -> similarity cluster (non-sensitive only) -> primary + supporting departments -> workload-aware staff assignment -> SLA -> escalation`.

The backend validates AI-like outputs against known department/category values and uses deterministic fallback logic so the demo works without an external AI key.

## RBAC
Backend APIs use JWT authentication and role checks. Students can only see their own requests. Department staff are scoped to their department. Triage agents can override routing. Dean sees escalated/hierarchy cases. Admin has full management/audit access.

## Clustering
Clustering is an impact-analysis layer. Student cases are never merged. Sensitive/high-sensitivity requests are excluded from normal clustering. The fallback uses token overlap + category/subcategory matching; it is structured so embeddings can be added later.

## Sensitive / anonymous routing
Mental-health or sensitive requests are routed to Mental Health / Counselling, excluded from normal cluster analytics, and anonymous resolver views hide student identity.

## SLA escalation
SLA windows are configurable in the routing engine. When a case breaches its SLA, the status becomes `ESCALATED` and an escalation record is created with the next authority. The demo hierarchy is staff -> department lead -> dean -> central student administration.

## API docs
With the backend running, open http://127.0.0.1:8000/docs


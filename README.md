# City of Harare — Financial Management System (FMS)
## Revenue Leakage Mitigation Platform
### Dissertation Project | Terrence Muromba | 2026

---

## Overview

This system is developed as an artefact for the dissertation titled:
**"A Financial Management System to Mitigate Revenue Leakage in the City of Harare"**

It implements Design Science Research (DSR) methodology, combining:
- Qualitative insights from City of Harare officials
- Quantitative anomaly detection on financial data
- A fully functional web-based FMS prototype

---

## Technology Stack

| Layer      | Technology                        |
|------------|-----------------------------------|
| Backend    | Python 3.10+ / FastAPI            |
| Database   | SQLite (via SQLAlchemy ORM)       |
| Auth       | JWT (python-jose) + bcrypt        |
| Frontend   | Vanilla HTML / CSS / JavaScript   |
| Charts     | Chart.js 4.4                      |
| Analysis   | Python (pandas, numpy)            |

---

## Quick Start

### Windows
Double-click `START_FMS.bat`
The browser will open automatically at: http://localhost:8000/static/pages/login.html

### Manual Start
```bash
cd backend
pip install fastapi uvicorn sqlalchemy python-jose passlib python-multipart bcrypt
python database.py
python seed.py
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
Then open: http://localhost:8000/static/pages/login.html

---

## Login Credentials

| Role              | Username    | Password     |
|-------------------|-------------|--------------|
| System Admin      | admin       | admin123     |
| Revenue Officer   | r.officer1  | password123  |
| Auditor           | auditor1    | password123  |
| Budget Officer    | budget1     | password123  |
| Accountant        | t.muromba   | password123  |

---

## System Modules

| Module              | Description                                                        |
|---------------------|--------------------------------------------------------------------|
| Dashboard           | KPI overview, charts, collection rate, leakage estimates           |
| Ratepayer Registry  | Register/search ratepayers by zone, ward, property type            |
| Invoice Management  | Create invoices, track status, anomaly flags                       |
| Payment Records     | Record payments, reconcile, detect unlinked payments               |
| Expenditure         | Log expenditures, approve, detect budget anomalies                 |
| Budget Overview     | Departmental budget utilisation with visual progress bars          |
| Leakage Monitor     | Core anomaly dashboard — flags, alerts, estimated leakage value    |
| Audit Trail         | Immutable log of all system actions (admin/auditor only)           |
| User Management     | View all users and roles (admin only)                              |

---

## Revenue Leakage Detection Logic

The system detects leakage through three mechanisms:

1. **Anomaly Flagging** — Invoices/payments are compared to category averages.
   Amounts significantly below average are flagged (low/medium/high).

2. **Reconciliation Tracking** — All payments must be reconciled against invoices.
   Unreconciled payments trigger leakage alerts.

3. **Alert Engine** — Pre-seeded and dynamically generated alerts cover:
   - Duplicate billing patterns
   - Unusual waiver spikes
   - Cash collection gaps
   - Stale overdue accounts
   - Budget overrun risks

---

## API Endpoints (FastAPI)

Interactive documentation available at: http://localhost:8000/docs

Key endpoints:
- `POST /api/auth/login` — Authenticate user
- `GET  /api/dashboard/summary` — KPI summary
- `GET  /api/ratepayers` — List ratepayers
- `POST /api/invoices` — Create invoice
- `POST /api/payments` — Record payment
- `GET  /api/leakage/summary` — Leakage metrics
- `GET  /api/audit-logs` — Audit trail

---

## File Structure

```
fms/
├── START_FMS.bat          ← Double-click to run on Windows
├── README.md
├── backend/
│   ├── main.py            ← FastAPI app + all routes
│   ├── database.py        ← SQLAlchemy models
│   ├── auth.py            ← JWT authentication
│   ├── seed.py            ← Demo data seeder
│   └── fms_harare.db      ← SQLite database (auto-created)
└── frontend/
    ├── css/
    │   └── shared.css
    ├── js/
    │   └── shared.js
    └── pages/
        ├── login.html
        ├── dashboard.html
        ├── ratepayers.html
        ├── invoices.html
        ├── payments.html
        ├── expenditures.html
        ├── budget.html
        ├── leakage.html
        ├── audit.html
        └── users.html
```

---

*City of Harare FMS · Dissertation Artefact · © 2026*

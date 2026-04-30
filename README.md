# City of Harare — Financial Management System (FMS v2.1)

A web-based Financial Management System designed to reduce and mitigate revenue leakage
in the City of Harare through automation, internal controls, and AI-driven analytics.

## What's New in v2.1

### Security Improvements
- **Brute-force lockout** — accounts lock for 30 minutes after 5 failed login attempts
- **Login attempt audit log** — all logins (success and failure) tracked with IP address
- **Password strength enforcement** — uppercase + lowercase + digit + 8 char minimum
- **Enhanced reconciliation** — records who reconciled a payment and when
- **Segregation of duties** — reconciliation restricted to admin/accountant/auditor roles

### AI / Analytics
- **Ratepayer Risk Scoring** — composite 0-100 risk score per ratepayer (4 factors)
- **Revenue Prediction** — OLS linear regression forecast for next month's revenue
- **Duplicate invoice detection** — SHA-256 fingerprint prevents duplicate billing

### Leakage Detection (now 7 rules)
1. Ghost accounts (12+ months no payment, outstanding balance)
2. Unlinked cash payments (cash with no invoice reference)
3. Stale high-value overdue invoices (>180 days, >$500)
4. Officer collection gap (Z-score below peer average)
5. Waived invoices with no audit trail
6. **NEW: Duplicate payments** (same ratepayer, amount, date)
7. **NEW: Round-trip waiver** (waiver + payment same account same day)

### New Modules
- **Payment Plans** — instalment arrangements for ratepayers with large debts
- **In-App Notifications** — per-user and broadcast notification system
- **Risk Register** — exportable risk register with colour-coded Excel output

### Data Integrity
- Alert resolution now requires mandatory resolution_notes for accountability
- Invoice creation returns duplicate warning if fingerprint already exists

## Quick Start

### Prerequisites
- Python 3.10+
- pip

### Installation

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Then open `frontend/pages/login.html` in your browser, or visit `http://localhost:8000`.

### Default Credentials
Run `python seed.py` to populate the database with sample data.

| Username | Password    | Role            |
|----------|-------------|-----------------|
| admin    | Admin123    | Administrator   |
| officer1 | Officer123  | Revenue Officer |
| auditor1 | Auditor123  | Auditor         |

## API Endpoints (v2.1 additions)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/security/login-attempts` | View login attempt history |
| POST | `/api/security/unlock-user/{id}` | Unlock a locked account |
| POST | `/api/ai/compute-risk-scores` | Run AI risk scoring |
| GET | `/api/ai/risk-register` | Ratepayer risk register |
| GET | `/api/ai/revenue-prediction` | Next-month revenue forecast |
| POST | `/api/invoices/check-duplicate` | Pre-creation duplicate check |
| GET | `/api/payment-plans` | List payment plans |
| POST | `/api/payment-plans` | Create instalment plan |
| PATCH | `/api/payment-plans/{id}/record-instalment` | Record instalment paid |
| PATCH | `/api/payment-plans/{id}/default` | Mark plan as defaulted |
| GET | `/api/notifications` | Get notifications |
| GET | `/api/notifications/unread-count` | Unread count for badge |
| PATCH | `/api/notifications/{id}/read` | Mark notification read |
| POST | `/api/notifications/broadcast` | Admin broadcast notification |
| GET | `/api/reports/risk-register` | Risk register export (JSON/CSV/XLSX) |

## System Architecture

```
backend/
  main.py        — FastAPI application (all endpoints, v2.1 integrated)
  database.py    — SQLAlchemy models (v2.1 schema with new tables)
  auth.py        — JWT authentication and role checking
  seed.py        — Database seeding with sample data
  requirements.txt

frontend/
  pages/         — HTML pages (dashboard, invoices, payments, leakage, etc.)
  css/shared.css — Shared stylesheet
  js/shared.js   — Shared JavaScript utilities
```

## Technology Stack
- **Backend**: Python, FastAPI, SQLAlchemy, SQLite
- **Authentication**: JWT (python-jose), bcrypt password hashing
- **Frontend**: Vanilla JavaScript, Chart.js, HTML/CSS
- **Export**: openpyxl (Excel), CSV (stdlib)

## Deployment (Render.com)
See `render.yaml` for configuration. Set `FMS_SECRET_KEY` environment variable in production.

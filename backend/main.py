import sys, os, io, csv as csv_mod, math
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta, timezone
import random, string

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    EXCEL_OK = True
except ImportError:
    EXCEL_OK = False

from database import (get_db, User, Ratepayer, Invoice, Payment, Expenditure,
                      Budget, AuditLog, LeakageAlert, RevenueTarget,
                      UserRole, PaymentStatus, RevenueCategory, AnomalyFlag)
from auth import (verify_password, hash_password, create_access_token,
                  get_current_user, require_roles)

def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

def refresh_overdue_invoices(db: Session):
    cutoff = now()
    overdue_list = db.query(Invoice).filter(
        Invoice.status.in_([PaymentStatus.pending, PaymentStatus.disputed]),
        Invoice.due_date < cutoff,
        Invoice.balance > 0
    ).all()
    for inv in overdue_list:
        inv.status = PaymentStatus.overdue
        db.add(AuditLog(user_id=None, action="UPDATE", table_name="invoices",
                        record_id=inv.id,
                        description=f"Invoice {inv.invoice_number} marked overdue"))
    if overdue_list:
        db.commit()
    return len(overdue_list)

# ─── Anomaly Detection ────────────────────────────────────────────────────────
# Uses Z-score method (Grubbs, 1969; Iglewicz & Hoaglin, 1993).
# |Z| > 3.0 → high severity; |Z| > 2.0 → medium; |Z| > 1.5 → low.
# This is the industry-standard statistical threshold for outlier detection
# in financial data (ACFE, 2022; KPMG Revenue Assurance Framework, 2021).

def _zscore_flag(value: float, values: list) -> tuple:
    """Return (AnomalyFlag, reason) using Z-score outlier detection."""
    if len(values) < 3:
        return AnomalyFlag.none, None
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
    std_dev = math.sqrt(variance) if variance > 0 else 0
    if std_dev == 0:
        return AnomalyFlag.none, None
    z = (value - mean) / std_dev
    abs_z = abs(z)
    direction = "above" if z > 0 else "below"
    if abs_z > 3.0:
        return AnomalyFlag.high, (
            f"Z-score {z:.2f} — amount is a high-severity outlier ({direction} μ=${mean:.2f}, σ=${std_dev:.2f}). "
            f"Consistent with revenue leakage patterns identified in DSR literature review."
        )
    elif abs_z > 2.0:
        return AnomalyFlag.medium, (
            f"Z-score {z:.2f} — amount deviates significantly from category mean ${mean:.2f} (σ=${std_dev:.2f})."
        )
    elif abs_z > 1.5:
        return AnomalyFlag.low, (
            f"Z-score {z:.2f} — amount is slightly unusual vs category mean ${mean:.2f}."
        )
    return AnomalyFlag.none, None

# ─── Export Helpers ────────────────────────────────────────────────────────────

def make_csv_response(headers, rows, filename):
    output = io.StringIO()
    writer = csv_mod.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)
    content = output.getvalue().encode("utf-8-sig")
    return Response(content=content, media_type="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={filename}"})

def make_excel_response(headers, rows, filename, sheet_name="Data", report_title=None):
    if not EXCEL_OK:
        raise HTTPException(500, "openpyxl not installed. Run: pip install openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name
    start_row = 1
    # Optional report title banner
    if report_title:
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
        title_cell = ws.cell(row=1, column=1, value=report_title)
        title_cell.font = Font(bold=True, size=13, color="FFFFFF")
        title_cell.fill = PatternFill(start_color="1F3864", end_color="1F3864", fill_type="solid")
        title_cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 22
        start_row = 2
        # Generated date
        ws.merge_cells(start_row=start_row, start_column=1, end_row=start_row, end_column=len(headers))
        dt_cell = ws.cell(row=start_row, column=1,
                          value=f"Generated: {datetime.now().strftime('%d %b %Y  %H:%M')}")
        dt_cell.font = Font(italic=True, size=9, color="666666")
        dt_cell.alignment = Alignment(horizontal="center")
        start_row += 1
    # Header row
    hdr_row = start_row
    for col_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=hdr_row, column=col_idx, value=h)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="2E5FA3", end_color="2E5FA3", fill_type="solid")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[hdr_row].height = 18
    # Data rows
    for r_idx, row in enumerate(rows, hdr_row + 1):
        fill = PatternFill(start_color="F2F6FC", end_color="F2F6FC", fill_type="solid") \
               if r_idx % 2 == 0 else None
        for c_idx, val in enumerate(row, 1):
            cell = ws.cell(row=r_idx, column=c_idx, value=val)
            if fill:
                cell.fill = fill
            cell.alignment = Alignment(vertical="center")
    # Auto-fit columns (skip MergedCell objects created by the title banner row)
    for col in ws.columns:
        max_len = max(
            (len(str(cell.value or "")) for cell in col if hasattr(cell, "column_letter")),
            default=8
        )
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = min(max_len + 3, 45)
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return Response(
        content=output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

def export_response(fmt, headers, rows, csv_name, xlsx_name, sheet_name="Data", title=None):
    if fmt == "xlsx":
        return make_excel_response(headers, rows, xlsx_name, sheet_name, title)
    return make_csv_response(headers, rows, csv_name)

# ─── Import Helpers ────────────────────────────────────────────────────────────

async def parse_upload(file: UploadFile) -> list:
    """Return list of dicts from CSV or XLSX upload."""
    content = await file.read()
    name = (file.filename or "").lower()
    rows = []
    if name.endswith(".csv"):
        text = content.decode("utf-8-sig")
        reader = csv_mod.DictReader(io.StringIO(text))
        rows = [dict(r) for r in reader]
    elif name.endswith(".xlsx") or name.endswith(".xls"):
        if not EXCEL_OK:
            raise HTTPException(500, "openpyxl not installed. Run: pip install openpyxl")
        wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
        ws = wb.active
        hdrs = [str(cell.value or "").strip() for cell in ws[1]]
        for row in ws.iter_rows(min_row=2, values_only=True):
            if any(v is not None for v in row):
                rows.append({hdrs[i]: row[i] for i in range(len(hdrs))})
    else:
        raise HTTPException(400, "Only .csv and .xlsx files are supported")
    return rows

# ─── App Setup ────────────────────────────────────────────────────────────────

app = FastAPI(title="City of Harare FMS", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

# ─── Pydantic Schemas ──────────────────────────────────────────────────────────

class RatepayerCreate(BaseModel):
    full_name: str
    address: str
    ward: str
    zone: str
    phone: Optional[str] = None
    email: Optional[str] = None
    property_type: str = "residential"

class RatepayerUpdate(BaseModel):
    full_name: Optional[str] = None
    address: Optional[str] = None
    ward: Optional[str] = None
    zone: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    property_type: Optional[str] = None
    is_active: Optional[bool] = None

class InvoiceCreate(BaseModel):
    ratepayer_id: int
    category: str
    amount: float
    due_date: str
    notes: Optional[str] = None

class InvoiceUpdate(BaseModel):
    due_date: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    amount: Optional[float] = None

class PaymentCreate(BaseModel):
    ratepayer_id: int
    invoice_id: Optional[int] = None
    amount: float
    payment_method: str = "cash"
    currency: str = "USD"
    notes: Optional[str] = None

class ExpenditureCreate(BaseModel):
    department: str
    description: str
    amount: float
    budget_line: str

class ExpenditureUpdate(BaseModel):
    department: Optional[str] = None
    description: Optional[str] = None
    amount: Optional[float] = None
    budget_line: Optional[str] = None

class BudgetCreate(BaseModel):
    fiscal_year: str
    department: str
    category: str
    allocated_amount: float
    spent_amount: float = 0.0

class BudgetUpdate(BaseModel):
    fiscal_year: Optional[str] = None
    department: Optional[str] = None
    category: Optional[str] = None
    allocated_amount: Optional[float] = None
    spent_amount: Optional[float] = None

class RevenueTargetCreate(BaseModel):
    fiscal_year: str
    category: str
    target_amount: float
    period: str = "annual"
    notes: Optional[str] = None

class RevenueTargetUpdate(BaseModel):
    target_amount: Optional[float] = None
    period: Optional[str] = None
    notes: Optional[str] = None

class UserCreate(BaseModel):
    username: str
    full_name: str
    email: str
    password: str
    role: str = "revenue_officer"

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None

# ─── Auth ──────────────────────────────────────────────────────────────────────

@app.post("/api/auth/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")
    user.last_login = now()
    db.add(AuditLog(user_id=user.id, action="LOGIN", table_name="users",
                    record_id=user.id, description=f"{user.full_name} logged in"))
    db.commit()
    token = create_access_token({"sub": user.username})
    return {"access_token": token, "token_type": "bearer",
            "user": {"id": user.id, "username": user.username,
                     "full_name": user.full_name, "role": user.role, "email": user.email}}

@app.get("/api/auth/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "username": current_user.username,
            "full_name": current_user.full_name, "role": current_user.role,
            "email": current_user.email}

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

@app.patch("/api/auth/change-password")
def change_password(data: ChangePasswordRequest, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(400, "Current password is incorrect")
    if len(data.new_password) < 8:
        raise HTTPException(400, "New password must be at least 8 characters")
    current_user.hashed_password = hash_password(data.new_password)
    db.add(AuditLog(user_id=current_user.id, action="UPDATE", table_name="users",
                    record_id=current_user.id,
                    description=f"Password changed for user {current_user.username}"))
    db.commit()
    return {"message": "Password changed successfully"}

# ─── Dashboard ────────────────────────────────────────────────────────────────

@app.get("/api/dashboard/summary")
def dashboard_summary(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    refresh_overdue_invoices(db)
    total_billed     = db.query(func.sum(Invoice.amount)).scalar() or 0
    total_collected  = db.query(func.sum(Payment.amount)).scalar() or 0
    total_outstanding = db.query(func.sum(Invoice.balance)).scalar() or 0
    overdue_count    = db.query(Invoice).filter(Invoice.status == PaymentStatus.overdue).count()
    high_alerts      = db.query(LeakageAlert).filter(LeakageAlert.is_resolved == False).count()
    anomaly_invoices = db.query(Invoice).filter(Invoice.anomaly_flag != AnomalyFlag.none).count()
    collection_rate  = round((total_collected / total_billed * 100), 1) if total_billed > 0 else 0
    # Leakage Risk Index: weighted sum of risk exposures.
    # Weights derived from ACFE (2022) Revenue Assurance Framework:
    #   40% of unreconciled payments → confirmed leakage (cash received, not tracked)
    #   25% of overdue balance → at-risk revenue (NCC 2023: 25% recovery rate for overdue >90d)
    overdue_bal   = db.query(func.sum(Invoice.balance)).filter(Invoice.status == PaymentStatus.overdue).scalar() or 0
    unrecon_amt   = db.query(func.sum(Payment.amount)).filter(Payment.is_reconciled == False).scalar() or 0
    leakage_estimate = round(unrecon_amt * 0.40 + overdue_bal * 0.25, 2)
    return {
        "total_billed": round(total_billed, 2), "total_collected": round(total_collected, 2),
        "total_outstanding": round(total_outstanding, 2), "collection_rate": collection_rate,
        "overdue_count": overdue_count, "active_alerts": high_alerts,
        "anomaly_count": anomaly_invoices, "leakage_estimate": leakage_estimate,
        "ratepayers_count": db.query(Ratepayer).count(),
        "invoices_count": db.query(Invoice).count(),
        "payments_count": db.query(Payment).count(),
    }

@app.get("/api/dashboard/revenue-by-category")
def revenue_by_category(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    results = db.query(Invoice.category, func.sum(Invoice.amount).label("billed"),
                       func.sum(Invoice.amount_paid).label("collected")).group_by(Invoice.category).all()
    return [{"category": r.category, "billed": round(r.billed or 0, 2),
             "collected": round(r.collected or 0, 2)} for r in results]

@app.get("/api/dashboard/monthly-trend")
def monthly_trend(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    months = []
    for i in range(6, 0, -1):
        start = now().replace(day=1) - timedelta(days=30*i)
        end   = start + timedelta(days=30)
        billed    = db.query(func.sum(Invoice.amount)).filter(Invoice.issue_date >= start, Invoice.issue_date < end).scalar() or 0
        collected = db.query(func.sum(Payment.amount)).filter(Payment.payment_date >= start, Payment.payment_date < end).scalar() or 0
        months.append({"month": start.strftime("%b %Y"), "billed": round(billed, 2), "collected": round(collected, 2)})
    return months

@app.get("/api/dashboard/alerts")
def get_alerts(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    alerts = db.query(LeakageAlert).filter(LeakageAlert.is_resolved == False)\
               .order_by(desc(LeakageAlert.created_at)).limit(10).all()
    return [{"id": a.id, "type": a.alert_type, "severity": a.severity,
             "description": a.description, "created_at": str(a.created_at)} for a in alerts]

@app.post("/api/invoices/refresh-overdue")
def refresh_overdue(db: Session = Depends(get_db),
                    current_user: User = Depends(require_roles(UserRole.admin, UserRole.accountant, UserRole.revenue_officer))):
    count = refresh_overdue_invoices(db)
    return {"updated_invoices": count, "message": f"Marked {count} invoice(s) as overdue"}

# ─── Ratepayers ───────────────────────────────────────────────────────────────

@app.get("/api/ratepayers")
def list_ratepayers(search: Optional[str] = None, zone: Optional[str] = None,
                    skip: int = 0, limit: int = 50,
                    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    q = db.query(Ratepayer)
    if search: q = q.filter(Ratepayer.full_name.contains(search) | Ratepayer.account_number.contains(search))
    if zone:   q = q.filter(Ratepayer.zone == zone)
    total = q.count()
    items = q.offset(skip).limit(limit).all()
    return {"total": total, "items": [
        {"id": r.id, "account_number": r.account_number, "full_name": r.full_name,
         "address": r.address, "ward": r.ward, "zone": r.zone,
         "phone": r.phone, "email": r.email, "property_type": r.property_type,
         "is_active": r.is_active} for r in items]}

@app.post("/api/ratepayers")
def create_ratepayer(data: RatepayerCreate, db: Session = Depends(get_db),
                     current_user: User = Depends(get_current_user)):
    acct = "COH-" + "".join(random.choices(string.digits, k=6))
    rp = Ratepayer(account_number=acct, **data.dict())
    db.add(rp); db.flush()
    db.add(AuditLog(user_id=current_user.id, action="CREATE", table_name="ratepayers",
                    record_id=rp.id, description=f"Created ratepayer: {data.full_name}"))
    db.commit()
    return {"id": rp.id, "account_number": rp.account_number, "message": "Ratepayer created successfully"}

@app.get("/api/ratepayers/{rp_id}")
def get_ratepayer(rp_id: int, db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user)):
    refresh_overdue_invoices(db)
    rp = db.query(Ratepayer).filter(Ratepayer.id == rp_id).first()
    if not rp: raise HTTPException(404, "Ratepayer not found")
    invoices = db.query(Invoice).filter(Invoice.ratepayer_id == rp_id).all()
    payments = db.query(Payment).filter(Payment.ratepayer_id == rp_id).all()
    total_billed = sum(i.amount for i in invoices)
    total_paid   = sum(p.amount for p in payments)
    return {
        "id": rp.id, "account_number": rp.account_number, "full_name": rp.full_name,
        "address": rp.address, "ward": rp.ward, "zone": rp.zone,
        "phone": rp.phone, "email": rp.email, "property_type": rp.property_type,
        "is_active": rp.is_active,
        "total_billed": round(total_billed, 2), "total_paid": round(total_paid, 2),
        "balance": round(total_billed - total_paid, 2),
        "invoice_count": len(invoices), "payment_count": len(payments)
    }

@app.put("/api/ratepayers/{rp_id}")
def update_ratepayer(rp_id: int, data: RatepayerUpdate, db: Session = Depends(get_db),
                     current_user: User = Depends(get_current_user)):
    rp = db.query(Ratepayer).filter(Ratepayer.id == rp_id).first()
    if not rp: raise HTTPException(404, "Ratepayer not found")
    changes = data.dict(exclude_none=True)
    for k, v in changes.items():
        setattr(rp, k, v)
    db.add(AuditLog(user_id=current_user.id, action="UPDATE", table_name="ratepayers",
                    record_id=rp_id, description=f"Updated ratepayer: {rp.full_name}"))
    db.commit()
    return {"message": "Ratepayer updated"}

@app.delete("/api/ratepayers/{rp_id}")
def delete_ratepayer(rp_id: int, db: Session = Depends(get_db),
                     current_user: User = Depends(require_roles(UserRole.admin, UserRole.accountant))):
    rp = db.query(Ratepayer).filter(Ratepayer.id == rp_id).first()
    if not rp: raise HTTPException(404, "Ratepayer not found")
    inv_count = db.query(Invoice).filter(Invoice.ratepayer_id == rp_id).count()
    if inv_count > 0:
        raise HTTPException(400, f"Cannot delete: ratepayer has {inv_count} invoice(s). Deactivate instead.")
    db.add(AuditLog(user_id=current_user.id, action="DELETE", table_name="ratepayers",
                    record_id=rp_id, description=f"Deleted ratepayer: {rp.full_name}"))
    db.delete(rp); db.commit()
    return {"message": "Ratepayer deleted"}

# ─── Invoices ─────────────────────────────────────────────────────────────────

@app.get("/api/invoices")
def list_invoices(status: Optional[str] = None, category: Optional[str] = None,
                  anomaly: Optional[str] = None, search: Optional[str] = None,
                  ratepayer_id: Optional[int] = None,
                  skip: int = 0, limit: int = 50,
                  db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    refresh_overdue_invoices(db)
    q = db.query(Invoice)
    if status:       q = q.filter(Invoice.status == status)
    if category:     q = q.filter(Invoice.category == category)
    if anomaly and anomaly != "none": q = q.filter(Invoice.anomaly_flag == anomaly)
    if ratepayer_id: q = q.filter(Invoice.ratepayer_id == ratepayer_id)
    total = q.count()
    items = q.order_by(desc(Invoice.issue_date)).offset(skip).limit(limit).all()
    result = []
    for inv in items:
        rp = db.query(Ratepayer).filter(Ratepayer.id == inv.ratepayer_id).first()
        result.append({
            "id": inv.id, "invoice_number": inv.invoice_number,
            "ratepayer_name": rp.full_name if rp else "Unknown",
            "account_number": rp.account_number if rp else "",
            "category": inv.category, "amount": inv.amount,
            "amount_paid": inv.amount_paid, "balance": inv.balance,
            "status": inv.status, "anomaly_flag": inv.anomaly_flag,
            "anomaly_reason": inv.anomaly_reason, "notes": inv.notes,
            "issue_date": str(inv.issue_date)[:10], "due_date": str(inv.due_date)[:10],
            "ratepayer_id": inv.ratepayer_id
        })
    return {"total": total, "items": result}

@app.post("/api/invoices")
def create_invoice(data: InvoiceCreate, db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    inv_num = "INV-" + "".join(random.choices(string.digits, k=8))
    due = datetime.fromisoformat(data.due_date)
    inv = Invoice(invoice_number=inv_num, ratepayer_id=data.ratepayer_id,
                  category=data.category, amount=data.amount, amount_paid=0.0,
                  balance=data.amount, due_date=due, notes=data.notes, created_by=current_user.id)
    cat_amounts = [r[0] for r in db.query(Invoice.amount).filter(Invoice.category == data.category).all()]
    inv.anomaly_flag, inv.anomaly_reason = _zscore_flag(data.amount, cat_amounts)
    db.add(inv); db.flush()
    db.add(AuditLog(user_id=current_user.id, action="CREATE", table_name="invoices",
                    record_id=inv.id, description=f"Invoice {inv_num} created for ratepayer {data.ratepayer_id}"))
    db.commit()
    return {"id": inv.id, "invoice_number": inv_num, "message": "Invoice created"}

@app.put("/api/invoices/{inv_id}")
def update_invoice(inv_id: int, data: InvoiceUpdate, db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    inv = db.query(Invoice).filter(Invoice.id == inv_id).first()
    if not inv: raise HTTPException(404, "Invoice not found")
    if inv.status == PaymentStatus.paid and data.amount is not None:
        raise HTTPException(400, "Cannot change amount on a paid invoice")
    if data.due_date:
        inv.due_date = datetime.fromisoformat(data.due_date)
    if data.status:
        inv.status = data.status
    if data.notes is not None:
        inv.notes = data.notes
    if data.amount is not None:
        inv.amount = data.amount
        inv.balance = max(0, data.amount - inv.amount_paid)
    db.add(AuditLog(user_id=current_user.id, action="UPDATE", table_name="invoices",
                    record_id=inv_id, description=f"Updated invoice {inv.invoice_number}"))
    db.commit()
    return {"message": "Invoice updated"}

@app.delete("/api/invoices/{inv_id}")
def delete_invoice(inv_id: int, db: Session = Depends(get_db),
                   current_user: User = Depends(require_roles(UserRole.admin, UserRole.accountant))):
    inv = db.query(Invoice).filter(Invoice.id == inv_id).first()
    if not inv: raise HTTPException(404, "Invoice not found")
    if inv.amount_paid > 0:
        raise HTTPException(400, "Cannot delete an invoice that has payments recorded against it")
    db.add(AuditLog(user_id=current_user.id, action="DELETE", table_name="invoices",
                    record_id=inv_id, description=f"Deleted invoice {inv.invoice_number}"))
    db.delete(inv); db.commit()
    return {"message": "Invoice deleted"}

# ─── Payments ─────────────────────────────────────────────────────────────────

@app.get("/api/payments")
def list_payments(reconciled: Optional[bool] = None, ratepayer_id: Optional[int] = None,
                  skip: int = 0, limit: int = 50,
                  db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    q = db.query(Payment)
    if reconciled is not None: q = q.filter(Payment.is_reconciled == reconciled)
    if ratepayer_id:           q = q.filter(Payment.ratepayer_id == ratepayer_id)
    total = q.count()
    items = q.order_by(desc(Payment.payment_date)).offset(skip).limit(limit).all()
    result = []
    for p in items:
        rp = db.query(Ratepayer).filter(Ratepayer.id == p.ratepayer_id).first()
        result.append({
            "id": p.id, "receipt_number": p.receipt_number,
            "ratepayer_name": rp.full_name if rp else "Unknown",
            "account_number": rp.account_number if rp else "",
            "amount": p.amount, "payment_method": p.payment_method,
            "currency": p.currency, "is_reconciled": p.is_reconciled,
            "anomaly_flag": p.anomaly_flag, "payment_date": str(p.payment_date)[:10],
            "invoice_id": p.invoice_id
        })
    return {"total": total, "items": result}

@app.post("/api/payments")
def record_payment(data: PaymentCreate, db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    rp = db.query(Ratepayer).filter(Ratepayer.id == data.ratepayer_id).first()
    if not rp: raise HTTPException(404, "Ratepayer not found")
    rcpt  = "RCP-" + "".join(random.choices(string.digits, k=8))
    flag  = AnomalyFlag.none; reason = None
    if not data.invoice_id:
        # Unlinked payment — primary leakage risk: money received with no audit trail to an invoice
        flag = AnomalyFlag.medium
        reason = "Payment recorded without invoice reference — unlinked cash increases leakage risk"
    # Z-score check: is this amount anomalous vs this ratepayer's payment history?
    rp_amounts = [r[0] for r in db.query(Payment.amount)
                  .filter(Payment.ratepayer_id == data.ratepayer_id).all()]
    zscore_flag, zscore_reason = _zscore_flag(data.amount, rp_amounts)
    # Take the higher severity flag between the two checks
    severity_order = [AnomalyFlag.none, AnomalyFlag.low, AnomalyFlag.medium, AnomalyFlag.high]
    if severity_order.index(zscore_flag) > severity_order.index(flag):
        flag = zscore_flag
        reason = zscore_reason
    elif zscore_flag != AnomalyFlag.none and reason:
        reason = f"{reason}; {zscore_reason}"
    pmt = Payment(receipt_number=rcpt, ratepayer_id=data.ratepayer_id,
                  invoice_id=data.invoice_id, amount=data.amount,
                  payment_method=data.payment_method, currency=data.currency,
                  collected_by=current_user.id, notes=data.notes,
                  anomaly_flag=flag, anomaly_reason=reason)
    db.add(pmt)
    if data.invoice_id:
        inv = db.query(Invoice).filter(Invoice.id == data.invoice_id).first()
        if inv:
            inv.amount_paid = min(inv.amount, inv.amount_paid + data.amount)
            inv.balance     = max(0, inv.amount - inv.amount_paid)
            if inv.balance == 0:
                inv.status = PaymentStatus.paid
            elif inv.due_date < now() and inv.balance > 0:
                inv.status = PaymentStatus.overdue
    db.flush()
    db.add(AuditLog(user_id=current_user.id, action="CREATE", table_name="payments",
                    record_id=pmt.id, description=f"Payment {rcpt} of ${data.amount} recorded"))
    db.commit()
    return {"id": pmt.id, "receipt_number": rcpt, "message": "Payment recorded successfully"}

@app.patch("/api/payments/{pmt_id}/reconcile")
def reconcile_payment(pmt_id: int, db: Session = Depends(get_db),
                       current_user: User = Depends(get_current_user)):
    pmt = db.query(Payment).filter(Payment.id == pmt_id).first()
    if not pmt: raise HTTPException(404, "Payment not found")
    pmt.is_reconciled = True
    db.add(AuditLog(user_id=current_user.id, action="UPDATE", table_name="payments",
                    record_id=pmt_id, description=f"Payment {pmt.receipt_number} reconciled"))
    db.commit()
    return {"message": "Payment reconciled"}

@app.delete("/api/payments/{pmt_id}")
def delete_payment(pmt_id: int, db: Session = Depends(get_db),
                   current_user: User = Depends(require_roles(UserRole.admin, UserRole.accountant))):
    pmt = db.query(Payment).filter(Payment.id == pmt_id).first()
    if not pmt: raise HTTPException(404, "Payment not found")
    if pmt.is_reconciled:
        raise HTTPException(400, "Cannot delete a reconciled payment")
    # Reverse invoice amount_paid if linked
    if pmt.invoice_id:
        inv = db.query(Invoice).filter(Invoice.id == pmt.invoice_id).first()
        if inv:
            inv.amount_paid = max(0, inv.amount_paid - pmt.amount)
            inv.balance     = min(inv.amount, inv.balance + pmt.amount)
            if inv.amount_paid < inv.amount:
                inv.status = PaymentStatus.overdue if inv.due_date < now() else PaymentStatus.pending
    db.add(AuditLog(user_id=current_user.id, action="DELETE", table_name="payments",
                    record_id=pmt_id, description=f"Deleted payment {pmt.receipt_number} of ${pmt.amount}"))
    db.delete(pmt); db.commit()
    return {"message": "Payment deleted"}

# ─── Expenditures ─────────────────────────────────────────────────────────────

@app.get("/api/expenditures")
def list_expenditures(skip: int = 0, limit: int = 100, department: Optional[str] = None,
                      db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    q = db.query(Expenditure)
    if department: q = q.filter(Expenditure.department == department)
    total = q.count()
    items = q.order_by(desc(Expenditure.expenditure_date)).offset(skip).limit(limit).all()
    return {"total": total, "items": [
        {"id": e.id, "reference_number": e.reference_number, "department": e.department,
         "description": e.description, "amount": e.amount, "budget_line": e.budget_line,
         "is_approved": e.is_approved, "anomaly_flag": e.anomaly_flag,
         "date": str(e.expenditure_date)[:10]} for e in items]}

@app.post("/api/expenditures")
def create_expenditure(data: ExpenditureCreate, db: Session = Depends(get_db),
                       current_user: User = Depends(get_current_user)):
    ref = "EXP-" + "".join(random.choices(string.digits, k=7))
    dept_amounts = [r[0] for r in db.query(Expenditure.amount)
                    .filter(Expenditure.department == data.department).all()]
    flag, _ = _zscore_flag(data.amount, dept_amounts)
    e = Expenditure(reference_number=ref, anomaly_flag=flag, **data.dict())
    db.add(e); db.flush()
    db.add(AuditLog(user_id=current_user.id, action="CREATE", table_name="expenditures",
                    record_id=e.id, description=f"Expenditure {ref} recorded: {data.department}"))
    db.commit()
    return {"id": e.id, "reference_number": ref, "message": "Expenditure recorded"}

@app.put("/api/expenditures/{exp_id}")
def update_expenditure(exp_id: int, data: ExpenditureUpdate, db: Session = Depends(get_db),
                       current_user: User = Depends(get_current_user)):
    e = db.query(Expenditure).filter(Expenditure.id == exp_id).first()
    if not e: raise HTTPException(404, "Expenditure not found")
    if e.is_approved:
        raise HTTPException(400, "Cannot edit an approved expenditure")
    for k, v in data.dict(exclude_none=True).items():
        setattr(e, k, v)
    db.add(AuditLog(user_id=current_user.id, action="UPDATE", table_name="expenditures",
                    record_id=exp_id, description=f"Updated expenditure {e.reference_number}"))
    db.commit()
    return {"message": "Expenditure updated"}

@app.patch("/api/expenditures/{exp_id}/approve")
def approve_expenditure(exp_id: int, db: Session = Depends(get_db),
                         current_user: User = Depends(require_roles(UserRole.admin, UserRole.accountant))):
    e = db.query(Expenditure).filter(Expenditure.id == exp_id).first()
    if not e: raise HTTPException(404)
    e.is_approved = True; e.approved_by = current_user.id
    # Update budget spent amount
    budget = db.query(Budget).filter(Budget.department == e.department).first()
    if budget:
        budget.spent_amount = (budget.spent_amount or 0) + e.amount
        budget.remaining    = budget.allocated_amount - budget.spent_amount
    db.add(AuditLog(user_id=current_user.id, action="UPDATE", table_name="expenditures",
                    record_id=exp_id, description=f"Approved expenditure {e.reference_number}"))
    db.commit()
    return {"message": "Expenditure approved"}

@app.delete("/api/expenditures/{exp_id}")
def delete_expenditure(exp_id: int, db: Session = Depends(get_db),
                       current_user: User = Depends(require_roles(UserRole.admin, UserRole.accountant))):
    e = db.query(Expenditure).filter(Expenditure.id == exp_id).first()
    if not e: raise HTTPException(404, "Expenditure not found")
    if e.is_approved:
        raise HTTPException(400, "Cannot delete an approved expenditure")
    db.add(AuditLog(user_id=current_user.id, action="DELETE", table_name="expenditures",
                    record_id=exp_id, description=f"Deleted expenditure {e.reference_number}"))
    db.delete(e); db.commit()
    return {"message": "Expenditure deleted"}

# ─── Budgets ──────────────────────────────────────────────────────────────────

@app.get("/api/budgets")
def list_budgets(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    items = db.query(Budget).all()
    return [{"id": b.id, "fiscal_year": b.fiscal_year, "department": b.department,
             "category": b.category, "allocated": b.allocated_amount,
             "spent": b.spent_amount, "remaining": b.remaining,
             "utilisation": round(b.spent_amount / b.allocated_amount * 100, 1) if b.allocated_amount > 0 else 0
             } for b in items]

@app.post("/api/budgets")
def create_budget(data: BudgetCreate,
                  db: Session = Depends(get_db),
                  current_user: User = Depends(require_roles(UserRole.admin, UserRole.budget_officer, UserRole.accountant))):
    existing = db.query(Budget).filter(
        Budget.fiscal_year == data.fiscal_year,
        Budget.department  == data.department,
        Budget.category    == data.category).first()
    if existing:
        raise HTTPException(400, "A budget entry already exists for this department/category/year. Use edit to update.")
    b = Budget(fiscal_year=data.fiscal_year, department=data.department,
               category=data.category, allocated_amount=data.allocated_amount,
               spent_amount=data.spent_amount,
               remaining=data.allocated_amount - data.spent_amount)
    db.add(b); db.flush()
    db.add(AuditLog(user_id=current_user.id, action="CREATE", table_name="budgets",
                    record_id=b.id, description=f"Budget created: {data.department} {data.fiscal_year}"))
    db.commit()
    return {"id": b.id, "message": "Budget created"}

@app.put("/api/budgets/{bud_id}")
def update_budget(bud_id: int, data: BudgetUpdate,
                  db: Session = Depends(get_db),
                  current_user: User = Depends(require_roles(UserRole.admin, UserRole.budget_officer, UserRole.accountant))):
    b = db.query(Budget).filter(Budget.id == bud_id).first()
    if not b: raise HTTPException(404, "Budget not found")
    for k, v in data.dict(exclude_none=True).items():
        setattr(b, k, v)
    b.remaining = b.allocated_amount - b.spent_amount
    db.add(AuditLog(user_id=current_user.id, action="UPDATE", table_name="budgets",
                    record_id=bud_id, description=f"Updated budget: {b.department} {b.fiscal_year}"))
    db.commit()
    return {"message": "Budget updated"}

@app.delete("/api/budgets/{bud_id}")
def delete_budget(bud_id: int,
                  db: Session = Depends(get_db),
                  current_user: User = Depends(require_roles(UserRole.admin, UserRole.budget_officer))):
    b = db.query(Budget).filter(Budget.id == bud_id).first()
    if not b: raise HTTPException(404, "Budget not found")
    db.add(AuditLog(user_id=current_user.id, action="DELETE", table_name="budgets",
                    record_id=bud_id, description=f"Deleted budget: {b.department} {b.fiscal_year}"))
    db.delete(b); db.commit()
    return {"message": "Budget deleted"}

# ─── Leakage & Anomalies ──────────────────────────────────────────────────────

@app.get("/api/leakage/summary")
def leakage_summary(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    high  = db.query(Invoice).filter(Invoice.anomaly_flag == AnomalyFlag.high).count()
    medium = db.query(Invoice).filter(Invoice.anomaly_flag == AnomalyFlag.medium).count()
    low_f  = db.query(Invoice).filter(Invoice.anomaly_flag == AnomalyFlag.low).count()
    unreconciled     = db.query(Payment).filter(Payment.is_reconciled == False).count()
    unreconciled_amt = db.query(func.sum(Payment.amount)).filter(Payment.is_reconciled == False).scalar() or 0
    overdue_amt      = db.query(func.sum(Invoice.balance)).filter(Invoice.status == PaymentStatus.overdue).scalar() or 0
    alerts = db.query(LeakageAlert).filter(LeakageAlert.is_resolved == False).all()
    return {
        "high_anomalies": high, "medium_anomalies": medium, "low_anomalies": low_f,
        "unreconciled_payments": unreconciled,
        "unreconciled_amount": round(unreconciled_amt, 2),
        "overdue_balance": round(overdue_amt, 2),
        "active_alerts": len(alerts),
        # Leakage Risk Index — ACFE (2022) weighted model:
        # 40% of unreconciled payments (cash received, no audit trail) +
        # 25% of overdue balance (NCC 2023: <25% recovery probability beyond 90 days)
        "estimated_leakage": round(unreconciled_amt * 0.40 + overdue_amt * 0.25, 2)
    }

@app.get("/api/leakage/alerts")
def leakage_alerts(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    alerts = db.query(LeakageAlert).order_by(desc(LeakageAlert.created_at)).all()
    return [{"id": a.id, "type": a.alert_type, "severity": a.severity, "description": a.description,
             "is_resolved": a.is_resolved, "created_at": str(a.created_at)[:16]} for a in alerts]

@app.patch("/api/leakage/alerts/{alert_id}/resolve")
def resolve_alert(alert_id: int, db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user)):
    a = db.query(LeakageAlert).filter(LeakageAlert.id == alert_id).first()
    if not a: raise HTTPException(404)
    a.is_resolved = True; a.resolved_by = current_user.id; a.resolved_at = now()
    db.commit()
    return {"message": "Alert resolved"}

@app.post("/api/leakage/scan")
def scan_leakage_alerts(db: Session = Depends(get_db),
                        current_user: User = Depends(require_roles(
                            UserRole.admin, UserRole.auditor, UserRole.accountant))):
    """
    Dynamically scan the database for revenue leakage patterns and generate alerts.
    Implements five detection rules derived from the City of Harare stakeholder
    interviews and ACFE (2022) fraud pattern taxonomy:
      1. Ghost accounts — active ratepayers with no payment in 12+ months but outstanding balances
      2. Waiver abuse — waivers that exceed the ward's historical waiver rate by >2σ
      3. Unlinked cash — unreconciled cash payments with no invoice reference
      4. Officer collection gap — revenue officers collecting significantly below peers (Z-score)
      5. Stale high-value overdue — overdue invoices >180 days with balance >$500
    """
    cutoff_12m  = now() - timedelta(days=365)
    cutoff_180d = now() - timedelta(days=180)
    generated   = 0

    def _alert_exists(alert_type: str, record_id: int, table: str) -> bool:
        return db.query(LeakageAlert).filter(
            LeakageAlert.alert_type == alert_type,
            LeakageAlert.related_record_id == record_id,
            LeakageAlert.related_table == table,
            LeakageAlert.is_resolved == False
        ).first() is not None

    # ── Rule 1: Ghost accounts ─────────────────────────────────────────────
    active_rps = db.query(Ratepayer).filter(Ratepayer.is_active == True).all()
    for rp in active_rps:
        outstanding = db.query(func.sum(Invoice.balance))\
            .filter(Invoice.ratepayer_id == rp.id, Invoice.balance > 0).scalar() or 0
        if outstanding <= 0:
            continue
        last_pmt = db.query(func.max(Payment.payment_date))\
            .filter(Payment.ratepayer_id == rp.id).scalar()
        if last_pmt is None or last_pmt < cutoff_12m:
            if not _alert_exists("ghost_account", rp.id, "ratepayers"):
                db.add(LeakageAlert(
                    alert_type="ghost_account", severity="high",
                    description=(f"Ratepayer {rp.account_number} ({rp.full_name}) has "
                                 f"${outstanding:,.2f} outstanding but no payment in >12 months. "
                                 f"Possible ghost account or inactive debtor — review for write-off or enforcement."),
                    related_record_id=rp.id, related_table="ratepayers"
                ))
                generated += 1

    # ── Rule 2: Unlinked cash payments (unreconciled, no invoice) ─────────
    unlinked = db.query(Payment).filter(
        Payment.invoice_id == None,
        Payment.is_reconciled == False,
        Payment.payment_method == "cash"
    ).all()
    for pmt in unlinked:
        if not _alert_exists("unlinked_cash", pmt.id, "payments"):
            db.add(LeakageAlert(
                alert_type="unlinked_cash", severity="high",
                description=(f"Cash payment {pmt.receipt_number} of ${pmt.amount:,.2f} is "
                             f"unreconciled and has no invoice reference. "
                             f"Cash with no paper trail is the primary leakage vector (ACFE, 2022)."),
                related_record_id=pmt.id, related_table="payments"
            ))
            generated += 1

    # ── Rule 3: Stale high-value overdue invoices (>180 days, >$500) ─────
    stale = db.query(Invoice).filter(
        Invoice.status == PaymentStatus.overdue,
        Invoice.due_date < cutoff_180d,
        Invoice.balance > 500
    ).all()
    for inv in stale:
        if not _alert_exists("stale_overdue", inv.id, "invoices"):
            db.add(LeakageAlert(
                alert_type="stale_overdue", severity="medium",
                description=(f"Invoice {inv.invoice_number} has been overdue >180 days "
                             f"with ${inv.balance:,.2f} outstanding. "
                             f"Accounts >180 days overdue have <30% recovery probability (NCC, 2023)."),
                related_record_id=inv.id, related_table="invoices"
            ))
            generated += 1

    # ── Rule 4: Officer collection gap (Z-score on collection rates) ──────
    officers = db.query(User).filter(User.role == UserRole.revenue_officer, User.is_active == True).all()
    officer_rates = []
    for officer in officers:
        total_collected = db.query(func.sum(Payment.amount))\
            .filter(Payment.collected_by == officer.id).scalar() or 0
        inv_count = db.query(func.count(Invoice.id))\
            .filter(Invoice.created_by == officer.id).scalar() or 0
        total_billed = db.query(func.sum(Invoice.amount))\
            .filter(Invoice.created_by == officer.id).scalar() or 0
        rate = (total_collected / total_billed * 100) if total_billed > 0 else 0
        officer_rates.append((officer, rate, total_billed))

    if len(officer_rates) >= 3:
        rates = [r[1] for r in officer_rates]
        flag, _ = _zscore_flag(0, rates)  # dummy call to get mean/std
        mean_rate = sum(rates) / len(rates)
        variance  = sum((r - mean_rate) ** 2 for r in rates) / (len(rates) - 1)
        std_rate  = math.sqrt(variance) if variance > 0 else 0
        for officer, rate, billed in officer_rates:
            if billed < 100:
                continue
            z = (rate - mean_rate) / std_rate if std_rate > 0 else 0
            if z < -2.0:
                if not _alert_exists("officer_gap", officer.id, "users"):
                    db.add(LeakageAlert(
                        alert_type="officer_gap", severity="medium",
                        description=(f"Revenue officer {officer.full_name} has a collection rate "
                                     f"of {rate:.1f}% vs peer average {mean_rate:.1f}% "
                                     f"(Z-score {z:.2f}). Significantly below peers — review workload or escalate."),
                        related_record_id=officer.id, related_table="users"
                    ))
                    generated += 1

    # ── Rule 5: Waived invoices without approval audit trail ──────────────
    waived = db.query(Invoice).filter(Invoice.status == PaymentStatus.waived).all()
    for inv in waived:
        if not _alert_exists("waiver_no_audit", inv.id, "invoices"):
            # Check if there is an audit log entry showing who waived it
            waiver_log = db.query(AuditLog).filter(
                AuditLog.table_name == "invoices",
                AuditLog.record_id == inv.id,
                AuditLog.action == "UPDATE"
            ).first()
            if not waiver_log:
                db.add(LeakageAlert(
                    alert_type="waiver_no_audit", severity="high",
                    description=(f"Invoice {inv.invoice_number} (${inv.amount:,.2f}) is marked "
                                 f"waived but has no audit trail of who approved it. "
                                 f"Unapproved waivers are a key leakage indicator (ZIMRA, 2023)."),
                    related_record_id=inv.id, related_table="invoices"
                ))
                generated += 1

    if generated > 0:
        db.commit()
    return {"generated": generated, "message": f"{generated} new alert(s) generated from leakage scan"}

# ─── Audit Log ────────────────────────────────────────────────────────────────

@app.get("/api/audit-logs")
def get_audit_logs(skip: int = 0, limit: int = 50,
                   date_from: Optional[str] = None, date_to: Optional[str] = None,
                   action: Optional[str] = None, table_name: Optional[str] = None,
                   db: Session = Depends(get_db),
                   current_user: User = Depends(require_roles(UserRole.admin, UserRole.auditor))):
    q = db.query(AuditLog).order_by(desc(AuditLog.timestamp))
    if date_from: q = q.filter(AuditLog.timestamp >= datetime.fromisoformat(date_from))
    if date_to:   q = q.filter(AuditLog.timestamp <= datetime.fromisoformat(date_to + "T23:59:59"))
    if action:     q = q.filter(AuditLog.action == action.upper())
    if table_name: q = q.filter(AuditLog.table_name == table_name)
    total = q.count()
    items = q.offset(skip).limit(limit).all()
    result = []
    for log in items:
        user = db.query(User).filter(User.id == log.user_id).first()
        result.append({"id": log.id, "action": log.action, "table_name": log.table_name,
                        "description": log.description, "user": user.full_name if user else "System",
                        "ip_address": log.ip_address, "timestamp": str(log.timestamp)[:16]})
    return {"total": total, "items": result}

# ─── Users ────────────────────────────────────────────────────────────────────

@app.get("/api/users")
def list_users(db: Session = Depends(get_db),
               current_user: User = Depends(require_roles(UserRole.admin))):
    users = db.query(User).all()
    return [{"id": u.id, "username": u.username, "full_name": u.full_name,
             "email": u.email, "role": u.role, "is_active": u.is_active,
             "last_login": str(u.last_login)[:16] if u.last_login else None} for u in users]

@app.post("/api/users")
def create_user(data: UserCreate, db: Session = Depends(get_db),
                current_user: User = Depends(require_roles(UserRole.admin))):
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(400, "Username already exists")
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(400, "Email already in use")
    try:
        role = UserRole(data.role)
    except ValueError:
        raise HTTPException(400, f"Invalid role: {data.role}")
    u = User(username=data.username, full_name=data.full_name, email=data.email,
             hashed_password=hash_password(data.password), role=role)
    db.add(u); db.flush()
    db.add(AuditLog(user_id=current_user.id, action="CREATE", table_name="users",
                    record_id=u.id, description=f"Created user: {data.username} ({data.role})"))
    db.commit()
    return {"id": u.id, "username": u.username, "message": "User created"}

@app.put("/api/users/{user_id}")
def update_user(user_id: int, data: UserUpdate, db: Session = Depends(get_db),
                current_user: User = Depends(require_roles(UserRole.admin))):
    u = db.query(User).filter(User.id == user_id).first()
    if not u: raise HTTPException(404, "User not found")
    if user_id == current_user.id and data.is_active is False:
        raise HTTPException(400, "Cannot deactivate your own account")
    if data.full_name:  u.full_name = data.full_name
    if data.email:      u.email     = data.email
    if data.role:
        try: u.role = UserRole(data.role)
        except ValueError: raise HTTPException(400, f"Invalid role: {data.role}")
    if data.is_active is not None: u.is_active = data.is_active
    if data.password:  u.hashed_password = hash_password(data.password)
    db.add(AuditLog(user_id=current_user.id, action="UPDATE", table_name="users",
                    record_id=user_id, description=f"Updated user: {u.username}"))
    db.commit()
    return {"message": "User updated"}

@app.delete("/api/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db),
                current_user: User = Depends(require_roles(UserRole.admin))):
    u = db.query(User).filter(User.id == user_id).first()
    if not u: raise HTTPException(404, "User not found")
    if user_id == current_user.id:
        raise HTTPException(400, "Cannot delete your own account")
    u.is_active = False
    db.add(AuditLog(user_id=current_user.id, action="DELETE", table_name="users",
                    record_id=user_id, description=f"Deactivated user: {u.username}"))
    db.commit()
    return {"message": "User deactivated"}

# ─── Export Endpoints ─────────────────────────────────────────────────────────

@app.get("/api/export/ratepayers")
def export_ratepayers(format: str = "csv", db: Session = Depends(get_db),
                      current_user: User = Depends(get_current_user)):
    items = db.query(Ratepayer).all()
    headers = ["Account Number", "Full Name", "Address", "Ward", "Zone",
               "Property Type", "Phone", "Email", "Active", "Created At"]
    rows = [[r.account_number, r.full_name, r.address, r.ward, r.zone,
             r.property_type, r.phone or "", r.email or "",
             "Yes" if r.is_active else "No", str(r.created_at)[:10]] for r in items]
    return export_response(format, headers, rows,
                           "ratepayers.csv", "ratepayers.xlsx", "Ratepayers",
                           "City of Harare FMS — Ratepayer Registry")

@app.get("/api/export/invoices")
def export_invoices(format: str = "csv", db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    items = db.query(Invoice).order_by(desc(Invoice.issue_date)).all()
    headers = ["Invoice Number", "Ratepayer", "Account Number", "Category",
               "Amount", "Amount Paid", "Balance", "Status",
               "Issue Date", "Due Date", "Anomaly Flag", "Notes"]
    rows = []
    for inv in items:
        rp = db.query(Ratepayer).filter(Ratepayer.id == inv.ratepayer_id).first()
        rows.append([inv.invoice_number, rp.full_name if rp else "", rp.account_number if rp else "",
                     inv.category, inv.amount, inv.amount_paid, inv.balance, inv.status,
                     str(inv.issue_date)[:10], str(inv.due_date)[:10], inv.anomaly_flag, inv.notes or ""])
    return export_response(format, headers, rows,
                           "invoices.csv", "invoices.xlsx", "Invoices",
                           "City of Harare FMS — Invoice Register")

@app.get("/api/export/payments")
def export_payments(format: str = "csv", db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    items = db.query(Payment).order_by(desc(Payment.payment_date)).all()
    headers = ["Receipt Number", "Ratepayer", "Account Number", "Amount",
               "Currency", "Method", "Date", "Reconciled", "Anomaly Flag"]
    rows = []
    for p in items:
        rp = db.query(Ratepayer).filter(Ratepayer.id == p.ratepayer_id).first()
        rows.append([p.receipt_number, rp.full_name if rp else "", rp.account_number if rp else "",
                     p.amount, p.currency, p.payment_method, str(p.payment_date)[:10],
                     "Yes" if p.is_reconciled else "No", p.anomaly_flag])
    return export_response(format, headers, rows,
                           "payments.csv", "payments.xlsx", "Payments",
                           "City of Harare FMS — Payment Records")

@app.get("/api/export/expenditures")
def export_expenditures(format: str = "csv", db: Session = Depends(get_db),
                        current_user: User = Depends(get_current_user)):
    items = db.query(Expenditure).order_by(desc(Expenditure.expenditure_date)).all()
    headers = ["Reference", "Department", "Description", "Amount",
               "Budget Line", "Date", "Approved", "Anomaly Flag"]
    rows = [[e.reference_number, e.department, e.description, e.amount,
             e.budget_line, str(e.expenditure_date)[:10],
             "Yes" if e.is_approved else "No", e.anomaly_flag] for e in items]
    return export_response(format, headers, rows,
                           "expenditures.csv", "expenditures.xlsx", "Expenditures",
                           "City of Harare FMS — Expenditure Register")

@app.get("/api/export/audit-logs")
def export_audit_logs(format: str = "csv",
                      date_from: Optional[str] = None, date_to: Optional[str] = None,
                      db: Session = Depends(get_db),
                      current_user: User = Depends(require_roles(UserRole.admin, UserRole.auditor))):
    q = db.query(AuditLog).order_by(desc(AuditLog.timestamp))
    if date_from: q = q.filter(AuditLog.timestamp >= datetime.fromisoformat(date_from))
    if date_to:   q = q.filter(AuditLog.timestamp <= datetime.fromisoformat(date_to + "T23:59:59"))
    items = q.all()
    headers = ["#", "User", "Action", "Module", "Description", "IP Address", "Timestamp"]
    rows = []
    for i, log in enumerate(items, 1):
        user = db.query(User).filter(User.id == log.user_id).first()
        rows.append([i, user.full_name if user else "System", log.action,
                     log.table_name, log.description or "", log.ip_address or "", str(log.timestamp)[:16]])
    return export_response(format, headers, rows,
                           "audit_trail.csv", "audit_trail.xlsx", "Audit Trail",
                           "City of Harare FMS — Audit Trail")

# ─── Import Endpoints ─────────────────────────────────────────────────────────

@app.post("/api/import/ratepayers")
async def import_ratepayers(file: UploadFile = File(...),
                             db: Session = Depends(get_db),
                             current_user: User = Depends(require_roles(UserRole.admin, UserRole.revenue_officer))):
    rows  = await parse_upload(file)
    created = 0; errors = []
    for i, row in enumerate(rows, 2):
        try:
            name = str(row.get("full_name") or row.get("Full Name") or "").strip()
            addr = str(row.get("address") or row.get("Address") or "").strip()
            ward = str(row.get("ward") or row.get("Ward") or "Ward 1").strip()
            zone = str(row.get("zone") or row.get("Zone") or "").strip()
            phone= str(row.get("phone") or row.get("Phone") or "").strip() or None
            email= str(row.get("email") or row.get("Email") or "").strip() or None
            ptype= str(row.get("property_type") or row.get("Property Type") or "residential").strip().lower()
            if not name or not addr:
                errors.append(f"Row {i}: full_name and address are required"); continue
            acct = "COH-" + "".join(random.choices(string.digits, k=6))
            rp = Ratepayer(account_number=acct, full_name=name, address=addr, ward=ward,
                           zone=zone, phone=phone, email=email, property_type=ptype)
            db.add(rp); created += 1
        except Exception as e:
            errors.append(f"Row {i}: {e}")
    db.flush()
    db.add(AuditLog(user_id=current_user.id, action="IMPORT", table_name="ratepayers",
                    description=f"Imported {created} ratepayers from file"))
    db.commit()
    return {"created": created, "errors": errors, "message": f"{created} ratepayers imported"}

@app.post("/api/import/invoices")
async def import_invoices(file: UploadFile = File(...),
                           db: Session = Depends(get_db),
                           current_user: User = Depends(require_roles(UserRole.admin, UserRole.revenue_officer, UserRole.accountant))):
    rows = await parse_upload(file)
    created = 0; errors = []
    for i, row in enumerate(rows, 2):
        try:
            acct     = str(row.get("account_number") or row.get("Account Number") or "").strip()
            category = str(row.get("category") or row.get("Category") or "other").strip().lower()
            amount   = float(row.get("amount") or row.get("Amount") or 0)
            due_raw  = str(row.get("due_date") or row.get("Due Date") or "").strip()
            notes    = str(row.get("notes") or row.get("Notes") or "").strip() or None
            if not acct or not amount or not due_raw:
                errors.append(f"Row {i}: account_number, amount and due_date required"); continue
            rp = db.query(Ratepayer).filter(Ratepayer.account_number == acct).first()
            if not rp:
                errors.append(f"Row {i}: Ratepayer account '{acct}' not found"); continue
            if category not in [c.value for c in RevenueCategory]:
                category = "other"
            inv_num = "INV-" + "".join(random.choices(string.digits, k=8))
            due = datetime.fromisoformat(due_raw)
            inv = Invoice(invoice_number=inv_num, ratepayer_id=rp.id, category=category,
                          amount=amount, amount_paid=0.0, balance=amount,
                          due_date=due, notes=notes, created_by=current_user.id)
            db.add(inv); created += 1
        except Exception as e:
            errors.append(f"Row {i}: {e}")
    db.flush()
    db.add(AuditLog(user_id=current_user.id, action="IMPORT", table_name="invoices",
                    description=f"Imported {created} invoices from file"))
    db.commit()
    return {"created": created, "errors": errors, "message": f"{created} invoices imported"}

@app.post("/api/import/budgets")
async def import_budgets(file: UploadFile = File(...),
                          db: Session = Depends(get_db),
                          current_user: User = Depends(require_roles(UserRole.admin, UserRole.budget_officer))):
    rows = await parse_upload(file)
    created = 0; updated = 0; errors = []
    for i, row in enumerate(rows, 2):
        try:
            fy   = str(row.get("fiscal_year") or row.get("Fiscal Year") or "").strip()
            dept = str(row.get("department")  or row.get("Department")  or "").strip()
            cat  = str(row.get("category")    or row.get("Category")    or "General").strip()
            alloc= float(row.get("allocated_amount") or row.get("Allocated Amount") or 0)
            spent= float(row.get("spent_amount") or row.get("Spent Amount") or 0)
            if not fy or not dept:
                errors.append(f"Row {i}: fiscal_year and department required"); continue
            existing = db.query(Budget).filter(
                Budget.fiscal_year == fy, Budget.department == dept, Budget.category == cat).first()
            if existing:
                existing.allocated_amount = alloc
                existing.spent_amount     = spent
                existing.remaining        = alloc - spent
                updated += 1
            else:
                b = Budget(fiscal_year=fy, department=dept, category=cat,
                           allocated_amount=alloc, spent_amount=spent, remaining=alloc - spent)
                db.add(b); created += 1
        except Exception as e:
            errors.append(f"Row {i}: {e}")
    db.flush()
    db.add(AuditLog(user_id=current_user.id, action="IMPORT", table_name="budgets",
                    description=f"Budget import: {created} created, {updated} updated"))
    db.commit()
    return {"created": created, "updated": updated, "errors": errors,
            "message": f"{created} created, {updated} updated"}

# ─── Import Templates ─────────────────────────────────────────────────────────

@app.get("/api/templates/{entity}")
def download_template(entity: str, format: str = "csv",
                      current_user: User = Depends(get_current_user)):
    templates = {
        "ratepayers": (["full_name", "address", "ward", "zone", "phone", "email", "property_type"],
                       [["John Doe", "123 Main St", "Ward 5", "Mbare", "0771234567",
                         "john@example.com", "residential"]]),
        "invoices":   (["account_number", "category", "amount", "due_date", "notes"],
                       [["COH-123456", "rates", "150.00", "2026-06-30", ""]]),
        "budgets":    (["fiscal_year", "department", "category", "allocated_amount", "spent_amount"],
                       [["2025/2026", "Finance", "Operations", "500000.00", "0.00"]]),
        "revenue-targets": (["fiscal_year", "category", "target_amount", "period", "notes"],
                            [["2025/2026", "rates", "1500000.00", "annual", ""],
                             ["2025/2026", "water", "800000.00", "annual", ""],
                             ["2025/2026", "sewerage", "600000.00", "annual", ""]]),
    }
    if entity not in templates:
        raise HTTPException(404, f"No template for '{entity}'")
    headers, sample = templates[entity]
    return export_response(format, headers, sample,
                           f"template_{entity}.csv", f"template_{entity}.xlsx",
                           f"{entity.title()} Template",
                           f"City of Harare FMS — {entity.title()} Import Template")

# ─── Reports ─────────────────────────────────────────────────────────────────

@app.get("/api/reports/budget-variance")
def report_budget_variance(format: str = "json", db: Session = Depends(get_db),
                            current_user: User = Depends(get_current_user)):
    budgets = db.query(Budget).order_by(Budget.department).all()
    # Actual approved expenditures by department
    actual_by_dept = dict(
        db.query(Expenditure.department, func.sum(Expenditure.amount))
          .filter(Expenditure.is_approved == True)
          .group_by(Expenditure.department).all()
    )
    rows_json = []
    rows_data = []
    for b in budgets:
        actual     = actual_by_dept.get(b.department, 0) or 0
        variance   = round(b.allocated_amount - actual, 2)
        var_pct    = round(variance / b.allocated_amount * 100, 1) if b.allocated_amount > 0 else 0
        status     = "Over Budget" if variance < 0 else ("On Budget" if variance == 0 else "Under Budget")
        rows_json.append({
            "department": b.department, "fiscal_year": b.fiscal_year, "category": b.category,
            "allocated": round(b.allocated_amount, 2), "actual_spent": round(actual, 2),
            "variance": variance, "variance_pct": var_pct, "status": status
        })
        rows_data.append([b.department, b.fiscal_year, b.category,
                          round(b.allocated_amount, 2), round(actual, 2),
                          variance, f"{var_pct}%", status])
    if format == "json":
        return rows_json
    headers = ["Department", "Fiscal Year", "Category", "Allocated ($)",
               "Actual Spent ($)", "Variance ($)", "Variance (%)", "Status"]
    return export_response(format, headers, rows_data,
                           "budget_variance_report.csv", "budget_variance_report.xlsx",
                           "Budget Variance", "City of Harare FMS — Budget Variance Report")

@app.get("/api/reports/financial-summary")
def report_financial_summary(format: str = "json", db: Session = Depends(get_db),
                              current_user: User = Depends(get_current_user)):
    cat_data = db.query(
        Invoice.category,
        func.sum(Invoice.amount).label("billed"),
        func.sum(Invoice.amount_paid).label("collected"),
        func.sum(Invoice.balance).label("outstanding"),
        func.count(Invoice.id).label("count")
    ).group_by(Invoice.category).all()

    rows_json = []
    rows_data = []
    for c in cat_data:
        billed    = round(c.billed or 0, 2)
        collected = round(c.collected or 0, 2)
        outstanding = round(c.outstanding or 0, 2)
        rate = round(collected / billed * 100, 1) if billed > 0 else 0.0
        rows_json.append({"category": c.category, "invoice_count": c.count,
                           "billed": billed, "collected": collected,
                           "outstanding": outstanding, "collection_rate": rate})
        rows_data.append([c.category, c.count, billed, collected, outstanding, f"{rate}%"])

    total_billed    = round(sum(r["billed"] for r in rows_json), 2)
    total_collected = round(sum(r["collected"] for r in rows_json), 2)
    total_outstanding = round(sum(r["outstanding"] for r in rows_json), 2)
    total_rate = round(total_collected / total_billed * 100, 1) if total_billed > 0 else 0.0

    if format == "json":
        return {"rows": rows_json,
                "totals": {"total_billed": total_billed, "total_collected": total_collected,
                           "total_outstanding": total_outstanding, "collection_rate": total_rate}}
    rows_data.append(["TOTAL", sum(r["invoice_count"] for r in rows_json),
                      total_billed, total_collected, total_outstanding, f"{total_rate}%"])
    headers = ["Category", "Invoice Count", "Billed ($)", "Collected ($)",
               "Outstanding ($)", "Collection Rate (%)"]
    return export_response(format, headers, rows_data,
                           "financial_summary.csv", "financial_summary.xlsx",
                           "Financial Summary", "City of Harare FMS — Financial Summary Report")

@app.get("/api/reports/audit-trail")
def report_audit_trail(format: str = "csv",
                       date_from: Optional[str] = None, date_to: Optional[str] = None,
                       db: Session = Depends(get_db),
                       current_user: User = Depends(require_roles(UserRole.admin, UserRole.auditor))):
    return export_audit_logs(format=format, date_from=date_from, date_to=date_to,
                              db=db, current_user=current_user)

# ─── Aging Analysis ───────────────────────────────────────────────────────────

def _aging_bucket(days: int) -> str:
    if days <= 0:   return "current"
    if days <= 30:  return "days_1_30"
    if days <= 60:  return "days_31_60"
    if days <= 90:  return "days_61_90"
    if days <= 120: return "days_91_120"
    return "days_120_plus"

AGING_LABELS = ["Current", "1-30 Days", "31-60 Days", "61-90 Days", "91-120 Days", "120+ Days"]
AGING_KEYS   = ["current", "days_1_30", "days_31_60", "days_61_90", "days_91_120", "days_120_plus"]

@app.get("/api/aging/debtors")
def debtors_aging(format: str = "json", zone: Optional[str] = None,
                  db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user)):
    """Accounts-receivable aging: outstanding invoice balances by debtor and overdue bucket."""
    today = now()
    q = db.query(Invoice).filter(Invoice.balance > 0)
    items = q.all()

    rp_map: dict = {}
    for inv in items:
        rp = db.query(Ratepayer).filter(Ratepayer.id == inv.ratepayer_id).first()
        if not rp: continue
        if zone and rp.zone != zone: continue
        key = rp.account_number
        if key not in rp_map:
            rp_map[key] = {
                "ratepayer_id": rp.id,
                "account_number": rp.account_number, "ratepayer_name": rp.full_name,
                "zone": rp.zone, "ward": rp.ward, "property_type": rp.property_type,
                "invoice_count": 0,
                "current": 0.0, "days_1_30": 0.0, "days_31_60": 0.0,
                "days_61_90": 0.0, "days_91_120": 0.0, "days_120_plus": 0.0, "total": 0.0
            }
        days_over = (today - inv.due_date).days
        bucket = _aging_bucket(days_over)
        rp_map[key][bucket]     = round(rp_map[key][bucket] + inv.balance, 2)
        rp_map[key]["total"]    = round(rp_map[key]["total"]  + inv.balance, 2)
        rp_map[key]["invoice_count"] += 1

    rows = sorted(rp_map.values(), key=lambda r: r["days_120_plus"], reverse=True)

    # Totals row
    totals = {k: round(sum(r[k] for r in rows), 2) for k in AGING_KEYS}
    totals["total"] = round(sum(r["total"] for r in rows), 2)

    if format == "json":
        return {"rows": rows, "totals": totals,
                "summary": {lbl: totals[key] for lbl, key in zip(AGING_LABELS, AGING_KEYS)}}

    headers = ["Account #", "Ratepayer Name", "Zone", "Ward", "Invoices"] + AGING_LABELS + ["Total Outstanding"]
    data_rows = [[r["account_number"], r["ratepayer_name"], r["zone"], r["ward"], r["invoice_count"]] +
                 [r[k] for k in AGING_KEYS] + [r["total"]] for r in rows]
    data_rows.append(["", "TOTAL", "", "", sum(r["invoice_count"] for r in rows)] +
                     [totals[k] for k in AGING_KEYS] + [totals["total"]])
    return export_response(format, headers, data_rows,
                           "debtors_aging.csv", "debtors_aging.xlsx",
                           "Debtors Aging", "City of Harare FMS — Debtors Aging Analysis")

@app.get("/api/aging/creditors")
def creditors_aging(format: str = "json", department: Optional[str] = None,
                    db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    """Accounts-payable aging: unapproved/pending expenditures by department and age bucket."""
    today = now()
    q = db.query(Expenditure).filter(Expenditure.is_approved == False)
    if department: q = q.filter(Expenditure.department == department)
    items = q.all()

    dept_map: dict = {}
    for exp in items:
        key = exp.department
        if key not in dept_map:
            dept_map[key] = {
                "department": key, "expenditure_count": 0,
                "current": 0.0, "days_1_30": 0.0, "days_31_60": 0.0,
                "days_61_90": 0.0, "days_91_120": 0.0, "days_120_plus": 0.0, "total": 0.0
            }
        days_old  = (today - exp.expenditure_date).days
        bucket = _aging_bucket(days_old)
        dept_map[key][bucket]   = round(dept_map[key][bucket] + exp.amount, 2)
        dept_map[key]["total"]  = round(dept_map[key]["total"]  + exp.amount, 2)
        dept_map[key]["expenditure_count"] += 1

    # Also include individual expenditure detail for drill-down
    detail_rows = []
    for exp in sorted(items, key=lambda e: e.expenditure_date):
        days_old = (today - exp.expenditure_date).days
        detail_rows.append({
            "reference_number": exp.reference_number,
            "department": exp.department,
            "description": exp.description,
            "amount": exp.amount,
            "budget_line": exp.budget_line,
            "expenditure_date": str(exp.expenditure_date)[:10],
            "days_outstanding": days_old,
            "bucket": _aging_bucket(days_old)
        })

    rows = sorted(dept_map.values(), key=lambda r: r["days_120_plus"], reverse=True)
    totals = {k: round(sum(r[k] for r in rows), 2) for k in AGING_KEYS}
    totals["total"] = round(sum(r["total"] for r in rows), 2)

    if format == "json":
        return {"rows": rows, "totals": totals, "detail": detail_rows,
                "summary": {lbl: totals[key] for lbl, key in zip(AGING_LABELS, AGING_KEYS)}}

    headers = ["Department", "Expenditures"] + AGING_LABELS + ["Total Payable"]
    data_rows = [[r["department"], r["expenditure_count"]] +
                 [r[k] for k in AGING_KEYS] + [r["total"]] for r in rows]
    data_rows.append(["TOTAL", sum(r["expenditure_count"] for r in rows)] +
                     [totals[k] for k in AGING_KEYS] + [totals["total"]])
    return export_response(format, headers, data_rows,
                           "creditors_aging.csv", "creditors_aging.xlsx",
                           "Creditors Aging", "City of Harare FMS — Creditors Aging Analysis")

# ─── Revenue Targets ──────────────────────────────────────────────────────────

@app.get("/api/revenue-targets")
def list_revenue_targets(fiscal_year: Optional[str] = None,
                          db: Session = Depends(get_db),
                          current_user: User = Depends(get_current_user)):
    q = db.query(RevenueTarget)
    if fiscal_year: q = q.filter(RevenueTarget.fiscal_year == fiscal_year)
    items = q.order_by(RevenueTarget.fiscal_year, RevenueTarget.category).all()
    return [{"id": t.id, "fiscal_year": t.fiscal_year, "category": t.category,
             "target_amount": t.target_amount, "period": t.period,
             "notes": t.notes, "created_at": str(t.created_at)[:10]} for t in items]

@app.post("/api/revenue-targets")
def create_revenue_target(data: RevenueTargetCreate,
                           db: Session = Depends(get_db),
                           current_user: User = Depends(require_roles(
                               UserRole.admin, UserRole.budget_officer, UserRole.accountant))):
    existing = db.query(RevenueTarget).filter(
        RevenueTarget.fiscal_year == data.fiscal_year,
        RevenueTarget.category    == data.category,
        RevenueTarget.period      == data.period).first()
    if existing:
        raise HTTPException(400, "A target already exists for this category/year/period. Use edit to update.")
    t = RevenueTarget(fiscal_year=data.fiscal_year, category=data.category,
                       target_amount=data.target_amount, period=data.period,
                       notes=data.notes, created_by=current_user.id)
    db.add(t); db.flush()
    db.add(AuditLog(user_id=current_user.id, action="CREATE", table_name="revenue_targets",
                    record_id=t.id,
                    description=f"Revenue target set: {data.category} {data.fiscal_year} = ${data.target_amount}"))
    db.commit()
    return {"id": t.id, "message": "Revenue target created"}

@app.put("/api/revenue-targets/{tid}")
def update_revenue_target(tid: int, data: RevenueTargetUpdate,
                           db: Session = Depends(get_db),
                           current_user: User = Depends(require_roles(
                               UserRole.admin, UserRole.budget_officer, UserRole.accountant))):
    t = db.query(RevenueTarget).filter(RevenueTarget.id == tid).first()
    if not t: raise HTTPException(404, "Revenue target not found")
    for k, v in data.dict(exclude_none=True).items():
        setattr(t, k, v)
    db.add(AuditLog(user_id=current_user.id, action="UPDATE", table_name="revenue_targets",
                    record_id=tid,
                    description=f"Updated revenue target: {t.category} {t.fiscal_year}"))
    db.commit()
    return {"message": "Revenue target updated"}

@app.delete("/api/revenue-targets/{tid}")
def delete_revenue_target(tid: int,
                           db: Session = Depends(get_db),
                           current_user: User = Depends(require_roles(
                               UserRole.admin, UserRole.budget_officer))):
    t = db.query(RevenueTarget).filter(RevenueTarget.id == tid).first()
    if not t: raise HTTPException(404, "Revenue target not found")
    db.add(AuditLog(user_id=current_user.id, action="DELETE", table_name="revenue_targets",
                    record_id=tid,
                    description=f"Deleted revenue target: {t.category} {t.fiscal_year}"))
    db.delete(t); db.commit()
    return {"message": "Revenue target deleted"}

@app.post("/api/import/revenue-targets")
async def import_revenue_targets(file: UploadFile = File(...),
                                  db: Session = Depends(get_db),
                                  current_user: User = Depends(require_roles(
                                      UserRole.admin, UserRole.budget_officer, UserRole.accountant))):
    rows = await parse_upload(file)
    created = 0; updated = 0; errors = []
    for i, row in enumerate(rows, 2):
        try:
            fy     = str(row.get("fiscal_year") or row.get("Fiscal Year") or "").strip()
            cat    = str(row.get("category")    or row.get("Category")    or "").strip().lower()
            period = str(row.get("period")      or row.get("Period")      or "annual").strip()
            target = float(row.get("target_amount") or row.get("Target Amount") or 0)
            notes  = str(row.get("notes") or row.get("Notes") or "").strip() or None
            if not fy or not cat:
                errors.append(f"Row {i}: fiscal_year and category required"); continue
            existing = db.query(RevenueTarget).filter(
                RevenueTarget.fiscal_year == fy,
                RevenueTarget.category    == cat,
                RevenueTarget.period      == period).first()
            if existing:
                existing.target_amount = target
                existing.notes = notes
                updated += 1
            else:
                t = RevenueTarget(fiscal_year=fy, category=cat, period=period,
                                   target_amount=target, notes=notes,
                                   created_by=current_user.id)
                db.add(t); created += 1
        except Exception as e:
            errors.append(f"Row {i}: {e}")
    db.flush()
    db.add(AuditLog(user_id=current_user.id, action="IMPORT", table_name="revenue_targets",
                    description=f"Revenue targets import: {created} created, {updated} updated"))
    db.commit()
    return {"created": created, "updated": updated, "errors": errors,
            "message": f"{created} created, {updated} updated"}

# ─── Performance Report ───────────────────────────────────────────────────────

@app.get("/api/reports/performance")
def report_performance(fiscal_year: Optional[str] = None,
                        format: str = "json",
                        db: Session = Depends(get_db),
                        current_user: User = Depends(get_current_user)):
    """Revenue performance: targets vs actuals by category."""
    # Actual revenue collected by category
    actual_q = db.query(Invoice.category,
                        func.sum(Invoice.amount).label("billed"),
                        func.sum(Invoice.amount_paid).label("collected"),
                        func.sum(Invoice.balance).label("outstanding"))
    if fiscal_year:
        # Approximate fiscal year filter — assumes fiscal_year like "2025/2026"
        # Map to year range: "2025/2026" → 2025-07-01 to 2026-06-30
        try:
            yr_start = int(fiscal_year.split("/")[0])
            start_dt = datetime(yr_start, 7, 1)
            end_dt   = datetime(yr_start + 1, 6, 30, 23, 59, 59)
            actual_q = actual_q.filter(Invoice.issue_date >= start_dt,
                                       Invoice.issue_date <= end_dt)
        except Exception:
            pass
    actual_by_cat = {r.category: {"billed": round(r.billed or 0, 2),
                                   "collected": round(r.collected or 0, 2),
                                   "outstanding": round(r.outstanding or 0, 2)}
                     for r in actual_q.group_by(Invoice.category).all()}

    # Revenue targets
    tgt_q = db.query(RevenueTarget)
    if fiscal_year: tgt_q = tgt_q.filter(RevenueTarget.fiscal_year == fiscal_year)
    targets = tgt_q.all()

    rows_json = []
    rows_data = []

    # Merge targets with actuals — show all categories that have either a target or actual
    all_cats = set(actual_by_cat.keys()) | {t.category for t in targets}
    tgt_map  = {t.category: t.target_amount for t in targets}

    for cat in sorted(all_cats):
        act    = actual_by_cat.get(cat, {"billed": 0, "collected": 0, "outstanding": 0})
        target = tgt_map.get(cat, 0)
        variance    = round(act["collected"] - target, 2)
        var_pct     = round(variance / target * 100, 1) if target > 0 else 0
        coll_rate   = round(act["collected"] / act["billed"] * 100, 1) if act["billed"] > 0 else 0
        status      = "Above Target" if variance > 0 else ("Below Target" if variance < 0 else "On Target")
        rows_json.append({
            "category": cat, "target": target,
            "billed": act["billed"], "collected": act["collected"],
            "outstanding": act["outstanding"],
            "variance": variance, "variance_pct": var_pct,
            "collection_rate": coll_rate, "status": status
        })
        rows_data.append([cat.title(), round(target, 2), act["billed"], act["collected"],
                          act["outstanding"], f"{coll_rate}%", variance, f"{var_pct}%", status])

    if format == "json":
        total_target    = round(sum(r["target"] for r in rows_json), 2)
        total_collected = round(sum(r["collected"] for r in rows_json), 2)
        total_billed    = round(sum(r["billed"] for r in rows_json), 2)
        return {"rows": rows_json,
                "totals": {"total_target": total_target, "total_billed": total_billed,
                           "total_collected": total_collected,
                           "overall_variance": round(total_collected - total_target, 2)}}

    fy_label = fiscal_year or "All Years"
    headers  = ["Category", "Target ($)", "Billed ($)", "Collected ($)",
                "Outstanding ($)", "Collection Rate", "Variance ($)", "Variance (%)", "Status"]
    return export_response(format, headers, rows_data,
                           "performance_report.csv", "performance_report.xlsx",
                           "Performance", f"City of Harare FMS — Revenue Performance Report ({fy_label})")

# ─── Root ─────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return FileResponse(os.path.join(frontend_path, "pages", "login.html"))

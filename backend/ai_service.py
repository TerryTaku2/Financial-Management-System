"""
AI Analysis Service — City of Harare FMS
Uses Claude claude-sonnet-4-6 with live SQLAlchemy queries against the actual
FMS database models (Invoice, Payment, Budget, LeakageAlert, Ratepayer, etc.)
"""

import os
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

import anthropic

from database import (
    Invoice, Payment, Budget, LeakageAlert, Ratepayer, Expenditure,
    RevenueTarget, AuditLog, User,
    PaymentStatus, AnomalyFlag, RevenueCategory
)

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You are an expert financial analyst embedded in the City of Harare's
Financial Management System (FMS v2.1). Your role is to analyse live municipal revenue
data, identify leakage risks, explain anomalies, and provide actionable recommendations
to city finance officers and management.

Key facts about this system:
- City of Harare has a documented revenue leakage problem: ~39.7% collection rate
- Primary leakage vectors: unreconciled cash payments, ghost ratepayers, duplicate
  billing, and unauthorised waivers
- Revenue categories: rates (largest), water, sewerage, refuse, licensing, parking,
  rentals, other
- Anomaly detection uses Z-score statistical analysis (Grubbs 1969)
- Risk index: 40% overdue ratio + 25% overdue balance + 35% anomaly rate

When answering:
- Be specific — cite exact figures from the data provided
- Use bullet points for lists and recommendations
- Bold key figures using **asterisks**
- End every analysis with 2–3 prioritised, actionable recommendations
- Write in a professional tone suitable for a municipal finance report
- If data is limited, say so clearly rather than speculating"""


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ── Data fetchers ──────────────────────────────────────────────────────────────

def _get_revenue_summary(db: Session) -> str:
    rows = (db.query(
                Invoice.category,
                func.sum(Invoice.amount).label("billed"),
                func.sum(Invoice.amount_paid).label("collected"),
                func.sum(Invoice.balance).label("outstanding"),
                func.count(Invoice.id).label("count")
            )
            .group_by(Invoice.category)
            .order_by(desc("outstanding"))
            .all())
    if not rows:
        return "No revenue data available."
    lines = []
    for r in rows:
        cat = r.category.value if hasattr(r.category, 'value') else str(r.category)
        rate = round(r.collected / r.billed * 100, 1) if r.billed else 0
        lines.append(
            f"  {cat}: billed=${r.billed:,.2f}, collected=${r.collected:,.2f}, "
            f"outstanding=${r.outstanding:,.2f}, collection_rate={rate}%, invoices={r.count}"
        )
    return "\n".join(lines)


def _get_kpis(db: Session) -> str:
    billed      = db.query(func.sum(Invoice.amount)).scalar() or 0
    collected   = db.query(func.sum(Payment.amount)).scalar() or 0
    outstanding = db.query(func.sum(Invoice.balance)).filter(Invoice.status != PaymentStatus.paid).scalar() or 0
    overdue_bal = db.query(func.sum(Invoice.balance)).filter(Invoice.status == PaymentStatus.overdue).scalar() or 0
    alerts      = db.query(func.count(LeakageAlert.id)).filter(LeakageAlert.is_resolved == False).scalar() or 0
    anomalies   = db.query(func.count(Invoice.id)).filter(Invoice.anomaly_flag != AnomalyFlag.none).scalar() or 0
    unrecon     = db.query(func.count(Payment.id)).filter(Payment.is_reconciled == False).scalar() or 0
    ratepayers  = db.query(func.count(Ratepayer.id)).scalar() or 0
    rate        = round(collected / billed * 100, 1) if billed else 0
    return (
        f"  total_billed=${billed:,.2f}, total_collected=${collected:,.2f}, "
        f"collection_rate={rate}%, outstanding=${outstanding:,.2f}, "
        f"overdue_balance=${overdue_bal:,.2f}, active_alerts={alerts}, "
        f"anomaly_flags={anomalies}, unreconciled_payments={unrecon}, "
        f"total_ratepayers={ratepayers}"
    )


def _get_anomalies(db: Session, limit: int = 10) -> str:
    rows = (db.query(Invoice)
            .filter(Invoice.anomaly_flag != AnomalyFlag.none)
            .order_by(desc(Invoice.amount))
            .limit(limit).all())
    if not rows:
        return "  No anomalous invoices flagged."
    lines = []
    for inv in rows:
        flag = inv.anomaly_flag.value if hasattr(inv.anomaly_flag, 'value') else str(inv.anomaly_flag)
        cat  = inv.category.value if hasattr(inv.category, 'value') else str(inv.category)
        st   = inv.status.value if hasattr(inv.status, 'value') else str(inv.status)
        lines.append(
            f"  {inv.invoice_number}: ${inv.amount:,.2f} [{flag}] cat={cat} status={st}"
            + (f" reason={inv.anomaly_reason}" if inv.anomaly_reason else "")
        )
    return "\n".join(lines)


def _get_monthly_trend(db: Session, months: int = 6) -> str:
    lines = []
    for i in range(months - 1, -1, -1):
        ref = _now() - timedelta(days=30 * i)
        ms  = ref.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        me  = ms.replace(month=ms.month % 12 + 1, day=1) if ms.month < 12 else ms.replace(year=ms.year + 1, month=1, day=1)
        b   = db.query(func.sum(Invoice.amount)).filter(Invoice.issue_date >= ms, Invoice.issue_date < me).scalar() or 0
        c   = db.query(func.sum(Payment.amount)).filter(Payment.payment_date >= ms, Payment.payment_date < me).scalar() or 0
        rate = round(c / b * 100, 1) if b else 0
        lines.append(f"  {ms.strftime('%b %Y')}: billed=${b:,.2f}, collected=${c:,.2f}, rate={rate}%")
    return "\n".join(lines)


def _get_top_debtors(db: Session, limit: int = 5) -> str:
    rows = (db.query(
                Ratepayer.full_name, Ratepayer.account_number, Ratepayer.ward,
                func.sum(Invoice.balance).label("overdue")
            )
            .join(Invoice, Invoice.ratepayer_id == Ratepayer.id)
            .filter(Invoice.status == PaymentStatus.overdue)
            .group_by(Ratepayer.id)
            .order_by(desc("overdue"))
            .limit(limit).all())
    if not rows:
        return "  No overdue accounts."
    return "\n".join(
        f"  {r.full_name} ({r.account_number}, {r.ward}): ${r.overdue:,.2f} overdue"
        for r in rows
    )


def _get_leakage_alerts(db: Session) -> str:
    rows = (db.query(LeakageAlert)
            .filter(LeakageAlert.is_resolved == False)
            .order_by(LeakageAlert.created_at.desc())
            .limit(10).all())
    if not rows:
        return "  No active leakage alerts."
    return "\n".join(
        f"  [{a.severity.upper()}] {a.alert_type}: {a.description}"
        for a in rows
    )


def _get_budget_overview(db: Session) -> str:
    rows = db.query(Budget).order_by(Budget.allocated_amount.desc()).limit(10).all()
    if not rows:
        return "  No budget data."
    lines = []
    for b in rows:
        util = round(b.spent_amount / b.allocated_amount * 100, 1) if b.allocated_amount else 0
        flag = " ⚠️ OVER" if b.spent_amount > b.allocated_amount else ""
        lines.append(f"  {b.department}: allocated=${b.allocated_amount:,.2f}, spent=${b.spent_amount:,.2f}, utilisation={util}%{flag}")
    return "\n".join(lines)


def _build_context(query: str, db: Session) -> str:
    ts = _now().strftime('%d %B %Y %H:%M')
    return f"""=== LIVE CITY OF HARARE FMS DATA — {ts} ===

KEY PERFORMANCE INDICATORS:
{_get_kpis(db)}

REVENUE BY CATEGORY (billed vs collected):
{_get_revenue_summary(db)}

MONTHLY TREND (last 6 months):
{_get_monthly_trend(db)}

TOP 5 OVERDUE ACCOUNTS:
{_get_top_debtors(db)}

ACTIVE LEAKAGE ALERTS:
{_get_leakage_alerts(db)}

TOP ANOMALY-FLAGGED INVOICES:
{_get_anomalies(db)}

BUDGET UTILISATION BY DEPARTMENT:
{_get_budget_overview(db)}

=== ANALYST QUESTION ===
{query}"""


# ── Public API ─────────────────────────────────────────────────────────────────

def analyse(query: str, db: Session) -> str:
    """Non-streaming analysis. Returns complete text response."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key or api_key == "your-api-key-here":
        raise ValueError("ANTHROPIC_API_KEY not configured.")
    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_context(query, db)}],
    )
    return response.content[0].text


def analyse_stream(query: str, db: Session):
    """Streaming generator — yields text tokens as they arrive from Claude."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key or api_key == "your-api-key-here":
        yield "Error: ANTHROPIC_API_KEY not configured. Add it to the .env file."
        return
    client = anthropic.Anthropic(api_key=api_key)
    with client.messages.stream(
        model=MODEL,
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_context(query, db)}],
    ) as stream:
        for text in stream.text_stream:
            yield text

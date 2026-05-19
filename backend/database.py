import os
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, Enum, text, inspect as sa_inspect
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime, timezone

def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

import enum

DATABASE_URL = "sqlite:///" + os.path.join(os.path.dirname(os.path.abspath(__file__)), "fms_harare.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class UserRole(str, enum.Enum):
    admin = "admin"
    revenue_officer = "revenue_officer"
    auditor = "auditor"
    accountant = "accountant"
    budget_officer = "budget_officer"

class PaymentStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    overdue = "overdue"
    disputed = "disputed"
    waived = "waived"

class RevenueCategory(str, enum.Enum):
    rates = "rates"
    water = "water"
    sewerage = "sewerage"
    refuse = "refuse"
    licensing = "licensing"
    parking = "parking"
    rentals = "rentals"
    other = "other"

class AnomalyFlag(str, enum.Enum):
    none = "none"
    low = "low"
    medium = "medium"
    high = "high"

class PaymentPlanStatus(str, enum.Enum):
    active = "active"
    completed = "completed"
    defaulted = "defaulted"
    cancelled = "cancelled"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    full_name = Column(String)
    email = Column(String, unique=True)
    hashed_password = Column(String)
    role = Column(Enum(UserRole), default=UserRole.revenue_officer)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)
    last_login = Column(DateTime, nullable=True)
    failed_login_count = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    password_changed_at = Column(DateTime, nullable=True)

class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True)
    ip_address = Column(String, nullable=True)
    success = Column(Boolean, default=False)
    attempted_at = Column(DateTime, default=utcnow)
    failure_reason = Column(String, nullable=True)

class Ratepayer(Base):
    __tablename__ = "ratepayers"
    id = Column(Integer, primary_key=True, index=True)
    account_number = Column(String, unique=True, index=True)
    full_name = Column(String)
    address = Column(String)
    ward = Column(String)
    zone = Column(String)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    property_type = Column(String, default="residential")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)
    risk_score = Column(Float, default=0.0)
    risk_label = Column(String, default="low")
    risk_updated_at = Column(DateTime, nullable=True)
    invoices = relationship("Invoice", back_populates="ratepayer")
    payments = relationship("Payment", back_populates="ratepayer")
    payment_plans = relationship("PaymentPlan", back_populates="ratepayer")

class Invoice(Base):
    __tablename__ = "invoices"
    id = Column(Integer, primary_key=True, index=True)
    invoice_number = Column(String, unique=True, index=True)
    ratepayer_id = Column(Integer, ForeignKey("ratepayers.id"))
    category = Column(Enum(RevenueCategory))
    amount = Column(Float)
    amount_paid = Column(Float, default=0.0)
    balance = Column(Float)
    issue_date = Column(DateTime, default=utcnow)
    due_date = Column(DateTime)
    status = Column(Enum(PaymentStatus), default=PaymentStatus.pending)
    anomaly_flag = Column(Enum(AnomalyFlag), default=AnomalyFlag.none)
    anomaly_reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"))
    fingerprint = Column(String, nullable=True, index=True)
    ratepayer = relationship("Ratepayer", back_populates="invoices")

class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True, index=True)
    receipt_number = Column(String, unique=True, index=True)
    ratepayer_id = Column(Integer, ForeignKey("ratepayers.id"))
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=True)
    amount = Column(Float)
    payment_method = Column(String, default="cash")
    currency = Column(String, default="USD")
    payment_date = Column(DateTime, default=utcnow)
    collected_by = Column(Integer, ForeignKey("users.id"))
    is_reconciled = Column(Boolean, default=False)
    reconciled_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reconciled_at = Column(DateTime, nullable=True)
    anomaly_flag = Column(Enum(AnomalyFlag), default=AnomalyFlag.none)
    anomaly_reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    idempotency_key = Column(String, nullable=True, unique=True)
    ratepayer = relationship("Ratepayer", back_populates="payments")

class PaymentPlan(Base):
    __tablename__ = "payment_plans"
    id = Column(Integer, primary_key=True, index=True)
    ratepayer_id = Column(Integer, ForeignKey("ratepayers.id"))
    total_debt = Column(Float)
    instalment_amount = Column(Float)
    frequency = Column(String, default="monthly")
    total_instalments = Column(Integer)
    instalments_paid = Column(Integer, default=0)
    start_date = Column(DateTime)
    next_due_date = Column(DateTime)
    status = Column(Enum(PaymentPlanStatus), default=PaymentPlanStatus.active)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=utcnow)
    notes = Column(Text, nullable=True)
    ratepayer = relationship("Ratepayer", back_populates="payment_plans")

class Expenditure(Base):
    __tablename__ = "expenditures"
    id = Column(Integer, primary_key=True, index=True)
    reference_number = Column(String, unique=True)
    department = Column(String)
    description = Column(Text)
    amount = Column(Float)
    budget_line = Column(String)
    expenditure_date = Column(DateTime, default=utcnow)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    is_approved = Column(Boolean, default=False)
    anomaly_flag = Column(Enum(AnomalyFlag), default=AnomalyFlag.none)

class Budget(Base):
    __tablename__ = "budgets"
    id = Column(Integer, primary_key=True, index=True)
    fiscal_year = Column(String)
    department = Column(String)
    category = Column(String)
    allocated_amount = Column(Float)
    spent_amount = Column(Float, default=0.0)
    remaining = Column(Float)
    created_at = Column(DateTime, default=utcnow)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String)
    table_name = Column(String)
    record_id = Column(Integer, nullable=True)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    ip_address = Column(String, nullable=True)
    timestamp = Column(DateTime, default=utcnow)
    description = Column(Text, nullable=True)

class LeakageAlert(Base):
    __tablename__ = "leakage_alerts"
    id = Column(Integer, primary_key=True, index=True)
    alert_type = Column(String)
    severity = Column(String, default="medium")
    description = Column(Text)
    related_record_id = Column(Integer, nullable=True)
    related_table = Column(String, nullable=True)
    is_resolved = Column(Boolean, default=False)
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    resolved_at = Column(DateTime, nullable=True)
    resolution_notes = Column(Text, nullable=True)

class RevenueTarget(Base):
    __tablename__ = "revenue_targets"
    id = Column(Integer, primary_key=True, index=True)
    fiscal_year = Column(String, index=True)
    category = Column(String)
    target_amount = Column(Float)
    period = Column(String, default="annual")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)

class SystemNotification(Base):
    __tablename__ = "system_notifications"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    title = Column(String)
    message = Column(Text)
    category = Column(String, default="info")
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)
    expires_at = Column(DateTime, nullable=True)
    related_table = Column(String, nullable=True)
    related_record_id = Column(Integer, nullable=True)

class ExchangeRate(Base):
    __tablename__ = "exchange_rates"
    id = Column(Integer, primary_key=True, index=True)
    currency = Column(String, unique=True, index=True)
    rate_to_usd = Column(Float, default=1.0)
    source = Column(String, nullable=True)
    manual = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=utcnow)

class BillingRate(Base):
    __tablename__ = "billing_rates"
    id = Column(Integer, primary_key=True, index=True)
    category = Column(Enum(RevenueCategory), unique=True)
    flat_amount = Column(Float, default=0.0)
    description = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_at = Column(DateTime, default=utcnow)

class BillingRun(Base):
    __tablename__ = "billing_runs"
    id = Column(Integer, primary_key=True, index=True)
    run_number = Column(String, unique=True, index=True)
    billing_period = Column(String)
    categories = Column(String, nullable=True)
    due_date = Column(DateTime)
    invoices_created = Column(Integer, default=0)
    total_amount = Column(Float, default=0.0)
    status = Column(String, default="completed")
    notes = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=utcnow)

Base.metadata.create_all(bind=engine)

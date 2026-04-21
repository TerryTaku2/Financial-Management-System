from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, Enum
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime, timezone

def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

import enum

DATABASE_URL = "sqlite:///./fms_harare.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ─── Enums ───────────────────────────────────────────────────────────────────

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

# ─── Models ──────────────────────────────────────────────────────────────────

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
    invoices = relationship("Invoice", back_populates="ratepayer")
    payments = relationship("Payment", back_populates="ratepayer")

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
    anomaly_flag = Column(Enum(AnomalyFlag), default=AnomalyFlag.none)
    anomaly_reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    ratepayer = relationship("Ratepayer", back_populates="payments")

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

class RevenueTarget(Base):
    """Planned/target revenue by category and fiscal year for performance tracking."""
    __tablename__ = "revenue_targets"
    id = Column(Integer, primary_key=True, index=True)
    fiscal_year = Column(String, index=True)
    category = Column(String)          # rates, water, sewerage, etc.
    target_amount = Column(Float)      # planned revenue for the period
    period = Column(String, default="annual")  # annual, Q1, Q2, Q3, Q4, or YYYY-MM
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)

Base.metadata.create_all(bind=engine)

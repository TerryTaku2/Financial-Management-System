import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from database import SessionLocal, User, Ratepayer, Invoice, Payment, Expenditure, Budget, AuditLog, LeakageAlert
from database import UserRole, PaymentStatus, RevenueCategory, AnomalyFlag
from auth import hash_password
from datetime import datetime, timedelta, timezone

def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)
import random, string

db = SessionLocal()

def rnd_acct():
    return "COH-" + "".join(random.choices(string.digits, k=6))

def rnd_inv():
    return "INV-" + "".join(random.choices(string.digits, k=8))

def rnd_rcpt():
    return "RCP-" + "".join(random.choices(string.digits, k=8))

# ── Users ──────────────────────────────────────────────────────
users_data = [
    ("admin", "System Administrator", "admin@harare.gov.zw", "admin123", UserRole.admin),
    ("t.muromba", "Terrence Muromba", "t.muromba@harare.gov.zw", "password123", UserRole.accountant),
    ("r.officer1", "Ruth Chikwanda", "r.chikwanda@harare.gov.zw", "password123", UserRole.revenue_officer),
    ("r.officer2", "James Moyo", "j.moyo@harare.gov.zw", "password123", UserRole.revenue_officer),
    ("auditor1", "Grace Mutasa", "g.mutasa@harare.gov.zw", "password123", UserRole.auditor),
    ("budget1", "Peter Ncube", "p.ncube@harare.gov.zw", "password123", UserRole.budget_officer),
]
created_users = []
for uname, fname, email, pwd, role in users_data:
    existing = db.query(User).filter(User.username == uname).first()
    if not existing:
        u = User(username=uname, full_name=fname, email=email,
                 hashed_password=hash_password(pwd), role=role,
                 last_login=now())
        db.add(u)
        db.flush()
        created_users.append(u)
    else:
        created_users.append(existing)
db.commit()

admin_user = db.query(User).filter(User.username == "admin").first()
officer1 = db.query(User).filter(User.username == "r.officer1").first()

# ── Ratepayers ─────────────────────────────────────────────────
wards = ["Ward 1", "Ward 2", "Ward 3", "Ward 5", "Ward 7", "Ward 10", "Ward 17", "Ward 22"]
zones = ["Avondale", "Borrowdale", "Chitungwiza", "Glen Norah", "Highfield",
         "Kuwadzana", "Mabvuku", "Mbare", "Mount Pleasant", "Southerton"]
property_types = ["residential", "commercial", "industrial"]
names = [
    ("Tatenda Moyo","0771234001"),("Chido Mutasa","0772234002"),("Blessing Ncube","0773234003"),
    ("Tafara Dube","0774234004"),("Rudo Sibanda","0775234005"),("Farai Chikwanda","0776234006"),
    ("Tinashe Banda","0777234007"),("Nyasha Zimba","0778234008"),("Kudzai Mhaka","0779234009"),
    ("Simba Charamba","0771234010"),("Memory Gumbo","0772234011"),("Tapiwa Nhamo","0773234012"),
    ("Rumbidzai Mpofu","0774234013"),("Tinotenda Shava","0775234014"),("Kudakwashe Zvobgo","0776234015"),
    ("Panashe Marange","0777234016"),("Mufaro Chitsa","0778234017"),("Tanaka Musariri","0779234018"),
    ("Tawanda Munyoro","0771234019"),("Yeukai Mahachi","0772234020"),
    ("ABC Hardware Ltd","0773234021"),("Harare Bakery Co","0774234022"),("ZimTech Solutions","0775234023"),
    ("Sunrise Pharmacy","0776234024"),("Mbare Fresh Produce","0777234025"),
]
ratepayers = []
for name, phone in names:
    existing = db.query(Ratepayer).filter(Ratepayer.phone == phone).first()
    if not existing:
        r = Ratepayer(
            account_number=rnd_acct(), full_name=name,
            address=f"{random.randint(1,200)} {random.choice(['Samora Machel','Jason Moyo','Robert Mugabe','Kaguvi','Angwa'])} St",
            ward=random.choice(wards), zone=random.choice(zones),
            phone=phone, email=f"{name.lower().replace(' ','.')[:12]}@gmail.com",
            property_type=random.choice(property_types)
        )
        db.add(r)
        db.flush()
        ratepayers.append(r)
    else:
        ratepayers.append(existing)
db.commit()

ratepayers = db.query(Ratepayer).all()

# ── Invoices + Payments ────────────────────────────────────────
categories = list(RevenueCategory)
statuses_weighted = ([PaymentStatus.paid]*8 + [PaymentStatus.overdue]*5 +
                     [PaymentStatus.pending]*4 + [PaymentStatus.disputed]*2 + [PaymentStatus.waived])
anomaly_rates = [AnomalyFlag.none]*15 + [AnomalyFlag.low]*4 + [AnomalyFlag.medium]*2 + [AnomalyFlag.high]

invoice_count = db.query(Invoice).count()
if invoice_count < 10:
    for rp in ratepayers:
        for _ in range(random.randint(2, 5)):
            cat = random.choice(categories)
            amount = round(random.uniform(20, 800), 2)
            days_ago = random.randint(10, 180)
            issue_dt = now() - timedelta(days=days_ago)
            due_dt = issue_dt + timedelta(days=30)
            status = random.choice(statuses_weighted)
            flag = random.choice(anomaly_rates)
            paid = amount if status == PaymentStatus.paid else (round(amount * random.uniform(0.1,0.7),2) if status == PaymentStatus.pending else 0.0)
            reason = None
            if flag == AnomalyFlag.high:
                reason = "Payment recorded without matching invoice reference"
            elif flag == AnomalyFlag.medium:
                reason = "Amount significantly below average for category"
            elif flag == AnomalyFlag.low:
                reason = "Duplicate payment pattern detected"

            inv = Invoice(
                invoice_number=rnd_inv(), ratepayer_id=rp.id,
                category=cat, amount=amount, amount_paid=paid,
                balance=round(amount - paid, 2),
                issue_date=issue_dt, due_date=due_dt,
                status=status, anomaly_flag=flag, anomaly_reason=reason,
                created_by=admin_user.id
            )
            db.add(inv)
            db.flush()

            if status == PaymentStatus.paid:
                pmt = Payment(
                    receipt_number=rnd_rcpt(), ratepayer_id=rp.id,
                    invoice_id=inv.id, amount=amount,
                    payment_method=random.choice(["cash","ecocash","bank_transfer","rtgs"]),
                    currency=random.choice(["USD","ZIG"]),
                    payment_date=due_dt - timedelta(days=random.randint(0,25)),
                    collected_by=officer1.id,
                    is_reconciled=random.choice([True, True, False]),
                    anomaly_flag=flag, anomaly_reason=reason
                )
                db.add(pmt)
    db.commit()

# ── Expenditures ───────────────────────────────────────────────
dept_list = ["Finance","Water & Sanitation","Roads","Waste Management","Health","Human Resources","ICT"]
exp_count = db.query(Expenditure).count()
if exp_count < 5:
    for _ in range(40):
        dept = random.choice(dept_list)
        amount = round(random.uniform(500, 50000), 2)
        flag = random.choice([AnomalyFlag.none]*12 + [AnomalyFlag.low]*3 + [AnomalyFlag.medium])
        e = Expenditure(
            reference_number="EXP-" + "".join(random.choices(string.digits, k=7)),
            department=dept, description=f"{dept} operational expenditure",
            amount=amount, budget_line=f"BL-{random.randint(100,999)}",
            expenditure_date=now() - timedelta(days=random.randint(1,120)),
            approved_by=admin_user.id, is_approved=random.choice([True,True,False]),
            anomaly_flag=flag
        )
        db.add(e)
    db.commit()

# ── Budgets ────────────────────────────────────────────────────
bgt_count = db.query(Budget).count()
if bgt_count < 5:
    for dept in dept_list:
        allocated = round(random.uniform(100000, 2000000), 2)
        spent = round(allocated * random.uniform(0.3, 0.95), 2)
        b = Budget(
            fiscal_year="2025/2026", department=dept,
            category="Operational", allocated_amount=allocated,
            spent_amount=spent, remaining=round(allocated - spent, 2)
        )
        db.add(b)
    db.commit()

# ── Leakage Alerts ─────────────────────────────────────────────
alert_count = db.query(LeakageAlert).count()
if alert_count < 3:
    alerts = [
        ("Unreconciled Payments", "high", "47 payments totalling $12,450 remain unreconciled for >30 days", "payments"),
        ("Duplicate Invoice Pattern", "medium", "3 ratepayers billed twice for same period in Water category", "invoices"),
        ("Waiver Irregularity", "high", "Unusual spike in penalty waivers — 18 waivers in 7 days vs avg of 2/week", "invoices"),
        ("Cash Collection Gap", "medium", "Cash receipts for Ward 7 show $3,200 shortfall vs field collection report", "payments"),
        ("Stale Overdue Accounts", "low", "112 accounts overdue >90 days with no follow-up action logged", "invoices"),
        ("Budget Overrun Risk", "medium", "Roads department at 91% of budget with 4 months remaining in fiscal year", "budgets"),
    ]
    for atype, sev, desc, table in alerts:
        la = LeakageAlert(alert_type=atype, severity=sev, description=desc,
                          related_table=table, is_resolved=False)
        db.add(la)
    db.commit()

# ── Audit Logs ─────────────────────────────────────────────────
log_count = db.query(AuditLog).count()
if log_count < 5:
    actions = [
        ("LOGIN","users","User logged into system"),
        ("CREATE","invoices","New invoice created"),
        ("UPDATE","payments","Payment reconciled"),
        ("CREATE","payments","Payment receipt issued"),
        ("UPDATE","invoices","Invoice status changed to overdue"),
        ("FLAG","payments","Anomaly flag raised on payment"),
    ]
    for _ in range(30):
        act, tbl, desc = random.choice(actions)
        al = AuditLog(
            user_id=random.choice(created_users).id,
            action=act, table_name=tbl,
            record_id=random.randint(1,50),
            description=desc,
            ip_address=f"192.168.1.{random.randint(2,50)}",
            timestamp=now() - timedelta(hours=random.randint(1,500))
        )
        db.add(al)
    db.commit()

print("Database seeded successfully.")
db.close()

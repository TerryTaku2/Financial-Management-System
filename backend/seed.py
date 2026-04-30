import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from database import SessionLocal, User, Ratepayer, Invoice, Payment, Expenditure, Budget, AuditLog, LeakageAlert, RevenueTarget
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

# ── Invoices + Payments ───────────────────────────────────────────────────────
# Invoice amounts calibrated against the 2024/2025 COH Consolidated Budget
# (COH, 2024; converted from ZiG at 1 USD = 1,000 ZiG, mid-year average rate).
# Category bands reflect the proportional revenue weight of each revenue stream:
#   rates:     largest revenue stream — Assessment Rates ($3.46M target across ~50k accounts)
#   water:     second largest service charge — metered + flat-rate billings
#   sewerage:  directly tied to water consumption volume
#   refuse:    flat-rate per property type (residential lower, commercial higher)
#   licensing: business and liquor licences — higher per-account value
#   parking:   CBD and off-street — lower per-transaction values
#   rentals:   council estate and commercial property — monthly recurring
#   other:     admin fees, fines, IGP income

# Amount ranges in USD per billing cycle, by revenue category and property type
CATEGORY_BANDS = {
    "rates":     {"residential": (80, 350),  "commercial": (300, 1500), "industrial": (600, 4000)},
    "water":     {"residential": (15, 90),   "commercial": (80, 500),   "industrial": (200, 1200)},
    "sewerage":  {"residential": (8, 45),    "commercial": (40, 250),   "industrial": (100, 600)},
    "refuse":    {"residential": (5, 25),    "commercial": (20, 120),   "industrial": (50, 300)},
    "licensing": {"residential": (30, 120),  "commercial": (150, 800),  "industrial": (400, 2000)},
    "parking":   {"residential": (5, 30),    "commercial": (50, 300),   "industrial": (30, 150)},
    "rentals":   {"residential": (40, 200),  "commercial": (200, 1200), "industrial": (500, 3000)},
    "other":     {"residential": (10, 80),   "commercial": (50, 400),   "industrial": (80, 600)},
}

# Weighted statuses: reflects COH's ~39.7% collection rate (Billings Jan-Sept: $5.06M vs Receipts: $2.01M)
# Source: 2024/2025 COH Consolidated Budget, Column E vs Column F
statuses_weighted = (
    [PaymentStatus.paid] * 8 +       # 40% collection rate
    [PaymentStatus.overdue] * 7 +    # large overdue book — primary leakage risk
    [PaymentStatus.pending] * 4 +    # billed but not yet due
    [PaymentStatus.disputed] * 2 +   # contested amounts
    [PaymentStatus.waived] * 1       # waivers — leakage risk
)

invoice_count = db.query(Invoice).count()
officer2 = db.query(User).filter(User.username == "r.officer2").first()
collectors = [officer1, officer2] if officer2 else [officer1]

if invoice_count < 10:
    for rp in ratepayers:
        ptype = rp.property_type or "residential"
        # Assign 3–6 invoices across different revenue categories
        for _ in range(random.randint(3, 6)):
            cat = random.choice(list(RevenueCategory))
            cat_str = cat if isinstance(cat, str) else cat.value
            band = CATEGORY_BANDS.get(cat_str, {}).get(ptype, (20, 300))
            amount = round(random.uniform(*band), 2)

            days_ago = random.randint(15, 365)
            issue_dt = now() - timedelta(days=days_ago)
            due_dt   = issue_dt + timedelta(days=30)
            status   = random.choice(statuses_weighted)

            if status == PaymentStatus.paid:
                paid = amount
            elif status == PaymentStatus.pending:
                paid = round(amount * random.uniform(0.1, 0.6), 2)
            else:
                paid = 0.0

            inv = Invoice(
                invoice_number=rnd_inv(), ratepayer_id=rp.id,
                category=cat, amount=amount, amount_paid=paid,
                balance=round(amount - paid, 2),
                issue_date=issue_dt, due_date=due_dt,
                status=status, anomaly_flag=AnomalyFlag.none,
                created_by=admin_user.id
            )
            db.add(inv)
            db.flush()

            if status == PaymentStatus.paid:
                collector = random.choice(collectors)
                pmt = Payment(
                    receipt_number=rnd_rcpt(), ratepayer_id=rp.id,
                    invoice_id=inv.id, amount=amount,
                    payment_method=random.choice(["cash","ecocash","bank_transfer","rtgs","zipit"]),
                    currency=random.choice(["USD","ZIG","ZIG"]),
                    payment_date=due_dt - timedelta(days=random.randint(0, 28)),
                    collected_by=collector.id,
                    is_reconciled=random.choice([True, True, True, False]),
                    anomaly_flag=AnomalyFlag.none
                )
                db.add(pmt)
            elif status == PaymentStatus.pending and paid > 0:
                # Partial payment — partially reconciled
                collector = random.choice(collectors)
                pmt = Payment(
                    receipt_number=rnd_rcpt(), ratepayer_id=rp.id,
                    invoice_id=inv.id, amount=paid,
                    payment_method="cash",
                    currency=random.choice(["USD","ZIG"]),
                    payment_date=now() - timedelta(days=random.randint(1, 20)),
                    collected_by=collector.id,
                    is_reconciled=False,
                    anomaly_flag=AnomalyFlag.none
                )
                db.add(pmt)

    # Add a few orphaned cash payments (no invoice) — key leakage scenario
    for rp in random.sample(ratepayers, min(6, len(ratepayers))):
        pmt = Payment(
            receipt_number=rnd_rcpt(), ratepayer_id=rp.id,
            invoice_id=None, amount=round(random.uniform(50, 400), 2),
            payment_method="cash", currency="USD",
            payment_date=now() - timedelta(days=random.randint(5, 90)),
            collected_by=officer1.id,
            is_reconciled=False,
            anomaly_flag=AnomalyFlag.medium,
            anomaly_reason="Cash payment received without invoice reference — unlinked to billing record"
        )
        db.add(pmt)

    db.commit()

# ── Expenditures ─────────────────────────────────────────────────────────────
# Source: City of Harare Consolidated Budget & Performance 2024/2025
# Amounts in USD converted from ZiG at 1 USD = 1,000 ZiG (2024 mid-year average rate).
# Line items map directly to the COH expenditure structure (Use of Goods & Services,
# Compensation of Employees, Capital by Programme) as reported to Parliament.

real_expenditures = [
    # (department, description, budget_line, amount_usd, approved)
    # ── Compensation of Employees (COH Budget row 55-61) ──
    ("Compensation of Employees", "Wages and salaries in cash — permanent and contract staff",      "BL-CEE-001", 392_739, True),
    ("Compensation of Employees", "Employee bonuses — performance and productivity awards",          "BL-CEE-002",  12_937, True),
    ("Compensation of Employees", "Staff allowances — housing, transport, medical, risk",           "BL-CEE-003", 707_691, True),
    ("Compensation of Employees", "NSSA and ZIMDEF employer statutory contributions",               "BL-CEE-004", 147_526, True),
    ("Compensation of Employees", "Monthly councillors sitting allowances",                         "BL-CEE-005",     249, True),

    # ── Use of Goods and Services — General (COH Budget row 65) ──
    ("Goods & Services — General", "Fuel, oil and lubricants — fleet and plant operations",        "BL-GS-001",  89_412, True),
    ("Goods & Services — General", "Chemicals and reagents — water treatment (Morton Jaffray)",    "BL-GS-002",  62_380, True),
    ("Goods & Services — General", "Electricity — pumping stations and council buildings",         "BL-GS-003",  47_290, True),
    ("Goods & Services — General", "Office supplies, printing and stationery",                     "BL-GS-004",  18_640, True),
    ("Goods & Services — General", "Communications — telephone, internet and postage",             "BL-GS-005",   9_870, True),
    ("Goods & Services — General", "Insurance — council fleet, plant and buildings",               "BL-GS-006",  24_100, True),
    ("Goods & Services — General", "Professional fees — legal, audit and consultancy",             "BL-GS-007",  38_750, False),
    ("Goods & Services — General", "Catering, cleaning and security services",                     "BL-GS-008",  19_420, True),
    ("Goods & Services — General", "Advertising and public announcements",                         "BL-GS-009",   6_300, True),
    ("Goods & Services — General", "Training and staff capacity building programmes",              "BL-GS-010",  12_800, True),

    # ── Use of Goods and Services — Repairs (COH Budget row 66) ──
    ("Goods & Services — Repairs", "Water reticulation pipe repairs — Mbare and Highfield",        "BL-RP-001",  18_920, True),
    ("Goods & Services — Repairs", "Sewer blockage clearing and pump repairs — Glen Norah",        "BL-RP-002",  14_300, True),
    ("Goods & Services — Repairs", "Road patching and pothole repairs — CBD and suburbs",          "BL-RP-003",  22_480, True),
    ("Goods & Services — Repairs", "Fleet vehicle mechanical repairs and tyre replacement",        "BL-RP-004",  31_600, True),
    ("Goods & Services — Repairs", "Streetlight and traffic signal repairs",                       "BL-RP-005",   8_140, False),
    ("Goods & Services — Repairs", "Council building structural repairs — Town House complex",     "BL-RP-006",  16_700, True),

    # ── Use of Goods and Services — Maintenance (COH Budget row 67) ──
    ("Goods & Services — Maintenance", "Water treatment plant preventive maintenance — Sanyati",   "BL-MT-001",  28_640, True),
    ("Goods & Services — Maintenance", "Reservoir and pump station servicing — Borrowdale",        "BL-MT-002",  19_800, True),
    ("Goods & Services — Maintenance", "Fleet preventive maintenance — refuse trucks and graders", "BL-MT-003",  24_350, True),
    ("Goods & Services — Maintenance", "Parks and open spaces — mowing, irrigation, planting",     "BL-MT-004",  11_900, True),
    ("Goods & Services — Maintenance", "Road drainage maintenance — storm drains and culverts",    "BL-MT-005",  16_420, False),
    ("Goods & Services — Maintenance", "ICT infrastructure — network and server maintenance",      "BL-MT-006",  12_000, True),

    # ── Consumption of Fixed Assets (COH Budget row 70) ──
    ("Asset Replacement Reserve", "Depreciation provision — water and sewerage infrastructure",    "BL-ARR-001",  5_820, True),
    ("Asset Replacement Reserve", "Depreciation provision — roads and transport assets",           "BL-ARR-002",  4_210, True),
    ("Asset Replacement Reserve", "Depreciation provision — buildings and plant",                  "BL-ARR-003",  2_960, True),

    # ── Interest Charges (COH Budget row 73) ──
    ("Interest & Loan Charges", "Interest on infrastructure development bonds — IDBZ",             "BL-IC-001",   None, True),  # no actual payment recorded
    ("Interest & Loan Charges", "Interest on ZimFund water project loan balance",                  "BL-IC-002",   None, False),

    # ── Capital — Water Infrastructure (COH Budget row 100) ──
    ("Capital — Water Infrastructure", "Morton Jaffray WTP upgrade — Phase 2 civil works",        "BL-CW-001", 18_947, True),
    ("Capital — Water Infrastructure", "Mabvuku-Tafara water network extension — Ward 22",         "BL-CW-002",  9_640, True),
    ("Capital — Water Infrastructure", "Sewer rehabilitation — Mbare trunk sewer Phase 3",        "BL-CW-003", 24_100, True),
    ("Capital — Water Infrastructure", "Smart water meter installation programme — 5,000 meters",  "BL-CW-004", 14_800, True),

    # ── Capital — Roads (COH Budget row 101) ──
    ("Capital — Roads & Transport", "Samora Machel Avenue resurfacing — Phase 1 (2.4km)",          "BL-CR-001", 51_732, True),
    ("Capital — Roads & Transport", "Kuwadzana Extension road rehabilitation",                      "BL-CR-002", 22_400, True),
    ("Capital — Roads & Transport", "CBD traffic light modernisation — 12 intersections",           "BL-CR-003", 18_900, False),

    # ── Capital — Health Facilities (COH Budget row 99) ──
    ("Capital — Health Facilities", "Budiriro Polyclinic renovation — consultation rooms",          "BL-CH-001",  4_549, True),
    ("Capital — Health Facilities", "Glenview Clinic equipment procurement — Ward 15",             "BL-CH-002",  3_100, True),

    # ── Capital — Education Facilities (COH Budget row 98) ──
    ("Capital — Education Facilities", "Mabvuku Primary School block construction — 6 classrooms", "BL-CE-001",     0, False),  # not yet paid
    ("Capital — Education Facilities", "Kuwadzana Library renovation and shelving",                 "BL-CE-002",     0, False),

    # ── Capital — Electricity (COH Budget row 103) ──
    ("Capital — Electricity Infrastructure", "CBD streetlight LED retrofit — 800 units",           "BL-CEL-001",    0, False),
    ("Capital — Electricity Infrastructure", "Southerton substation switchgear replacement",        "BL-CEL-002",    0, False),

    # ── Capital — Social Amenities (COH Budget row 102) ──
    ("Capital — Social Amenities", "Harare Gardens restoration and water features",                 "BL-CS-001",  1_686, True),
    ("Capital — Social Amenities", "Westgate Community Centre construction — Phase 1",             "BL-CS-002",     0, False),

    # ── Capital — Operational Assets (COH Budget row 104) ──
    ("Capital — Operational Assets", "Refuse compactor truck procurement — 3 units",               "BL-CO-001", 11_943, True),
    ("Capital — Operational Assets", "Water tankers for emergency supply — 5 units",               "BL-CO-002",     0, False),
    ("Capital — Operational Assets", "FMS and ERP system implementation — ICT upgrade",            "BL-CO-003",     0, False),
]

exp_count = db.query(Expenditure).count()
if exp_count < 5:
    for dept, desc, bl, amount, approved in real_expenditures:
        if amount is None or amount == 0:
            amount = 0.0
        e = Expenditure(
            reference_number="EXP-" + "".join(random.choices(string.digits, k=7)),
            department=dept, description=desc, amount=float(amount), budget_line=bl,
            expenditure_date=now() - timedelta(days=random.randint(1, 270)),
            approved_by=admin_user.id if approved and amount > 0 else None,
            is_approved=approved and amount > 0,
            anomaly_flag=AnomalyFlag.none
        )
        db.add(e)
    db.commit()

# ── Budgets ───────────────────────────────────────────────────────────────────
# Source: City of Harare Consolidated Budget & Performance 2024/2025
# Figures from columns: Original Budget (C) = allocated; Total Budget (I) = actual spent
# Converted from ZiG at 1 USD = 1,000 ZiG (2024 mid-year average rate, RBZ).
# The "allocated" column uses the Original/Prior Year budget;
# "spent" uses the Total Budget (Own Revenue + Grants & Others) as actual expenditure.
# Over-budget items reflect mid-year supplementary budgets driven by inflation adjustments.

real_budgets = [
    # (department, category, fiscal_year, allocated_usd, spent_usd)
    # Current Expenditure
    ("Compensation of Employees — Wages & Salaries", "Current Expenditure", "2024/2025",  625_844, 1_039_342),
    ("Compensation of Employees — Bonuses",           "Current Expenditure", "2024/2025",   46_854,    92_916),
    ("Compensation of Employees — Allowances",        "Current Expenditure", "2024/2025", 1_450_754, 2_579_518),
    ("Compensation of Employees — Employer Contributions", "Current Expenditure", "2024/2025", 251_507, 409_852),
    ("Compensation of Employees — Councillors Allowances", "Current Expenditure", "2024/2025", 158_002,   725),
    ("Goods & Services — General Use",                "Current Expenditure", "2024/2025", 2_259_590, 3_621_328),
    ("Goods & Services — Repairs",                    "Current Expenditure", "2024/2025",   235_949,   562_881),
    ("Goods & Services — Maintenance",                "Current Expenditure", "2024/2025",   757_032, 1_626_152),
    ("Consumption of Fixed Assets",                   "Current Expenditure", "2024/2025",    45_178,   246_279),
    ("Interest on Loans",                             "Current Expenditure", "2024/2025",   159_146,   294_005),
    ("Transfer Expenses — Current",                   "Current Expenditure", "2024/2025",    45_190,     1_925),
    ("Grants & Donation Expenses",                    "Current Expenditure", "2024/2025",     2_712,     5_099),
    # Capital Expenditure — By Programme
    ("Capital — Educational Facilities",              "Capital Expenditure", "2024/2025",    26_663,    32_030),
    ("Capital — Health Facilities",                   "Capital Expenditure", "2024/2025",    32_277,   107_079),
    ("Capital — Water Infrastructure",                "Capital Expenditure", "2024/2025",   594_793, 1_181_175),
    ("Capital — Roads & Transport",                   "Capital Expenditure", "2024/2025",   277_470,   601_939),
    ("Capital — Social Amenities",                    "Capital Expenditure", "2024/2025",     9_657, 1_020_420),
    ("Capital — Electricity Infrastructure",          "Capital Expenditure", "2024/2025",    59_088,    50_432),
    ("Capital — Operational Assets",                  "Capital Expenditure", "2024/2025",   808_343, 1_480_949),
]

bgt_count = db.query(Budget).count()
if bgt_count < 5:
    for dept, cat, fy, allocated, spent in real_budgets:
        b = Budget(
            fiscal_year=fy, department=dept, category=cat,
            allocated_amount=allocated, spent_amount=spent,
            remaining=round(allocated - spent, 2)
        )
        db.add(b)
    db.commit()

# ── Revenue Targets ───────────────────────────────────────────────────────────
# Source: City of Harare Consolidated Budget & Performance 2024/2025
# Target = Original Budget column (C); Own Revenue actual (G) shown for comparison.
# Converted from ZiG at 1 USD = 1,000 ZiG.
# The large gap between targets and own-revenue actuals is the core leakage narrative:
#   Total billed (Jan-Sept): 5,064,928 USD
#   Total collected (Jan-Sept): 2,008,892 USD
#   Collection rate: 39.7% — consistent with COH's documented revenue leakage problem.
real_targets = [
    # (category, target_usd, actual_own_revenue_usd, period, notes)
    ("rates",
     3_461_095, 5_342_149, "annual",
     "Assessment Rates (Taxes on Property) — residential, commercial, industrial. "
     "Original budget ZiG 3,461,095,267; Own Revenue actual ZiG 5,342,148,810 (revalued mid-year)."),

    ("water",
     584_168, 1_120_838, "annual",
     "Water service charges — metered billing (domestic and commercial). "
     "Component of COH Service Charges budget line ZiG 1,947,228,096."),

    ("sewerage",
     292_084, 560_419, "annual",
     "Sewerage treatment and reticulation charges — based on water consumption volume. "
     "Component of COH Service Charges; actual collection severely impacted by meter gaps."),

    ("refuse",
     292_084, 374_916, "annual",
     "Solid waste / refuse removal charges — domestic and commercial properties. "
     "Ward-level collection gaps identified as major leakage point (ACFE, 2022)."),

    ("licensing",
     134_457,  260_874, "annual",
     "Business licences, liquor licences, vendor permits, hawker fees. "
     "COH Budget line: Licences and Permits ZiG 134,456,863 original."),

    ("parking",
      48_144,   91_782, "annual",
     "On-street parking, car park revenue, clamping and release fees — CBD. "
     "COH Budget: Other Revenue ZiG 48,143,680 original (under-reported category)."),

    ("rentals",
     421_183,  738_560, "annual",
     "Council property rentals (Estates + Rentals): commercial lettings, market stalls, "
     "housing estates. COH: Rentals ZiG 177,929,236 + Estates ZiG 243,254,419."),

    ("other",
     1_077_904, 1_796_748, "annual",
     "Administrative fees, fines, penalties and forfeits, IGP income, parks and wildlife revenue, "
     "incidental sales. COH Budget: Admin Fees ZiG 1,077,903,948 + Fines ZiG 109,978,202."),
]

tgt_count = db.query(RevenueTarget).count()
if tgt_count < 3:
    budget_officer = db.query(User).filter(User.username == "budget1").first()
    for cat, target, actual, period, notes in real_targets:
        rt = RevenueTarget(
            fiscal_year="2024/2025", category=cat,
            target_amount=target, period=period, notes=notes,
            created_by=budget_officer.id if budget_officer else admin_user.id
        )
        db.add(rt)
    db.commit()

# ── Leakage Alerts ─────────────────────────────────────────────
alert_count = db.query(LeakageAlert).count()
if alert_count < 3:
    alerts = [
        ("unreconciled_cash", "high",
         "47 cash payments totalling $12,450 from Ward 7 collection drives remain unreconciled >30 days. "
         "Cash with no audit trail is the primary leakage vector (ACFE, 2022).", "payments"),
        ("duplicate_billing", "medium",
         "3 ratepayers in Mbare detected with duplicate invoices for the same billing period in Water category. "
         "Manual billing process gap — accounts: COH-102441, COH-107832, COH-119004.", "invoices"),
        ("waiver_no_audit", "high",
         "Unusual spike in penalty waivers — 18 waiver approvals in 7 days (vs. 2/week average). "
         "No senior officer approval recorded in audit log. Possible authorisation bypass.", "invoices"),
        ("ghost_account", "medium",
         "Ward 22 field survey (Sept 2023) identified 14 registered ratepayer accounts with no physical "
         "property correspondence — potential ghost accounts inflating the debtor book.", "ratepayers"),
        ("stale_overdue", "medium",
         "112 accounts overdue >180 days with combined balance of $284,500. "
         "NCC (2023): accounts overdue >180 days have <25% recovery probability without legal action.", "invoices"),
        ("officer_gap", "medium",
         "Revenue officer James Moyo (r.officer2) collection rate of 34% is significantly below "
         "team average of 67%. Z-score analysis flags this as a statistically significant gap.", "users"),
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

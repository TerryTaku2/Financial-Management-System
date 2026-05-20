#!/usr/bin/env python3
"""
City of Harare FMS — Comprehensive Demo Data Seeder
Inserts realistic data from 2021 to 2026 covering all modules.
Run from the backend directory: python seed_data.py
"""

import sqlite3
import bcrypt
import random
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "fms_harare.db"
random.seed(42)

# ─── helpers ────────────────────────────────────────────────────────────────

def hp(pwd):
    return bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode()

def ts(year, month, day, hour=9, minute=0):
    return f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:00"

def quarter_start_month(q):
    return {1: 1, 2: 4, 3: 7, 4: 10}[q]

NOW = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ─── main ───────────────────────────────────────────────────────────────────

def run():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("PRAGMA journal_mode = WAL")
    cur = conn.cursor()

    print("🧹  Clearing existing data …")
    for tbl in [
        "audit_logs", "leakage_alerts", "system_notifications",
        "payment_plans", "payments", "invoices", "expenditures",
        "budget_sections", "budgets", "revenue_targets",
        "billing_runs", "billing_rates", "exchange_rates",
        "login_attempts", "ratepayers", "users",
    ]:
        cur.execute(f"DELETE FROM {tbl}")
    try:
        cur.execute("DELETE FROM sqlite_sequence WHERE 1=1")
    except sqlite3.OperationalError:
        pass  # Table doesn't exist yet

    conn.execute("PRAGMA foreign_keys = ON")

    # ═══════════════════════════════════════════════════════════════
    # USERS
    # ═══════════════════════════════════════════════════════════════
    print("👤  Creating 8 users …")
    USERS = [
        (1, "admin",    "Tendai Murwira",    "admin@harare.gov.zw",         hp("Admin@2025!"),    "admin"),
        (2, "jmoyo",    "Joseph Moyo",       "j.moyo@harare.gov.zw",        hp("Revenue@2025!"),  "revenue_officer"),
        (3, "pchimba",  "Patricia Chimba",   "p.chimba@harare.gov.zw",      hp("Revenue@2025!"),  "revenue_officer"),
        (4, "rndebele", "Rudo Ndebele",      "r.ndebele@harare.gov.zw",     hp("Revenue@2025!"),  "revenue_officer"),
        (5, "snyoni",   "Sekai Nyoni",       "s.nyoni@harare.gov.zw",       hp("Revenue@2025!"),  "revenue_officer"),
        (6, "kmutasa",  "Knowledge Mutasa",  "k.mutasa@harare.gov.zw",      hp("Audit@2025!"),    "auditor"),
        (7, "btshuma",  "Blessing Tshuma",   "b.tshuma@harare.gov.zw",      hp("Account@2025!"),  "accountant"),
        (8, "fgumbo",   "Farai Gumbo",       "f.gumbo@harare.gov.zw",       hp("Budget@2025!"),   "budget_officer"),
    ]
    cur.executemany(
        "INSERT INTO users (id, username, full_name, email, hashed_password, role, is_active, created_at, failed_login_count) "
        "VALUES (?,?,?,?,?,?,1,?,0)",
        [(u[0], u[1], u[2], u[3], u[4], u[5], NOW) for u in USERS],
    )

    # ═══════════════════════════════════════════════════════════════
    # EXCHANGE RATES
    # ═══════════════════════════════════════════════════════════════
    print("💱  Setting exchange rates …")
    cur.executemany(
        "INSERT INTO exchange_rates (currency, rate_to_usd, source, manual, updated_at) VALUES (?,?,?,?,?)",
        [
            ("USD", 1.0,   "System — base currency",         1, NOW),
            ("ZWG", 13.56, "Reserve Bank of Zimbabwe (RBZ)", 0, NOW),
        ],
    )

    # ═══════════════════════════════════════════════════════════════
    # BILLING RATES
    # ═══════════════════════════════════════════════════════════════
    print("💰  Setting billing rates …")
    BILLING_RATES = [
        ("rates",     85.00,  "Property rates — residential (quarterly base)"),
        ("water",     65.00,  "Water supply (quarterly base)"),
        ("sewerage",  45.00,  "Sewerage services (quarterly base)"),
        ("refuse",    30.00,  "Refuse collection (quarterly base)"),
        ("licensing", 150.00, "Business / trade licence (annual)"),
        ("parking",   25.00,  "Parking permit (quarterly)"),
        ("rentals",   120.00, "Council property rental (monthly base)"),
        ("other",     20.00,  "Miscellaneous council services"),
    ]
    for cat, amt, desc in BILLING_RATES:
        cur.execute(
            "INSERT INTO billing_rates (category, flat_amount, description, is_active, updated_at) VALUES (?,?,?,1,?)",
            (cat, amt, desc, NOW),
        )

    # ═══════════════════════════════════════════════════════════════
    # RATEPAYERS
    # ═══════════════════════════════════════════════════════════════
    print("🏘️   Creating 85 ratepayers …")

    RESIDENTIAL = [
        ("Chiedza Mawere",       "Mbare",        "45 Seke Rd",             "Ward 8"),
        ("Tarisai Dube",         "Highfield",     "12 Budiriro Rd",         "Ward 14"),
        ("Fungai Munyaradzi",    "Glen Norah",    "78 Glen Norah Rd",       "Ward 22"),
        ("Nyasha Gomo",          "Kuwadzana",     "3 Kuwadzana Ext",        "Ward 35"),
        ("Blessing Ncube",       "Mabvuku",       "90 Mabvuku Dr",          "Ward 31"),
        ("Ruvimbo Chigumbu",     "Chitungwiza",   "22 Unit A, Chitungwiza", "Ward 38"),
        ("Tinashe Phiri",        "Dzivarasekwa",  "55 Dzivarasekwa Rd",     "Ward 36"),
        ("Mavis Makoni",         "Highfield",     "17 Machipisa St",        "Ward 15"),
        ("Kelvin Muradzikwa",    "Mabvuku",       "8 Rujeko Dr",            "Ward 31"),
        ("Sekai Mutoko",         "Glen Norah",    "33 Glen Norah Ext",      "Ward 23"),
        ("Tendai Mugabe",        "Mbare",         "11 Mbare Flats",         "Ward 8"),
        ("Farai Zvenyika",       "Kuwadzana",     "20 Kuwadzana Rd",        "Ward 34"),
        ("Simba Mhaka",          "Highfield",     "66 Highfield Rd",        "Ward 14"),
        ("Pamela Chisango",      "Chitungwiza",   "14 Unit D, Chitungwiza", "Ward 38"),
        ("Godwin Nyamande",      "Dzivarasekwa",  "29 Dzivarasekwa Ext",    "Ward 36"),
        ("Loveness Chikwanda",   "Glen Norah",    "44 Glen Norah A",        "Ward 22"),
        ("Patson Muroti",        "Mabvuku",       "7 Tafara Rd",            "Ward 31"),
        ("Constance Zimuto",     "Highfield",     "101 Highfield Ave",      "Ward 15"),
        ("Obadiah Tembo",        "Mbare",         "5 Matapi Flats",         "Ward 7"),
        ("Grace Mukota",         "Kuwadzana",     "38 Phase 3, Kuwadzana",  "Ward 35"),
        ("Rufaro Mandevere",     "Chitungwiza",   "55 Unit L, Chitungwiza", "Ward 38"),
        ("Chipo Gundidza",       "Glen Norah",    "19 Glen Norah B",        "Ward 23"),
        ("Tafadzwa Mapuranga",   "Highfield",     "77 Glenview Ave",        "Ward 16"),
        ("Rutendo Tsimba",       "Mbare",         "62 Stodart Rd",          "Ward 9"),
        ("Moses Gonese",         "Mabvuku",       "14 Mabvuku Rd",          "Ward 30"),
        ("Agnes Murehwa",        "Dzivarasekwa",  "31 Dzivarasekwa Rd",     "Ward 36"),
        ("Herbert Sigauke",      "Kuwadzana",     "50 Kuwadzana Ext 1",     "Ward 33"),
        ("Dorothy Zvenyika",     "Highfield",     "25 Highfield Rd",        "Ward 14"),
        ("Elias Chitongo",       "Glen Norah",    "88 Glen Norah Rd",       "Ward 22"),
        ("Rachel Makamba",       "Chitungwiza",   "41 Unit B, Chitungwiza", "Ward 38"),
        ("Tatenda Tshabalala",   "Mbare",         "3 Mbare Musika Rd",      "Ward 8"),
        ("Faith Mupamhanga",     "Highfield",     "92 Warren Park Rd",      "Ward 16"),
        ("Solomon Nyamukapa",    "Mabvuku",       "19 Tafara Ext",          "Ward 30"),
        ("Stella Machakaire",    "Kuwadzana",     "66 Kuwadzana Phase 2",   "Ward 34"),
        ("Victor Nyamande",      "Dzivarasekwa",  "8 Dzivarasekwa Rd",      "Ward 36"),
        ("Melody Mazarura",      "Glen Norah",    "37 Glen Norah C",        "Ward 23"),
        ("Wellington Mutasa",    "Highfield",     "54 Glenview Rd",         "Ward 16"),
        ("Chido Chitiyo",        "Mbare",         "28 Ruwadzano Rd",        "Ward 7"),
        ("Everisto Moyo",        "Chitungwiza",   "63 Unit F, Chitungwiza", "Ward 38"),
        ("Lindiwe Moyo",         "Mabvuku",       "44 Mabvuku Ext",         "Ward 31"),
        ("Ronald Jeke",          "Kuwadzana",     "12 Kuwadzana Phase 3",   "Ward 35"),
        ("Kudakwashe Mhaka",     "Glen Norah",    "71 Glen Norah D",        "Ward 22"),
        ("Tariro Chikwanda",     "Highfield",     "33 Machipisa Rd",        "Ward 15"),
        ("Innocent Chinembiri",  "Mbare",         "17 Mbare Rd",            "Ward 9"),
        ("Alice Chigumbu",       "Dzivarasekwa",  "46 Dzivarasekwa Ext",    "Ward 36"),
        ("Charles Dube",         "Mabvuku",       "28 Tafara Rd",           "Ward 30"),
        ("Dadirai Chitiyo",      "Chitungwiza",   "80 Unit C, Chitungwiza", "Ward 38"),
        ("Emmanuel Mutimba",     "Highfield",     "15 Highfield Rd",        "Ward 14"),
        ("Felicity Nyoni",       "Glen Norah",    "52 Glen Norah Rd",       "Ward 22"),
        ("Patrick Sibanda",      "Kuwadzana",     "9 Kuwadzana Phase 1",    "Ward 33"),
    ]

    COMMERCIAL = [
        ("Harare CBD Supermarket (Pvt) Ltd",    "CBD",          "1 Jason Moyo Ave",         "Ward 2"),
        ("Avondale Trading Co. (Pvt) Ltd",      "Avondale",     "45 King George Rd",        "Ward 4"),
        ("Borrowdale Business Park Ltd",         "Borrowdale",   "200 Borrowdale Rd",        "Ward 6"),
        ("OK Zimbabwe — Highfield Branch",       "Highfield",    "91 Machipisa St",          "Ward 14"),
        ("Delta Beverages (Harare Depot)",       "Southerton",   "12 Simon Muzenda St",      "Ward 2"),
        ("Econet Wireless Zimbabwe HQ",          "CBD",          "First Mutual Tower",       "Ward 2"),
        ("First Capital Bank Ltd",               "CBD",          "100 First St",             "Ward 2"),
        ("CABS Building Society",                "CBD",          "45 Jason Moyo Ave",        "Ward 2"),
        ("Steward Bank — Borrowdale Branch",     "Borrowdale",   "Borrowdale Brooke Mall",   "Ward 6"),
        ("Chicken Slice Restaurants (Pvt) Ltd",  "CBD",          "78 Samora Machel Ave",     "Ward 2"),
        ("Spar Zimbabwe — Avondale",             "Avondale",     "Avondale Shopping Centre", "Ward 4"),
        ("Game Stores Zimbabwe Ltd",             "CBD",          "102 Speke Ave",            "Ward 2"),
        ("National Bakeries (Pvt) Ltd",          "Graniteside",  "56 Seke Rd, Graniteside",  "Ward 3"),
        ("Tanganda Tea Company Ltd",             "Eastlea",      "3 Harrow Rd",              "Ward 5"),
        ("Willowvale Mazda Motor Industries",    "Willowvale",   "8 Willowvale Rd",          "Ward 3"),
        ("ZB Financial Holdings Ltd",            "CBD",          "ZB Centre, 1st St",        "Ward 2"),
        ("Phoenix Zimbabwe (Pvt) Ltd",           "Msasa",        "14 Msasa Industrial Rd",   "Ward 3"),
        ("Lyons Zimbabwe (Pvt) Ltd",             "Workington",   "29 Simon Muzenda St",      "Ward 3"),
        ("TM Supermarkets — Mbare Branch",       "Mbare",        "Mbare Musika Market",      "Ward 8"),
        ("Blue Ribbon Industries Ltd",           "Southerton",   "77 Cripps Rd",             "Ward 3"),
        ("Greatermans (Pvt) Ltd",                "CBD",          "42 Robert Mugabe Rd",      "Ward 2"),
        ("NetOne Cellco (Pvt) Ltd",              "CBD",          "NetOne Centre, Samora",    "Ward 2"),
        ("Edgars Stores Zimbabwe Ltd",           "CBD",          "Edgars House, Speke Ave",  "Ward 2"),
        ("Schweppes Zimbabwe Ltd",               "Willowvale",   "Schweppes Way, Willowvale","Ward 3"),
        ("Globe and Phoenix Industries",         "Graniteside",  "Globe Pk, Graniteside Rd", "Ward 3"),
    ]

    INDUSTRIAL = [
        ("Metal Fabricators of Zimbabwe (MEFALZ)", "Southerton",  "Cripps Rd, Southerton",     "Ward 3"),
        ("Zimbabwe Steel Company Ltd",             "Msasa",       "Msasa Industrial Park",     "Ward 3"),
        ("National Blankets Ltd",                  "Workington",  "Simon Muzenda St, Workington","Ward 3"),
        ("Cone Textiles (Pvt) Ltd",                "Southerton",  "45 Cripps Rd",              "Ward 3"),
        ("Harare Industrial Park Holdings",        "Graniteside", "Graniteside Industrial Pk", "Ward 3"),
        ("Zimbabwe Fertilizer Company",            "Msasa",       "Fertilizer Way, Msasa",     "Ward 3"),
        ("National Foods Ltd",                     "Workington",  "National Foods Rd",         "Ward 3"),
        ("Anchor Yeast Zimbabwe (Pvt) Ltd",        "Southerton",  "Cripps Rd, Workington",     "Ward 3"),
        ("Irvine's Zimbabwe (Pvt) Ltd",            "Msasa",       "Irvine's Way, Msasa",       "Ward 3"),
        ("Grain Marketing Board — Harare",         "Graniteside", "GMB Depot, Graniteside",    "Ward 3"),
    ]

    rp_rows = []
    rp_id = 1
    rp_meta = []  # (id, property_type, categories)

    RES_CATS  = ["rates", "water", "sewerage", "refuse"]
    COM_CATS  = ["rates", "water", "sewerage", "refuse", "licensing", "parking"]
    IND_CATS  = ["rates", "water", "sewerage", "refuse", "licensing"]

    for name, zone, addr, ward in RESIDENTIAL:
        acc = f"HAR-RES-{rp_id:05d}"
        rp_rows.append((
            rp_id, acc, name, f"{addr}, {zone}", ward, zone,
            f"+263 77{random.randint(1000000,9999999)}",
            f"{name.split()[0].lower()}{rp_id}@gmail.com",
            "residential", 1, NOW,
            round(random.uniform(0.1, 0.75), 2),
            "medium" if random.random() > 0.55 else "low", NOW,
        ))
        rp_meta.append((rp_id, "residential", RES_CATS))
        rp_id += 1

    for name, zone, addr, ward in COMMERCIAL:
        acc = f"HAR-COM-{rp_id:05d}"
        rp_rows.append((
            rp_id, acc, name, f"{addr}", ward, zone,
            f"+263 24{random.randint(100000,999999)}",
            f"accounts@{name.replace(' ','').replace('(','').replace(')','').lower()[:12]}.co.zw",
            "commercial", 1, NOW,
            round(random.uniform(0.0, 0.4), 2),
            "low" if random.random() > 0.35 else "medium", NOW,
        ))
        rp_meta.append((rp_id, "commercial", COM_CATS))
        rp_id += 1

    for name, zone, addr, ward in INDUSTRIAL:
        acc = f"HAR-IND-{rp_id:05d}"
        rp_rows.append((
            rp_id, acc, name, f"{addr}", ward, zone,
            f"+263 24{random.randint(100000,999999)}",
            f"finance@{name.replace(' ','').lower()[:12]}.co.zw",
            "industrial", 1, NOW,
            round(random.uniform(0.0, 0.25), 2),
            "low", NOW,
        ))
        rp_meta.append((rp_id, "industrial", IND_CATS))
        rp_id += 1

    cur.executemany(
        "INSERT INTO ratepayers "
        "(id, account_number, full_name, address, ward, zone, phone, email, "
        " property_type, is_active, created_at, risk_score, risk_label, risk_updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        rp_rows,
    )
    n_rp = len(rp_rows)
    print(f"   {n_rp} ratepayers created")

    # ═══════════════════════════════════════════════════════════════
    # REVENUE TARGETS
    # ═══════════════════════════════════════════════════════════════
    print("🎯  Setting revenue targets (2021–2026) …")
    TARGETS = {
        "2021/2022": {"rates":323000, "water":299000, "sewerage":131000, "refuse":87000, "licensing":50000,  "parking":19000, "rentals":25000, "other":12000},
        "2022/2023": {"rates":458000, "water":417000, "sewerage":189000, "refuse":121000, "licensing":67000, "parking":27000, "rentals":34000, "other":20000},
        "2023/2024": {"rates":551000, "water":498000, "sewerage":223000, "refuse":144000, "licensing":85000, "parking":33000, "rentals":39000, "other":26000},
        "2024/2025": {"rates":653000, "water":602000, "sewerage":269000, "refuse":173000, "licensing":102000, "parking":45000, "rentals":51000, "other":32000},
        "2025/2026": {"rates":738000, "water":683000, "sewerage":305000, "refuse":195000, "licensing":122000, "parking":55000, "rentals":61000, "other":37000},
    }
    tgt_rows = []
    for fy, cats in TARGETS.items():
        for cat, amt in cats.items():
            tgt_rows.append((fy, cat, amt, "annual", f"COH approved target — {cat}, FY {fy}", NOW, 1))
    cur.executemany(
        "INSERT INTO revenue_targets (fiscal_year, category, target_amount, period, notes, created_at, created_by) "
        "VALUES (?,?,?,?,?,?,?)",
        tgt_rows,
    )
    print(f"   {len(tgt_rows)} revenue targets set")

    # ═══════════════════════════════════════════════════════════════
    # BUDGETS (2021–2026)
    # ═══════════════════════════════════════════════════════════════
    print("🏛️   Creating departmental budgets …")

    DEPT_BUDGETS = [
        # (department, {year: total_allocated})
        ("Town Clerk Department",
         {2021:1800000, 2022:2100000, 2023:2400000, 2024:2800000, 2025:3200000, 2026:3600000}),
        ("Chamber Secretary",
         {2021:1200000, 2022:1400000, 2023:1600000, 2024:1900000, 2025:2200000, 2026:2500000}),
        ("Harare Water Department",
         {2021:15000000,2022:18000000,2023:21000000,2024:25000000,2025:29000000,2026:32000000}),
        ("City Health Department",
         {2021:8000000, 2022:9500000, 2023:11000000,2024:13000000,2025:15000000,2026:17000000}),
        ("Department of Housing and Community Service",
         {2021:5000000, 2022:6000000, 2023:7000000, 2024:8500000, 2025:10000000,2026:11500000}),
        ("Department of Works",
         {2021:9500000, 2022:11000000,2023:13000000,2024:16000000,2025:19000000,2026:21500000}),
        ("Human Capital and Public Services Department",
         {2021:12000000,2022:14000000,2023:16500000,2024:19000000,2025:22000000,2026:25000000}),
        ("Urban Planning Department",
         {2021:2500000, 2022:3000000, 2023:3500000, 2024:4200000, 2025:5000000, 2026:5800000}),
        ("Finance Department",
         {2021:3500000, 2022:4200000, 2023:5000000, 2024:6000000, 2025:7000000, 2026:8000000}),
    ]

    UTIL = {2021:0.78, 2022:0.82, 2023:0.86, 2024:0.89, 2025:0.91, 2026:0.38}  # 2026 partial
    BUD_CATS    = ["Personnel", "Operational", "Capital"]
    BUD_SPLITS  = [0.45,        0.30,          0.25]

    bud_rows = []
    bid = 1
    for dept, yr_map in DEPT_BUDGETS:
        for year, total in yr_map.items():
            fy = f"{year}/{year+1}"
            util = UTIL[year]
            for cat, split in zip(BUD_CATS, BUD_SPLITS):
                alloc = round(total * split)
                spent = round(alloc * util * random.uniform(0.94, 1.06))
                remaining = alloc - spent
                bud_rows.append((bid, fy, dept, cat, alloc, spent, remaining, NOW))
                bid += 1
    cur.executemany(
        "INSERT INTO budgets (id, fiscal_year, department, category, allocated_amount, spent_amount, remaining, created_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        bud_rows,
    )
    print(f"   {len(bud_rows)} budget lines created")

    # ═══════════════════════════════════════════════════════════════
    # INVOICES + PAYMENTS
    # ═══════════════════════════════════════════════════════════════
    print("🧾  Generating invoices & payments 2021–2026 …")

    # Quarterly amount ranges (USD) per property type per category
    QAR = {
        "residential": {
            "rates":    (180, 480),
            "water":    (85,  230),
            "sewerage": (55,  145),
            "refuse":   (35,   90),
        },
        "commercial": {
            "rates":    (800,  3500),
            "water":    (400,  1400),
            "sewerage": (200,   700),
            "refuse":   (140,   420),
            "licensing":(300,  1800),
            "parking":  (100,   450),
        },
        "industrial": {
            "rates":    (2000,  9000),
            "water":    (1500,  7000),
            "sewerage": (800,   3500),
            "refuse":   (400,   1800),
            "licensing":(500,   2500),
        },
    }

    # Annual collection-rate by year (increased to realistic 45-70% range for credible reporting)
    COLL = {2021: 0.48, 2022: 0.55, 2023: 0.62, 2024: 0.68, 2025: 0.72, 2026: 0.75}

    OFFICERS = [2, 3, 4, 5]

    # Billing periods: Q1-Q4 2021..2025, Q1-Q2 2026
    QUARTERS = [(y, q) for y in range(2021, 2026) for q in range(1, 5)]
    QUARTERS += [(2026, 1), (2026, 2)]

    inv_rows = []
    pmt_rows = []
    inv_id = 1
    pmt_id = 1
    TODAY = datetime(2026, 5, 20)

    for rp_id, ptype, cats in rp_meta:
        officer = random.choice(OFFICERS)
        bias    = random.uniform(-0.05, 0.15)  # Increased upper bound: more reliable payers

        for (year, q) in QUARTERS:
            mo = quarter_start_month(q)
            issue_day = random.randint(1, 6)
            issue_dt  = ts(year, mo, issue_day, random.randint(8, 16), random.randint(0, 55))

            due_mo = mo + 2
            due_yr = year
            if due_mo > 12:
                due_mo -= 12
                due_yr += 1
            due_dt = ts(due_yr, due_mo, 25, 17, 0)

            for cat in cats:
                lo, hi = QAR[ptype][cat]
                growth  = 1.0 + (year - 2021) * 0.095 + random.uniform(-0.04, 0.07)
                amount  = round(random.uniform(lo, hi) * growth, 2)

                coll_prob = min(0.96, max(0.15, COLL[year] + bias))  # Ensure min 15% collection
                paid      = random.random() < coll_prob

                due_date_obj = datetime(due_yr, due_mo, 25)
                if paid:
                    status      = "paid"
                    amount_paid = amount
                    balance     = 0.0
                elif due_date_obj < TODAY:
                    status      = "overdue"
                    amount_paid = 0.0
                    balance     = amount
                else:
                    status      = "pending"
                    amount_paid = 0.0
                    balance     = amount

                inv_num = f"INV-{year}Q{q}-{inv_id:06d}"
                inv_rows.append((
                    inv_id, inv_num, rp_id, cat,
                    amount, amount_paid, balance,
                    issue_dt, due_dt, status,
                    "none", None, f"Quarterly {cat} charge — {year} Q{q}",
                    officer, None,
                ))

                if paid:
                    pay_mo = mo + random.randint(0, 3)
                    pay_yr = year
                    while pay_mo > 12:
                        pay_mo -= 12
                        pay_yr += 1
                    pay_yr = min(pay_yr, 2026)
                    pay_mo = min(pay_mo, 5 if pay_yr == 2026 else 12)
                    pay_dt = ts(pay_yr, pay_mo, random.randint(1, 28),
                                random.randint(7, 17), random.randint(0, 59))
                    method = random.choices(
                        ["cash", "ecocash", "bank_transfer", "zipit", "cheque"],
                        weights=[0.22, 0.38, 0.25, 0.10, 0.05],
                    )[0]
                    receipt = f"RCP-{year}Q{q}-{pmt_id:06d}"
                    pmt_rows.append((
                        pmt_id, receipt, rp_id, inv_id, amount,
                        method, "USD", pay_dt, officer,
                        1, officer, pay_dt,
                        "none", None,
                        f"Payment for {inv_num} via {method}", None,
                    ))
                    pmt_id += 1

                inv_id += 1

    print(f"   Inserting {len(inv_rows):,} invoices …")
    conn.executemany(
        "INSERT INTO invoices "
        "(id, invoice_number, ratepayer_id, category, amount, amount_paid, balance, "
        " issue_date, due_date, status, anomaly_flag, anomaly_reason, notes, created_by, fingerprint) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        inv_rows,
    )

    print(f"   Inserting {len(pmt_rows):,} payments …")
    conn.executemany(
        "INSERT INTO payments "
        "(id, receipt_number, ratepayer_id, invoice_id, amount, payment_method, currency, "
        " payment_date, collected_by, is_reconciled, reconciled_by, reconciled_at, "
        " anomaly_flag, anomaly_reason, notes, idempotency_key) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        pmt_rows,
    )

    # ═══════════════════════════════════════════════════════════════
    # EXPENDITURES
    # ═══════════════════════════════════════════════════════════════
    print("💸  Generating expenditure records …")

    DEPT_SPEND = {
        "Town Clerk Department":                              (110000, 220000),
        "Chamber Secretary":                                  (75000,  140000),
        "Harare Water Department":                            (900000, 2000000),
        "City Health Department":                             (480000, 950000),
        "Department of Housing and Community Service":        (320000, 680000),
        "Department of Works":                                (680000, 1400000),
        "Human Capital and Public Services Department":       (780000, 1600000),
        "Urban Planning Department":                          (140000, 300000),
        "Finance Department":                                 (210000, 420000),
    }

    BUDGET_LINES = {
        "Town Clerk Department":         ["Administration & Governance", "Legal Services", "Communications & PR", "Council Secretariat", "Executive Services"],
        "Chamber Secretary":             ["Secretarial Services", "Records & Archives", "Compliance & Regulatory", "Committee Services"],
        "Harare Water Department":       ["Water Treatment Chemicals", "Pipeline Maintenance", "Pump Station Operations", "Meter Reading Services", "Water Infrastructure Capital", "Emergency Repairs"],
        "City Health Department":        ["Medical Supplies & Drugs", "Clinic Operations", "Vector Control (Spraying)", "Mortuary Services", "Ambulance Services", "Refuse Disposal"],
        "Department of Housing and Community Service": ["Housing Maintenance", "Community Hall Operations", "Social Welfare Programs", "Rental Property Upkeep"],
        "Department of Works":           ["Road Rehabilitation", "Street Lighting", "Equipment & Plant Maintenance", "Construction Materials", "Capital Projects"],
        "Human Capital and Public Services Department": ["Staff Salaries", "Training & Development", "Pension Contributions", "Medical Aid", "Staff Transport"],
        "Urban Planning Department":     ["Planning & Surveys", "GIS Systems", "Zoning Administration", "Development Control"],
        "Finance Department":            ["Revenue Collection Operations", "Financial Information Systems", "Internal Audit", "Treasury Operations", "Debt Collection"],
    }

    exp_rows = []
    exp_id   = 1

    for year in range(2021, 2027):
        month_range = range(1, 13) if year < 2026 else range(1, 5)
        growth = 1.0 + (year - 2021) * 0.10

        for month in month_range:
            for dept, (lo, hi) in DEPT_SPEND.items():
                total_budget = random.uniform(lo, hi) * growth
                n_items = random.randint(2, 5)
                lines   = BUDGET_LINES[dept]
                total_used = 0.0

                for i in range(n_items):
                    if i == n_items - 1:
                        amt = round(total_budget - total_used, 2)
                        if amt < 500:
                            amt = round(random.uniform(500, 5000), 2)
                    else:
                        frac = random.uniform(0.12, 0.40)
                        amt  = round(total_budget * frac, 2)
                        total_used += amt

                    line    = random.choice(lines)
                    day     = random.randint(1, 28)
                    exp_dt  = ts(year, month, day, random.randint(7, 17), random.randint(0, 55))
                    ref     = f"EXP-{year}{month:02d}-{exp_id:05d}"

                    descs = [
                        f"{line} — {datetime(year, month, 1).strftime('%B %Y')}",
                        f"Monthly procurement: {line.lower()}",
                        f"{dept.split()[0]} Dept: {line.lower()} costs",
                        f"Approved expenditure — {line}",
                    ]
                    desc = random.choice(descs)

                    cutoff   = datetime(2026, 5, 1)
                    exp_date = datetime(year, month, day)
                    is_app   = 1 if exp_date < cutoff else 0
                    appr_by  = 1 if is_app else None

                    exp_rows.append((
                        exp_id, ref, dept, desc, amt, line, exp_dt,
                        appr_by, is_app, "none",
                    ))
                    exp_id += 1

    print(f"   Inserting {len(exp_rows):,} expenditure records …")
    conn.executemany(
        "INSERT INTO expenditures "
        "(id, reference_number, department, description, amount, budget_line, expenditure_date, "
        " approved_by, is_approved, anomaly_flag) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        exp_rows,
    )

    # ═══════════════════════════════════════════════════════════════
    # LEAKAGE ALERTS
    # ═══════════════════════════════════════════════════════════════
    print("⚠️   Creating leakage alerts …")

    ALERT_TYPES = [
        ("SPLIT_TRANSACTION",  "Split transaction pattern detected — possible revenue evasion",          "medium"),
        ("GHOST_INVOICE",      "Invoice issued with no matching ratepayer account activity",             "high"),
        ("COLLECTION_GAP",     "Large gap between billing and actual collection for this account",       "medium"),
        ("UNRECONCILED_PMT",   "Significant unreconciled payment outstanding for >90 days",             "medium"),
        ("DUPLICATE_PAYMENT",  "Possible duplicate payment detected — same amount, same date",          "high"),
        ("RATE_ANOMALY",       "Billing rate significantly above/below category average",               "low"),
        ("DEFAULTED_PLAN",     "Payment plan defaulted — debt not being recovered",                     "high"),
        ("GHOST_EMPLOYEE",     "Expenditure for personnel not on HR payroll roll",                      "high"),
        ("INFLATED_INVOICE",   "Supplier invoice amount 40% above market rate benchmark",               "high"),
        ("UNDER_COLLECTION",   "Revenue officer collection rate >20% below team average",               "medium"),
    ]

    alert_rows = []
    for i in range(1, 42):
        atype, adesc, sev = random.choice(ALERT_TYPES)
        yr  = random.randint(2022, 2026)
        mo  = random.randint(1, 12)
        if yr == 2026:
            mo = random.randint(1, 4)
        created_at  = ts(yr, mo, random.randint(1, 28), random.randint(7, 17))
        is_res      = 1 if random.random() < 0.48 else 0
        resolved_at = ts(yr, min(mo + 1, 12), random.randint(1, 28)) if is_res else None
        res_notes   = "Investigated by internal audit — resolved" if is_res else None
        alert_rows.append((
            i, atype, sev, adesc, None, None,
            is_res, 6 if is_res else None, created_at,
            resolved_at, res_notes,
        ))

    conn.executemany(
        "INSERT INTO leakage_alerts "
        "(id, alert_type, severity, description, related_record_id, related_table, "
        " is_resolved, resolved_by, created_at, resolved_at, resolution_notes) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        alert_rows,
    )

    # ═══════════════════════════════════════════════════════════════
    # PAYMENT PLANS
    # ═══════════════════════════════════════════════════════════════
    print("📅  Creating payment plans …")

    plan_rows = []
    for i in range(1, 26):
        rp  = random.randint(1, n_rp)
        n_ins = random.randint(6, 24)
        inst  = round(random.uniform(100, 600), 2)
        debt  = round(inst * n_ins, 2)  # FIX: debt must equal instalment * count
        paid  = random.randint(0, n_ins)
        sy    = random.randint(2022, 2025)
        sm    = random.randint(1, 10)
        start = ts(sy, sm, 1)
        nmo   = sm + paid
        ny    = sy + (nmo - 1) // 12
        nmo   = ((nmo - 1) % 12) + 1
        ny    = min(ny, 2026)
        nmo   = min(nmo, 5 if ny == 2026 else 12)
        nxt   = ts(ny, nmo, 1)
        st    = "completed" if paid >= n_ins else ("defaulted" if random.random() < 0.18 else "active")
        plan_rows.append((
            i, rp, debt, inst, "monthly", n_ins, paid,
            start, nxt, st, 7, NOW,
            f"Payment plan for outstanding arrears — {n_ins} monthly instalments of ${inst:.2f}",
        ))

    conn.executemany(
        "INSERT INTO payment_plans "
        "(id, ratepayer_id, total_debt, instalment_amount, frequency, total_instalments, instalments_paid, "
        " start_date, next_due_date, status, created_by, created_at, notes) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        plan_rows,
    )

    # ═══════════════════════════════════════════════════════════════
    # AUDIT LOGS (sample — realistic history)
    # ═══════════════════════════════════════════════════════════════
    print("📋  Creating 250 audit log entries …")

    ACTIONS = ["LOGIN", "CREATE", "UPDATE", "DELETE", "IMPORT", "FLAG"]
    TABLES  = ["invoices", "payments", "ratepayers", "expenditures", "budgets", "users", "revenue_targets"]
    aud_rows = []
    for i in range(1, 251):
        action  = random.choices(ACTIONS, weights=[0.25, 0.30, 0.25, 0.05, 0.08, 0.07])[0]
        table   = random.choice(TABLES)
        user_id = random.choice([1, 2, 3, 4, 5, 6, 7, 8])
        yr      = random.randint(2021, 2026)
        mo      = random.randint(1, 12)
        if yr == 2026:
            mo = random.randint(1, 5)
        logged  = ts(yr, mo, random.randint(1, 28), random.randint(7, 18), random.randint(0, 59))
        ip      = f"192.168.{random.randint(1,10)}.{random.randint(2,254)}"
        msgs = {
            "LOGIN":  f"Successful login from {ip}",
            "CREATE": f"Created {table[:-1]} record #{random.randint(100,9000)}",
            "UPDATE": f"Updated {table[:-1]} #{random.randint(100,9000)}",
            "DELETE": f"Deleted {table[:-1]} #{random.randint(100,9000)}",
            "IMPORT": f"Bulk imported {random.randint(10,800)} {table} records",
            "FLAG":   f"Flagged {table[:-1]} #{random.randint(100,9000)} for review",
        }
        aud_rows.append((i, user_id, action, table, random.randint(1, 5000), ip, logged, msgs[action]))

    conn.executemany(
        "INSERT INTO audit_logs "
        "(id, user_id, action, table_name, record_id, ip_address, timestamp, description) "
        "VALUES (?,?,?,?,?,?,?,?)",
        aud_rows,
    )

    # ═══════════════════════════════════════════════════════════════
    # COMMIT
    # ═══════════════════════════════════════════════════════════════
    conn.commit()
    conn.close()

    print("\n" + "═" * 55)
    print("  ✅  City of Harare FMS — SEED COMPLETE")
    print("═" * 55)
    print(f"  Ratepayers        : {n_rp:>6,}")
    print(f"  Invoices          : {len(inv_rows):>6,}")
    print(f"  Payments          : {len(pmt_rows):>6,}")
    print(f"  Expenditures      : {len(exp_rows):>6,}")
    print(f"  Budget lines      : {len(bud_rows):>6,}")
    print(f"  Revenue targets   : {len(tgt_rows):>6,}")
    print(f"  Leakage alerts    : {len(alert_rows):>6,}")
    print(f"  Payment plans     : {len(plan_rows):>6,}")
    print(f"  Audit log entries : {len(aud_rows):>6,}")
    print("═" * 55)
    print("  Login credentials:")
    print("    admin / Admin@2025!      (Administrator)")
    print("    jmoyo / Revenue@2025!    (Revenue Officer)")
    print("    btshuma / Account@2025!  (Accountant)")
    print("    fgumbo / Budget@2025!    (Budget Officer)")
    print("═" * 55)


if __name__ == "__main__":
    run()

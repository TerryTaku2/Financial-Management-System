#!/usr/bin/env python3
"""
Comprehensive FMS System Debugger
Checks for data inconsistencies, logic errors, and system issues
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from database import SessionLocal, User, Ratepayer, Invoice, Payment, Expenditure, Budget, AuditLog, LeakageAlert, RevenueTarget, PaymentPlan
from sqlalchemy import func
from datetime import datetime, timezone
import json

db = SessionLocal()

def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

print("\n" + "="*70)
print("  🔍 CITY OF HARARE FMS - COMPREHENSIVE SYSTEM DEBUGGER")
print("="*70)

issues = []
warnings = []

# ══════════════════════════════════════════════════════════════════════════════
# 1. DATABASE INTEGRITY CHECKS
# ══════════════════════════════════════════════════════════════════════════════
print("\n📊 [1/8] DATABASE INTEGRITY CHECKS")
print("-" * 70)

# Check foreign key constraints
print("   ✓ Checking foreign key constraints...")

# Invoices with invalid ratepayer_id
orphan_invoices = db.query(Invoice).filter(
    ~Invoice.ratepayer_id.in_(db.query(Ratepayer.id))
).all()
if orphan_invoices:
    issues.append(f"❌ {len(orphan_invoices)} invoices with orphaned ratepayer_id")
else:
    print("   ✓ No orphaned invoices")

# Payments with invalid ratepayer_id
orphan_payments = db.query(Payment).filter(
    ~Payment.ratepayer_id.in_(db.query(Ratepayer.id))
).all()
if orphan_payments:
    issues.append(f"❌ {len(orphan_payments)} payments with orphaned ratepayer_id")
else:
    print("   ✓ No orphaned payments")

# Invoices with invalid creator
orphan_creators_inv = db.query(Invoice).filter(
    ~Invoice.created_by.in_(db.query(User.id))
).all()
if orphan_creators_inv:
    issues.append(f"❌ {len(orphan_creators_inv)} invoices with invalid creator user_id")
else:
    print("   ✓ No invoices with invalid creators")

# ══════════════════════════════════════════════════════════════════════════════
# 2. INVOICE-PAYMENT CONSISTENCY
# ══════════════════════════════════════════════════════════════════════════════
print("\n💰 [2/8] INVOICE-PAYMENT CONSISTENCY")
print("-" * 70)

# Check amount_paid vs sum of payments
inv_payment_issues = []
for inv in db.query(Invoice).all()[:100]:  # Sample check
    total_paid = db.query(func.sum(Payment.amount)).filter(
        Payment.invoice_id == inv.id
    ).scalar() or 0.0
    if abs(inv.amount_paid - total_paid) > 0.01:
        inv_payment_issues.append({
            'invoice': inv.invoice_number,
            'recorded_paid': inv.amount_paid,
            'actual_paid': total_paid,
            'diff': total_paid - inv.amount_paid
        })

if inv_payment_issues:
    issues.append(f"❌ {len(inv_payment_issues)} invoices with payment amount mismatches")
    for issue in inv_payment_issues[:5]:
        print(f"      • {issue['invoice']}: recorded={issue['recorded_paid']}, actual={issue['actual_paid']}")
else:
    print("   ✓ All sampled invoices have consistent payment amounts")

# Check balance = amount - amount_paid
balance_issues = []
for inv in db.query(Invoice).all()[:100]:
    expected_balance = inv.amount - inv.amount_paid
    if abs(inv.balance - expected_balance) > 0.01:
        balance_issues.append({
            'invoice': inv.invoice_number,
            'recorded_balance': inv.balance,
            'expected_balance': expected_balance
        })

if balance_issues:
    issues.append(f"❌ {len(balance_issues)} invoices with incorrect balance calculations")
    for issue in balance_issues[:5]:
        print(f"      • {issue['invoice']}: recorded={issue['recorded_balance']}, expected={issue['expected_balance']}")
else:
    print("   ✓ All sampled invoices have correct balance calculations")

# ══════════════════════════════════════════════════════════════════════════════
# 3. INVOICE STATUS CONSISTENCY
# ══════════════════════════════════════════════════════════════════════════════
print("\n📋 [3/8] INVOICE STATUS CONSISTENCY")
print("-" * 70)

status_issues = []

# Paid invoices should have balance = 0
paid_with_balance = db.query(Invoice).filter(
    Invoice.status == 'paid',
    Invoice.balance != 0.0
).all()
if paid_with_balance:
    status_issues.append(f"   ❌ {len(paid_with_balance)} invoices marked PAID but have non-zero balance")
    issues.append(f"❌ {len(paid_with_balance)} 'paid' invoices with non-zero balance")

# Pending/overdue invoices should have amount_paid = 0
pending_with_payment = db.query(Invoice).filter(
    Invoice.status.in_(['pending', 'overdue']),
    Invoice.amount_paid > 0.0
).all()
if pending_with_payment:
    status_issues.append(f"   ⚠️  {len(pending_with_payment)} PENDING/OVERDUE invoices with partial payments")
    warnings.append(f"⚠️  {len(pending_with_payment)} pending/overdue invoices have partial payments")

if not status_issues:
    print("   ✓ Invoice status fields are consistent")
else:
    for issue in status_issues:
        print(issue)

# ══════════════════════════════════════════════════════════════════════════════
# 4. PAYMENT RECONCILIATION STATUS
# ══════════════════════════════════════════════════════════════════════════════
print("\n🔄 [4/8] PAYMENT RECONCILIATION STATUS")
print("-" * 70)

# Unreconciled payments should have no reconciled_at
unreconciled_with_date = db.query(Payment).filter(
    Payment.is_reconciled == False,
    Payment.reconciled_at != None
).all()
if unreconciled_with_date:
    issues.append(f"❌ {len(unreconciled_with_date)} unreconciled payments have reconciled_at date")
    print(f"   ❌ {len(unreconciled_with_date)} unreconciled payments with date")
else:
    print("   ✓ Unreconciled payments have no reconciliation dates")

# Reconciled payments should have reconciled_by and reconciled_at
reconciled_incomplete = db.query(Payment).filter(
    Payment.is_reconciled == True,
    ((Payment.reconciled_by == None) | (Payment.reconciled_at == None))
).all()
if reconciled_incomplete:
    issues.append(f"❌ {len(reconciled_incomplete)} reconciled payments missing reconciliation metadata")
    print(f"   ❌ {len(reconciled_incomplete)} reconciled payments missing metadata")
else:
    print("   ✓ All reconciled payments have complete metadata")

# Check idempotency keys for duplicates
dup_idempotency = db.query(Payment.idempotency_key, func.count(Payment.id)).filter(
    Payment.idempotency_key != None
).group_by(Payment.idempotency_key).having(func.count(Payment.id) > 1).all()
if dup_idempotency:
    issues.append(f"❌ {len(dup_idempotency)} duplicate idempotency keys found")
    print(f"   ❌ {len(dup_idempotency)} duplicate idempotency keys")
else:
    print("   ✓ No duplicate idempotency keys")

# ══════════════════════════════════════════════════════════════════════════════
# 5. BUDGET CONSISTENCY
# ══════════════════════════════════════════════════════════════════════════════
print("\n🏛️  [5/8] BUDGET CONSISTENCY")
print("-" * 70)

budget_issues = []

# Check remaining = allocated - spent
for bud in db.query(Budget).all()[:50]:
    expected_remaining = bud.allocated_amount - bud.spent_amount
    if abs(bud.remaining - expected_remaining) > 0.01:
        budget_issues.append({
            'dept': bud.department,
            'cat': bud.category,
            'recorded': bud.remaining,
            'expected': expected_remaining
        })

if budget_issues:
    issues.append(f"❌ {len(budget_issues)} budget lines with incorrect remaining balance")
    print(f"   ❌ {len(budget_issues)} budgets with incorrect remaining calculations")
    for issue in budget_issues[:3]:
        print(f"      • {issue['dept']} / {issue['cat']}")
else:
    print("   ✓ All sampled budget remaining balances are correct")

# Check no negative remaining budgets
negative_remaining = db.query(Budget).filter(Budget.remaining < 0).all()
if negative_remaining:
    issues.append(f"❌ {len(negative_remaining)} budget lines have negative remaining balance (overspent)")
    print(f"   ⚠️  {len(negative_remaining)} budgets are OVERSPENT (negative remaining)")
else:
    print("   ✓ No overspent budgets")

# ══════════════════════════════════════════════════════════════════════════════
# 6. REVENUE TARGET vs ACTUAL COLLECTION
# ══════════════════════════════════════════════════════════════════════════════
print("\n🎯 [6/8] REVENUE TARGET vs ACTUAL COLLECTION")
print("-" * 70)

target_collection_analysis = {}
for year in [2021, 2022, 2023, 2024, 2025, 2026]:
    fy = f"{year}/{year+1}"
    targets = db.query(RevenueTarget).filter(RevenueTarget.fiscal_year == fy).all()
    
    if not targets:
        continue
    
    total_target = sum(t.target_amount for t in targets)
    
    # Calculate actual collections for invoices in that year
    collected = db.query(func.sum(Payment.amount)).join(Invoice).filter(
        (Payment.payment_date >= f"{year}-01-01") & (Payment.payment_date <= f"{year+1}-01-01")
    ).scalar() or 0.0
    
    target_collection_analysis[fy] = {
        'target': total_target,
        'actual': collected,
        'achievement': (collected / total_target * 100) if total_target > 0 else 0
    }

print("   Revenue Target Achievement:")
for fy, data in sorted(target_collection_analysis.items()):
    achievement = data['achievement']
    status = "✓" if achievement >= 70 else "⚠️ " if achievement >= 50 else "❌"
    print(f"   {status} {fy}: ${data['actual']:,.0f} / ${data['target']:,.0f} ({achievement:.1f}%)")
    
    if achievement < 50:
        issues.append(f"❌ {fy} revenue collection {achievement:.1f}% below 50% threshold")

# ══════════════════════════════════════════════════════════════════════════════
# 7. PAYMENT PLAN CONSISTENCY
# ══════════════════════════════════════════════════════════════════════════════
print("\n📅 [7/8] PAYMENT PLAN CONSISTENCY")
print("-" * 70)

plan_issues = []

# Check next_due_date logic
for plan in db.query(PaymentPlan).all()[:20]:
    if plan.instalments_paid >= plan.total_instalments:
        if plan.status != 'completed':
            plan_issues.append(f"Plan {plan.id}: all instalments paid but status is '{plan.status}'")
            issues.append(f"❌ Payment plan {plan.id} fully paid but not marked 'completed'")
    
    # Validate debt calculation
    expected_debt = plan.instalment_amount * plan.total_instalments
    if abs(plan.total_debt - expected_debt) > 0.01:
        plan_issues.append(f"Plan {plan.id}: total_debt mismatch (recorded vs instalment*count)")
        issues.append(f"❌ Payment plan {plan.id} has inconsistent total_debt")

# Check for orphaned ratepayers in plans
orphan_plan_rp = db.query(PaymentPlan).filter(
    ~PaymentPlan.ratepayer_id.in_(db.query(Ratepayer.id))
).all()
if orphan_plan_rp:
    issues.append(f"❌ {len(orphan_plan_rp)} payment plans with orphaned ratepayer_id")

if not plan_issues:
    print("   ✓ All sampled payment plans are internally consistent")
else:
    for issue in plan_issues:
        print(f"   ⚠️  {issue}")

# ══════════════════════════════════════════════════════════════════════════════
# 8. ANOMALY FLAGS
# ══════════════════════════════════════════════════════════════════════════════
print("\n⚠️  [8/8] ANOMALY FLAGS & RISK SCORES")
print("-" * 70)

# Check anomalies flagged as 'none' but have reason
anomaly_inconsistencies = db.query(Invoice).filter(
    (Invoice.anomaly_flag == 'none') & (Invoice.anomaly_reason != None)
).count()
if anomaly_inconsistencies:
    issues.append(f"❌ {anomaly_inconsistencies} invoices flagged 'none' but have anomaly_reason")
    print(f"   ❌ {anomaly_inconsistencies} invoices have 'none' flag + reason text")

# Check ratepayers with invalid risk scores
invalid_risk = db.query(Ratepayer).filter(
    (Ratepayer.risk_score < 0) | (Ratepayer.risk_score > 100)
).all()
if invalid_risk:
    issues.append(f"❌ {len(invalid_risk)} ratepayers have out-of-range risk scores")
    print(f"   ❌ {len(invalid_risk)} ratepayers have invalid risk scores (not 0-100)")
else:
    print("   ✓ All ratepayer risk scores are in valid range (0-100)")

# Risk label validation
invalid_risk_labels = db.query(Ratepayer).filter(
    ~Ratepayer.risk_label.in_(['low', 'medium', 'high', 'critical'])
).all()
if invalid_risk_labels:
    issues.append(f"❌ {len(invalid_risk_labels)} ratepayers have invalid risk labels")
    print(f"   ❌ {len(invalid_risk_labels)} ratepayers have invalid risk labels")
else:
    print("   ✓ All ratepayer risk labels are valid")

# ══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "="*70)
print("  🔍 DEBUG SUMMARY")
print("="*70)

print(f"\n   📊 Data Counts:")
print(f"      • Users:          {db.query(User).count()}")
print(f"      • Ratepayers:     {db.query(Ratepayer).count()}")
print(f"      • Invoices:       {db.query(Invoice).count():,}")
print(f"      • Payments:       {db.query(Payment).count():,}")
print(f"      • Expenditures:   {db.query(Expenditure).count():,}")
print(f"      • Budget lines:   {db.query(Budget).count():,}")
print(f"      • Revenue targets: {db.query(RevenueTarget).count()}")
print(f"      • Payment plans:  {db.query(PaymentPlan).count()}")
print(f"      • Audit logs:     {db.query(AuditLog).count()}")
print(f"      • Leakage alerts: {db.query(LeakageAlert).count()}")

if issues:
    print(f"\n   ❌ CRITICAL ISSUES FOUND: {len(issues)}")
    for i, issue in enumerate(issues, 1):
        print(f"      {i}. {issue}")
else:
    print(f"\n   ✅ NO CRITICAL ISSUES FOUND")

if warnings:
    print(f"\n   ⚠️  WARNINGS: {len(warnings)}")
    for i, warning in enumerate(warnings, 1):
        print(f"      {i}. {warning}")

print("\n" + "="*70)

db.close()

import sys
sys.path.insert(0, '/home/claude/fms/backend')
from fastapi.testclient import TestClient
import main

client = TestClient(main.app)

# Login
r = client.post('/api/auth/login', data={'username':'admin','password':'admin123'})
data = r.json()
token = data['access_token']
user  = data['user']
print('LOGIN OK - User:', user['full_name'], '| Role:', user['role'])

headers = {'Authorization': f'Bearer {token}'}

# Dashboard
d = client.get('/api/dashboard/summary', headers=headers).json()
print('')
print('=== BACKEND FULLY OPERATIONAL ===')
print(f'  Total Billed:     ${d["total_billed"]:>10,.2f}')

# Refresh overdue invoices (auto-update logic)
refresh = client.post('/api/invoices/refresh-overdue', headers=headers).json()
print('')
print('=== OVERDUE STATUS REFRESH ===')
print(f'  Updated Overdue Invoices: {refresh.get("updated_invoices", 0)}')
print(f'  Message: {refresh.get("message")}')
print(f'  Total Collected:  ${d["total_collected"]:>10,.2f}')
print(f'  Outstanding:      ${d["total_outstanding"]:>10,.2f}')
print(f'  Est. Leakage:     ${d["leakage_estimate"]:>10,.2f}')
print(f'  Collection Rate:  {d["collection_rate"]}%')
print(f'  Ratepayers:       {d["ratepayers_count"]}')
print(f'  Invoices:         {d["invoices_count"]}')
print(f'  Payments:         {d["payments_count"]}')
print(f'  Active Alerts:    {d["active_alerts"]}')
print(f'  Anomaly Flags:    {d["anomaly_count"]}')

# Leakage
lk = client.get('/api/leakage/summary', headers=headers).json()
print('')
print('=== LEAKAGE MODULE ===')
print(f'  High Anomalies:   {lk["high_anomalies"]}')
print(f'  Med Anomalies:    {lk["medium_anomalies"]}')
print(f'  Unreconciled Pmts:{lk["unreconciled_payments"]} (${lk["unreconciled_amount"]:,.2f})')
print(f'  Overdue Balance:  ${lk["overdue_balance"]:,.2f}')
print(f'  Est. Leakage:     ${lk["estimated_leakage"]:,.2f}')

# Ratepayers
rp = client.get('/api/ratepayers?limit=5', headers=headers).json()
print('')
print(f'=== RATEPAYERS ({rp["total"]} total) ===')
for x in rp['items'][:4]:
    print(f'  [{x["account_number"]}] {x["full_name"]} - {x["zone"]}')

# Invoices
inv = client.get('/api/invoices?limit=5', headers=headers).json()
print('')
print(f'=== INVOICES ({inv["total"]} total) ===')
for x in inv['items'][:3]:
    print(f'  [{x["invoice_number"]}] {x["ratepayer_name"]} | {x["category"]} | ${x["amount"]} | {x["status"]}')

# Alerts
alrt = client.get('/api/leakage/alerts', headers=headers).json()
print('')
print(f'=== LEAKAGE ALERTS ({len(alrt)} total) ===')
for a in alrt[:4]:
    print(f'  [{a["severity"].upper()}] {a["type"]} - {a["description"][:60]}...')

# Audit
aud = client.get('/api/audit-logs', headers=headers).json()
print('')
print(f'=== AUDIT LOG ({aud["total"]} entries) ===')
for a in aud['items'][:3]:
    print(f'  {a["action"]} | {a["user"]} | {a["description"]}')

# Budgets
bgt = client.get('/api/budgets', headers=headers).json()
print('')
print(f'=== BUDGETS ({len(bgt)} departments) ===')
for b in bgt[:3]:
    print(f'  {b["department"]}: Allocated ${b["allocated"]:,.0f} | Spent ${b["spent"]:,.0f} | {b["utilisation"]}% used')

print('')
print('ALL ENDPOINTS OPERATIONAL')

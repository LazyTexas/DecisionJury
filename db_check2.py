import sqlite3, json

DB = r"E:\Work\Agent\DecisionJury\data\decisionjury.db"
db = sqlite3.connect(DB)
cur = db.cursor()

cur.execute("SELECT id, user_id, title, status, final_decision, report_id, created_at FROM cases ORDER BY created_at DESC LIMIT 10")
print("===== cases =====")
for r in cur.fetchall():
    print(f"  {r[0]} | {r[1]} | {r[2]!r} | status={r[3]} | final={r[4]} | report={r[5]} | {r[6]}")

cur.execute("SELECT id, case_id, title, summary, result, report_id, created_at FROM histories ORDER BY created_at DESC LIMIT 10")
print("===== histories =====")
rows = cur.fetchall()
print(f"  total={len(rows)}")
for r in rows:
    print(f"  {r[0]} | case={r[1]} | {r[2]!r} | {r[3]!r} | result={r[4]} | {r[6]}")

db.close()

"""Build console/console.html from console/template.html with the pilot data embedded.

Same rules as the MCP server (cloudcore/signals.py). churn_flag is not in data/,
so it cannot reach the page; the assert below double-checks.
Run:  python scripts/export_console_data.py
"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import re
from cloudcore.signals import load, assess, SWITCHING, THEMES, verification

c, t, r, x = load()
LEVELS = ["High", "Medium", "Uncertain", "Low"]
def flag(d, text, source):
    d["verification"] = verification(source, d.get("date"))
    d["switching"] = bool(SWITCHING.search(text))
    d["themes"] = [k.split(" (")[0] for k, pat in THEMES.items() if re.search(pat, text, re.I)]
    return d

accounts = []
for row in c.itertuples():
    a = assess(row.customer_id, c, t, r)
    bill = x[x.customer_id == row.customer_id].sort_values("billing_month")
    accounts.append({
        "id": row.customer_id, "name": row.company_name, "industry": row.industry, "region": row.region,
        "tenure": int(row.tenure_months), "products": row.products, "mrr": float(row.monthly_recurring_revenue),
        "tier": row.support_tier,
        "billing": bill.iloc[-1].drop(["customer_id", "transaction_id"]).to_dict() if len(bill) else None,
        "level": a["rule_suggestion"], "reasons": a["rule_reasons"], "evidence": a["evidence"],
        "tickets": [flag(d, d["ticket_text"], "ticket") for d in t[t.customer_id == row.customer_id].sort_values("date").drop(columns=["customer_id"]).to_dict("records")],
        "reviews": [flag(d, d["review_text"], "review") for d in r[r.customer_id == row.customer_id].drop(columns=["customer_id"]).to_dict("records")],
    })
blob = json.dumps(accounts, separators=(",", ":"), default=lambda v: v.item() if hasattr(v, "item") else str(v))
assert "churn_flag" not in blob
tpl = (ROOT / "console" / "template.html").read_text()
# 1) Claude artifact build: data embedded, runs on the artifact's own model and store.
(ROOT / "console" / "console.html").write_text(tpl.replace("/*__DATA__*/[]", blob))
# 2) Self-hosted web build: no data in the page; the backend serves it behind the team passcode.
web = ROOT / "web"
(web / "public").mkdir(parents=True, exist_ok=True)
(web / "src").mkdir(parents=True, exist_ok=True)
(web / "public" / "index.html").write_text(
    "<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1,viewport-fit=cover\">"
    "<meta name=\"robots\" content=\"noindex\"></head><body>\n"
    + tpl.replace('/*__MODE__*/"artifact"', '"web"') + "\n</body></html>\n")
(web / "src" / "accounts.json").write_text(blob)
print(f"console/console.html + web/public/index.html + web/src/accounts.json written: {len(accounts)} accounts, {len(blob)//1024} KB of data")

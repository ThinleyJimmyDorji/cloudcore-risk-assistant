"""CloudCore Customer Risk Intelligence — MCP data server.

Gives an AI assistant (Claude Code, Claude Desktop, or any MCP client) read
access to CloudCore customer, support and feedback data, plus one write tool
for recording the human review decision.

Guardrail: churn_flag is never loaded, so no tool can return it.

Run (stdio):  python -m cloudcore.server
Pilot data source: data/*.csv (refreshed nightly by scripts/prepare_data.py).
Production: replace load() in signals.py with CRM / helpdesk API calls; the
tools and the assistant stay the same.
"""
from __future__ import annotations
import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from mcp.server.mcpserver import MCPServer

from cloudcore.signals import load, assess, DATA

REVIEW_LOG = DATA.parent / "review_log.csv"
LEVELS = ["High", "Medium", "Uncertain", "Low"]

mcp = MCPServer(
    "cloudcore-risk",
    instructions=(
        "CloudCore customer, support-ticket and review data for the Customer Success team. "
        "Use get_risk_signals for evidence and a rule-based attention suggestion. "
        "Ticket content before 15 Feb 2026 and all (undated) reviews are unverified because of a data-integrity incident; "
        "say so whenever you quote them. "
        "Never predict churn and never decide on a customer's behalf: a person reviews every result."
    ),
)


def _customers():
    c, t, r, x = load()
    return c, t, r, x


@mcp.tool()
def get_customer(customer_id: str) -> dict:
    """Customer profile (industry, region, tenure, products, support tier, MRR) and latest billing usage."""
    c, _, _, x = _customers()
    row = c[c.customer_id == customer_id]
    if row.empty:
        return {"error": f"No customer {customer_id}"}
    out = row.iloc[0].to_dict()
    usage = x[x.customer_id == customer_id]
    if not usage.empty:
        out["latest_billing"] = usage.sort_values("billing_month").iloc[-1].drop(["customer_id", "transaction_id"]).to_dict()
    return out


@mcp.tool()
def get_support_history(customer_id: str) -> list[dict]:
    """All support tickets for a customer, oldest first: date, product, channel, satisfaction (1-5), text."""
    _, t, _, _ = _customers()
    return t[t.customer_id == customer_id].sort_values("date").drop(columns=["customer_id"]).to_dict("records")


@mcp.tool()
def get_reviews(customer_id: str) -> list[dict]:
    """All written reviews for a customer: product, rating (1-5), text."""
    _, _, r, _ = _customers()
    return r[r.customer_id == customer_id].drop(columns=["customer_id"]).to_dict("records")


@mcp.tool()
def get_risk_signals(customer_id: str) -> dict:
    """Evidence for one account (switching language, poor support experiences, complaint themes,
    profile risk factors) and a rule-based attention suggestion: High, Medium, Uncertain or Low."""
    try:
        return assess(customer_id)
    except KeyError as e:
        return {"error": str(e)}


@mcp.tool()
def find_accounts(
    region: Literal["San Francisco", "Singapore", "Sydney"] | None = None,
    product: Literal["Analytics Pro", "CloudSync", "DataVault"] | None = None,
    support_tier: Literal["Basic", "Standard", "Premium", "Enterprise"] | None = None,
    min_level: Literal["High", "Medium", "Uncertain", "Low"] = "Medium",
    limit: int = 15,
) -> list[dict]:
    """Screen accounts by filters and return those at or above min_level, strongest evidence first.
    Ranking: suggestion level, then verified warning signs, then switching language, then poor
    support experiences, then MRR (MRR orders accounts within a level; it never sets the level)."""
    c, t, r, _ = _customers()
    sel = c
    if region:
        sel = sel[sel.region == region]
    if product:
        sel = sel[sel.products.str.contains(product)]
    if support_tier:
        sel = sel[sel.support_tier == support_tier]
    keep = LEVELS[: LEVELS.index(min_level) + 1]
    out = []
    for cid in sel.customer_id:
        a = assess(cid, c, t, r)
        if a["rule_suggestion"] not in keep:
            continue
        e = a["evidence"]
        mrr = float(c.loc[c.customer_id == cid, "monthly_recurring_revenue"].iloc[0])
        out.append({
            "customer_id": cid,
            "company_name": a["company_name"],
            "rule_suggestion": a["rule_suggestion"],
            "verified_warning_signs": e["verified_warning_signs"],
            "unverified_warning_signs": e["unverified_warning_signs"],
            "switching_language": len(e["switching_language"]),
            "poor_experiences": len(e["low_satisfaction_tickets"]) + len(e["poor_reviews"]),
            "profile_context": e["profile_risk_factors"],
            "monthly_recurring_revenue": mrr,
        })
    out.sort(key=lambda d: (LEVELS.index(d["rule_suggestion"]), -d["verified_warning_signs"], -d["switching_language"],
                            -d["poor_experiences"], -d["monthly_recurring_revenue"]))
    return out[:limit]


@mcp.tool()
def log_review(
    customer_id: str,
    assistant_level: Literal["High", "Medium", "Uncertain", "Low"],
    decision: Literal["accept", "override", "defer"],
    reviewer: str,
    final_level: Literal["High", "Medium", "Uncertain", "Low"] | None = None,
    note: str = "",
) -> dict:
    """Record the Customer Success reviewer's decision on an assessment. Only call this when a
    person has explicitly stated their decision; never record one on their behalf."""
    new = not REVIEW_LOG.exists()
    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "customer_id": customer_id, "assistant_level": assistant_level, "decision": decision,
        "final_level": final_level or assistant_level, "reviewer": reviewer, "note": note,
    }
    with REVIEW_LOG.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row))
        if new:
            w.writeheader()
        w.writerow(row)
    return {"logged": row}


@mcp.tool()
def get_review_log(customer_id: str | None = None) -> list[dict]:
    """Past human review decisions, optionally for one customer."""
    if not REVIEW_LOG.exists():
        return []
    with REVIEW_LOG.open() as f:
        rows = list(csv.DictReader(f))
    return [r for r in rows if not customer_id or r["customer_id"] == customer_id]


if __name__ == "__main__":
    mcp.run()

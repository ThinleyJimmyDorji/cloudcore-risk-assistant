"""Warning-signal rules for the CloudCore Customer Risk Intelligence Assistant.

These rules encode the Assessment 2 Orange findings (see RULES.md). They do not
predict churn. They gather evidence from what customers said and experienced,
and suggest an attention level that a Customer Success person reviews.

- The level comes from evidence in tickets and reviews. Profile facts (support
  tier, tenure, product count), region, ticket volume and MRR are context only.
- Ticket and review content before the data-integrity incident cut-off
  (15 Feb 2026) may have been tampered with, and reviews carry no date, so that
  evidence is "unverified". High needs at least one verified warning sign.
- churn_flag is never an input.
"""
from __future__ import annotations
import re
from pathlib import Path
import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data"

# Customer's own words that signal intent to leave or a named competitor.
SWITCHING = re.compile(
    r"\b(AWS|Azure|Google Cloud|big clouds|Step Functions|considering switching|"
    r"evaluating alternatives|considering alternatives|move this to|switching cost)\b",
    re.I,
)
# "Switching cost is the only thing holding us back" = staying only because leaving is hard.
LOCKED_IN = re.compile(r"switching cost is the only thing holding us back", re.I)

THEMES = {
    "CloudSync reliability (sync failures, duplicated records)": r"\bsync|cloudsync|duplicated (half our )?records|failed overnight",
    "Integration / API breakage": r"ERP|API error|field mapping|integration|large batch",
    "Onboarding & usability": r"onboarding|learning curve|interface|docs are thin|confusing|full access",
    "Performance (slow dashboards, timeouts)": r"slow|times out|over a minute|latency",
    "Billing & pricing": r"billed twice|refund|pricing climbed|for the price|invoice",
    "Storage / backup failures": r"uploads have been failing|blocking our backups",
}
LOW_SAT = 2          # ticket satisfaction <= 2 counts as a poor support experience
POOR_RATING = 2      # review rating <= 2 counts as poor feedback
SHORT_TENURE = 12    # months (profile context only)
INCIDENT_CUTOFF = "2026-02-15"  # tickets on/after this date were validated after remediation


def load():
    c = pd.read_csv(DATA / "customers.csv")
    t = pd.read_csv(DATA / "support_tickets.csv")
    r = pd.read_csv(DATA / "reviews.csv")
    x = pd.read_csv(DATA / "transactions.csv")
    assert "churn_flag" not in c.columns, "churn_flag must never reach the assistant"
    return c, t, r, x


def _themes(texts: list[str]) -> dict[str, int]:
    out = {}
    for name, pat in THEMES.items():
        n = sum(bool(re.search(pat, s, re.I)) for s in texts)
        if n:
            out[name] = n
    return out


def verification(source: str, date: str | None) -> str:
    """'verified' for tickets dated on/after the incident cut-off; otherwise why it isn't."""
    if source == "review" or not date:
        return "unverified-undated"
    return "verified" if date >= INCIDENT_CUTOFF else "unverified-pre-incident"


def assess(customer_id: str, c=None, t=None, r=None) -> dict:
    """Return the evidence for one account and a rule-based attention suggestion."""
    if c is None:
        c, t, r, _ = load()
    row = c[c.customer_id == customer_id]
    if row.empty:
        raise KeyError(f"Unknown customer {customer_id}")
    p = row.iloc[0]
    tk = t[t.customer_id == customer_id].sort_values("date")
    rv = r[r.customer_id == customer_id]

    feedback = [("ticket", d.date, int(d.satisfaction_score), d.ticket_text) for d in tk.itertuples()] + \
               [("review", None, int(d.rating), d.review_text) for d in rv.itertuples()]
    texts = [f[3] for f in feedback]
    item = lambda f: {"source": f[0], "date": f[1], "score": f[2], "text": f[3], "verification": verification(f[0], f[1])}

    switching = [f for f in feedback if SWITCHING.search(f[3])]
    low_tickets = [f for f in feedback if f[0] == "ticket" and f[2] <= LOW_SAT]
    poor_reviews = [f for f in feedback if f[0] == "review" and f[2] <= POOR_RATING]
    poor = low_tickets + poor_reviews
    warnings = list({id(f): f for f in switching + poor}.values())   # each feedback item counted once
    verified_warnings = [f for f in warnings if verification(f[0], f[1]) == "verified"]
    themes = _themes([f[3] for f in poor]) or {}

    profile = []
    if p.support_tier == "Basic":
        profile.append("Basic support tier")
    if p.tenure_months < SHORT_TENURE:
        profile.append(f"Short tenure ({p.tenure_months} months)")
    if "+" not in p.products:
        profile.append(f"Single product ({p.products})")

    # Conflict: switching language followed by a later clearly positive ticket.
    last_switch_date = max((f[1] for f in switching if f[1]), default=None)
    later_positive = [f for f in feedback if f[0] == "ticket" and last_switch_date
                      and f[1] > last_switch_date and f[2] >= 4]

    n_items = len(feedback)
    strong = bool(switching and poor) or len(poor) >= 2   # leaving language with pain, or repeated pain
    reasons = []

    # Rule order matters: the first matching rule sets the suggestion.
    if switching and later_positive:
        level = "Uncertain"
        reasons.append("Switching language was followed by a better support experience; a person needs to confirm intent.")
    elif strong and verified_warnings:
        level = "High"
        reasons.append(("The customer's own words mention leaving or a competitor, alongside a poor experience"
                        if switching and poor else "Repeated poor support experiences")
                       + (", and this warning sign comes from a verified (post-incident) ticket." if len(verified_warnings) == 1
                          else f", and {len(verified_warnings)} of these warning signs come from verified (post-incident) tickets."))
    elif strong:
        level = "Medium"
        reasons.append(("Leaving language with a poor experience" if switching and poor else "Repeated poor experiences")
                       + ", but all of it predates the data-integrity incident or is undated. Confirm with the customer before treating this as High.")
    elif switching or poor:
        level = "Medium"
        f = next(iter(warnings))
        reasons.append(("Switching language" if switching else "One poor experience")
                       + (" on a verified ticket" if verified_warnings else " (unverified evidence)")
                       + ", without a repeated pattern yet. Check in and ask whether it was resolved.")
    elif n_items < 2:
        level = "Uncertain"
        reasons.append(f"Only {n_items} feedback item(s) on record — not enough evidence either way.")
    else:
        avg = sum(f[2] for f in feedback) / n_items
        if avg >= 3.5:
            level = "Low"
            reasons.append(f"Feedback is neutral-to-positive (average {avg:.1f}/5) with no warning signs.")
        else:
            level = "Uncertain"
            reasons.append(f"Feedback is lukewarm (average {avg:.1f}/5) but shows no clear warning sign.")

    verified_items = sum(verification(f[0], f[1]) == "verified" for f in feedback)
    return {
        "customer_id": customer_id,
        "company_name": p.company_name,
        "rule_suggestion": level,
        "rule_reasons": reasons,
        "evidence": {
            "switching_language": [item(f) for f in switching],
            "staying_only_because_of_switching_cost": any(LOCKED_IN.search(s) for s in texts),
            "low_satisfaction_tickets": [item(f) for f in low_tickets],
            "poor_reviews": [item(f) for f in poor_reviews],
            "verified_warning_signs": len(verified_warnings),
            "unverified_warning_signs": len(warnings) - len(verified_warnings),
            "complaint_themes": themes,
            "profile_risk_factors": profile,
            "feedback_items_on_record": n_items,
            "verified_feedback_items": verified_items,
            "avg_ticket_satisfaction": round(float(tk.satisfaction_score.mean()), 2) if len(tk) else None,
            "avg_review_rating": round(float(rv.rating.mean()), 2) if len(rv) else None,
        },
        "context_not_scored": {
            "region": p.region,
            "ticket_count": int(len(tk)),
            "profile": profile,
            "monthly_recurring_revenue": float(p.monthly_recurring_revenue),
            "note": "Profile (support tier, tenure, product count), region, ticket volume and MRR are shown for context only. "
                    "Scoring them would rate customers by what they buy or where they are, not by what they told us. "
                    "MRR is used only to order accounts within the same level.",
        },
    }

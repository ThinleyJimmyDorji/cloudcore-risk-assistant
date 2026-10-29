---
name: account-brief
description: Assess one CloudCore account for Customer Success. Gives an attention level, the evidence, complaint themes, what to investigate, a next step and what still needs human review. Use when someone asks about a specific customer ID or company, or wants call prep.
---

# Account brief

1. Call `get_risk_signals(customer_id)`, `get_customer`, `get_support_history` and `get_reviews`. Call `get_review_log(customer_id)` to see if a person has already reviewed this account.
2. Read the tickets and reviews yourself. Check what the rules flagged against the actual text. Look for anything the rules miss: sarcasm, a problem that was later resolved, an urgent outage, or a renewal mention.
3. Decide the level. Keep the `rule_suggestion` unless the text clearly contradicts it. If you change it, add the line **"Assistant disagrees with rules — needs human review"** and give the reason.
4. Write the brief in exactly this structure:

```
## <Company name> (<customer_id>) — Attention: <High | Medium | Uncertain | Low>

**Why this account may need attention** — 1–2 sentences.

**Key evidence**
- <quoted ticket/review text> (<ticket|review>, <date>, <score>/5, <Verified | Unverified · pre-incident | Unverified · undated>)
- Context (not scored): <tier, tenure, products, MRR>

**Main complaint / service themes** — <themes, or "none recorded">

**What Customer Success should investigate** — 2–3 specific questions.

**Suggested next step** — one action, an owner role (CSM / Support / Product), and a timeframe.

**Talking points for the call** — 2–3 points the CSM can say in their own words. Acknowledge the specific problem and don't over-promise.

**Needs human review** — what the data can't tell us (e.g. whether the issue was fixed, contract dates, the relationship history). If any key evidence is unverified, say it predates the data-integrity incident or is undated, and needs confirming with the customer.

_Based on <n> tickets and <n> reviews. This is decision support, not a churn prediction._
```

5. Offer to log the decision. If the user gives their name and a decision, call `log_review`.

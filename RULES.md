# Attention rules

These rules turn the Assessment 2 Orange findings into a consistent first pass. `cloudcore/signals.py` implements them, and the `get_risk_signals` tool returns the result. The assistant starts from the rule suggestion, reads the actual tickets and reviews, and explains the result. **A person decides.**

**The level comes from what customers said and experienced.** It never comes from what kind of customer they are.

## What the rules look at

| Signal | Why (Orange finding) | Role |
|---|---|---|
| Low-satisfaction ticket (≤ 2/5) | 50% flag rate vs 20.9% without one | **Warning sign** |
| Poor review (≤ 2/5) | Lower satisfaction among flagged accounts | **Warning sign** |
| Switching language or a named competitor (AWS, Azure, "evaluating alternatives") | Sentiment scoring misses switching intent | **Warning sign** |
| Complaint themes (CloudSync sync, integration, onboarding…) | Recurring complaint clusters | Explains the *why* |
| Support tier, tenure, number of products | Strong correlates in Orange, but they describe what a customer buys, not what they experienced | **Context only** |
| Region | San Francisco has a 49.2% flag rate | **Context only**: scoring it would penalise customers for where they are |
| Ticket volume | Not significantly associated with churn | **Context only** |
| MRR | Lowest-MRR quarter has a 54% flag rate, highest 3%; mostly mirrors support tier | **Context only**: orders accounts within a level, never sets the level |
| Sentiment score | Misleading on its own | **Not used** |
| `churn_flag` | This is the outcome being checked against | **Never visible to the assistant** |

## Data integrity: verified and unverified evidence

A data-integrity incident, discovered in late February 2026, involved unauthorised edits, score changes and deletions in ticket and review records. Following the Assessment 2 approach, the conservative cut-off is **15 February 2026**:

| Label | Applies to | Count |
|---|---|---|
| `verified` | Tickets dated 15 Feb 2026 or later (validated after remediation) | 120 tickets |
| `unverified-pre-incident` | Tickets dated before 15 Feb 2026 | 240 tickets |
| `unverified-undated` | All reviews (no date field) | 240 reviews |

Unverified evidence still counts. Assessment 2 found the main patterns held up in the verified subset. But it **can't make an account High on its own**.

## Attention levels

The first rule that matches sets the level.

*Strong evidence* means switching language together with a poor experience, or two or more poor experiences.

1. **Uncertain:** switching language followed by a later positive ticket (4/5 or above). A person needs to confirm intent.
2. **High:** strong evidence, with **at least one warning sign on a verified ticket**.
3. **Medium:** strong evidence, but all of it unverified. The brief says to confirm with the customer before escalating.
4. **Medium:** a single warning sign (one poor experience, or switching language on its own).
5. **Uncertain:** fewer than two tickets or reviews, or lukewarm feedback (average below 3.5) with no warning sign.
6. **Low:** enough feedback, neutral to positive, no warning signs.

**Call-list order:** level, then number of verified warning signs, then switching language, then poor experiences, then MRR. The weekly list takes High accounts first, then Medium accounts with a warning sign, up to 10, and leaves out accounts reviewed in the last 7 days.

## Exploratory check (in-sample, not accuracy)

`python eval/run_rules_eval.py` compares the suggestions with the historical `churn_flag` after the fact:

| Level | Accounts | Historically flagged |
|---|---|---|
| High | 7 | 57.1% |
| Medium | 47 | 38.3% |
| Uncertain | 127 | 26.8% |
| Low | 99 | 15.2% |

The base rate is 25.4%.

**The trade-off we chose.** The previous rules let support tier, tenure and product count push accounts to High. They separated the historical flags more sharply: 72% of High accounts and 5.5% of Low accounts were flagged. But they rated customers mainly by what they buy, so every short-tenure, single-product Basic customer looked risky before saying a word.

The evidence-based rules are fairer and easier to explain, and they don't depend on tampered or undated records. In return, they match the historical flags less closely.

`churn_flag` means "churned **or at risk**", and may itself have been set from those profile facts. So the sharper separation of the old rules is partly circular.

**Limits:**
- The thresholds were chosen on the same 280 customers, so this check is in-sample. It doesn't show how the rules would do on new customers.
- Only 7 accounts reach High because only 120 tickets are verified. As verified data builds up after remediation, more accounts will qualify.

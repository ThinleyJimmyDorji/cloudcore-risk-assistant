---
name: weekly-watchlist
description: Produce Customer Success's weekly call list of CloudCore accounts that most need attention, with a one-line reason each. Use for "who should we call this week", "watch-list", or a filtered list (region, product, tier).
---

# Weekly watch-list

Priya's brief: *a short, accurate list beats a long noisy one.*

1. Call `find_accounts` with any filters the user gave, `min_level="Medium"` and `limit=15`. High accounts come first, then Medium. The order is by verified evidence first, with MRR only breaking ties.
2. Call `get_review_log()` and leave out any account a person reviewed in the last 7 days. List the excluded accounts in one line at the end.
3. For each remaining account, call `get_risk_signals` and write one row. Cap the list at 10 rows unless the user asks for more.

```
| # | Account | Level | Why now (customer's words where possible) | Suggested owner |
|---|---------|-------|--------------------------------------------|-----------------|
```

4. After the table, add:
   - **Patterns this week:** 1–2 lines, e.g. "6 of 10 are CloudSync-only on Basic support". Patterns like this are product or pricing issues, not just call issues.
   - **Evidence quality:** how many rows rest only on unverified evidence (before 15 Feb 2026, or undated reviews). Those calls should confirm the problem first.
   - **Not on this list:** accounts with no recent feedback can't be assessed well. Say how many are Uncertain because of missing evidence.
   - A reminder that this is a prioritised starting point and the CSM decides who to call.
5. Offer an `account-brief` for any row.

# PRODUCT.md — why the screen looks the way it does

> **Status (2026-09-18, D-113):** written 2026-09-14 for the research screen (`web/index.html`) as it stood then. The numbers quoted below are those of the decision records they cite and some have moved since — the "2 of 26" of D-066 is now 3 of 44 at quoted prices and 0 of 44 under the full test (D-103). Current numbers: `findings/latest.json` and the README. The staged product is in `PRODUCT_ROADMAP.md`. Kept because the screen's reasoning is still the one in use.

This document is the bridge between `DECISIONS.md` and the interface. That file
records **what we measured**; this one records **what those measurements mean on
screen**.

**What it is not:** a feature list. If it were, it would repeat `BACKLOG.md` and rot
at the first design change. Layout, colour, component library and framework are not
here — those are cheap to change, and deciding them now would be pretending to
know what we do not.

**The principle:** fix what is expensive to change later, leave the rest open.
Exactly what we did with the data model (D-040).

---

## 1. What the product does

Two markets give different probabilities for the same future event. This product
**measures** that gap and says **how much it can be trusted**.

What it does not say: what you should do about it. We measured — the gap is real
in direction but almost nowhere tradable (D-049). Printing an opportunity label
would be wrong on 44 rows out of 44.

## 2. Audience — and the contradiction, resolved

The priority is a **personal research tool**; the site also carries portfolio and
brand value.

Those two look like they pull in opposite directions: a portfolio piece wants to
look finished, a personal tool wants not to lie. **There is no contradiction.** To
a reader who knows derivatives, a tool that prints "44%" on a ladder with a spread
of 0.099 looks amateur; a tool that says "on this row the spread is wider than the
gap I am measuring, so I am not producing a number" looks like it knows the
subject. **Saying nothing is not a defect — it is the portfolio value itself.**

Policy: silence is not hidden, it is presented well.

---

## 3. Constants that come from measurement

These are not design preferences, they are **findings**. Changing one takes a new
measurement.

### 3.1 On most rows there is no headline number
On TSLA, 7 of 14 rungs produce no number; on the SPY downside, 7 of 7 (D-021).
→ **List columns are always chosen from things that can always be computed.** The
pricing number cannot be the column the list rests on.

### 3.2 The strength of the evidence changes with the horizon
At short tenors the digital is model-free; at long tenors the touch bound assumes
a model (D-046). Kalshi's annual terminal buckets removed that constraint for
crypto (D-066), but the proxy error remains for commodities and indices.
→ **Every row carries its own evidence level.** Showing them as if they were the
same kind of number is wrong.

### 3.3 Nothing came out tradable
0 of 44 survive on a narrow spread, 0 of 25 on a wide one, and delta hedging does
not replicate the digital anyway (measured: a model-free digital cannot be
replicated). On the Kalshi annual buckets 2 of 26 cleared the band for the first
time (D-066) — and even that carries the expiry-gap caveat.
→ **There is no "buyable / sellable" label.** The band itself is shown: the gap,
the uncertainty, the friction, and why it is untouchable.

### 3.4 The reference is not zero, it is the gap's own history
The options-implied probability carries a variance risk premium; reading the raw
gap against zero pushes the user in the same structural direction every time
(D-009).
→ **A "typical gap" field is required.** It does not exist yet — the archive
started on 2026-08-30.

### 3.5 Every number sits next to a constraint that could refute it
Four errors have been caught so far and **all four were caught by a constraint,
not by a number**: a curly quote, a gamed metric, the wrong curve on the put side,
and one cent at a bucket boundary (D-067). In the last of those the digitals
looked flawless one by one; only the constraint that an exhaustive set must sum to
1 made the error visible.
→ **This is the design principle of the product.** Next to every number on screen
stands a check that could falsify it: the sum, monotonicity, two methods agreeing,
the spread, simultaneity.

---

## 4. Screen architecture

### 4.1 Headline: the pricing thesis
What the screen says is a thesis. One measurement leads: whichever comparison
currently has the strongest evidence level.

### 4.2 The list: flow as filler, plus columns that can always be computed
Flow data is present on every market (D-038); the pricing number is sparse. So the
**thesis is the headline message and flow is the list filler.** They do not
contradict each other, they do different jobs.

List columns — every one of them computable on every row:

| column | why it is here |
|---|---|
| asset / ladder | identity |
| rung count | how deep the ladder goes |
| **measurable ratio** (e.g. `20/22`) | reliability at a glance |
| evidence level | model-free / model-assuming |
| volume · open interest | liquidity |
| freshness | last update, and the drift between the two sides |
| expiry | horizon |

The pricing number is **not a load-bearing column** in the list; it appears on the
rows that have earned it.

### 4.3 Ordering: by measurability
Not alphabetical, not by volume. Measured assets on top (BTC/ETH: 20/22),
unmeasurable ones below. That way the top of the screen is full and alive; fading
starts where it is expected and reads as "this region cannot be measured" rather
than "the data failed to arrive".

### 4.4 Detail: on clicking a row
The rung table, both sides' prices, the gap, the uncertainty, the friction
breakdown, and the checks that apply. Tabs: **Pricing** and **Hedge** are active;
the others do not open until they are verified in `DATA_SOURCES.md`.

---

## 5. Silent-row policy

A row that cannot be measured is **shown faded**, with the reason revealed on
hover. It is not filtered out and not hidden.

The reason is always concrete and numeric:
- `spread 0.099 — wider than the gap we measure`
- `time value 1.2% of price — deep ITM, unusable`
- `PM price at tick floor`
- `no put chain — downside not measurable`
- `bucket sum 1.13 — set fails exhaustiveness check`

**Why faded and not hidden:** showing where we cannot measure raises the value of
where we can. Hide it and the product looks like it knows everything, which it
does not.

---

## 6. A thin archive is not hidden either

The "typical gap" field will sit empty for weeks. A counter goes there instead:
`reference: collecting — 3 days`.

Showing the counter instead of concealing the gap turns the archive from a defect
into a feature: the user sees what is accumulating, and knows what arrives at the
end of it.

Until the archive is long enough, the words **"statistically significant"** are not
used anywhere. The language stays descriptive.

---

## 7. Language

**Everything is in English** — the interface, the code, the documents and the
archive's own field names. Derivatives terminology is settled in English
("terminal probability", "touch probability", "implied"), the venues publish in
English, and a reader coming to this as a portfolio piece reads English. Keeping a
single language end to end also means a field name on screen, in the archive and in
a script is literally the same string.

## 8. Terminology (applies to the interface too)

Not used: *fair value, true probability, AI probability, edge, signal, arbitrage,
insider, smart money.*

Used: *prediction-market-implied probability, options-implied risk-neutral
probability, cross-market probability gap, terminal / touch probability,
measurable / not measurable, large trade, concentrated position, historical
resolution record.*

Reason: we do not name what we cannot claim. "Edge" and "signal" promise something
tradable; as far as we have measured, there is no such thing here.

---

## 9. Deliberately left open

These are not decided because they are **cheap to change**, and deciding them now
would be an imitation of knowledge:

- layout, typography, colour palette
- framework and component library (nothing will be forked, a library will be used)
- chart types
- mobile behaviour
- alert channel (B-007)

---

## 10. What changes this document

The constants in section 3 change only through **a new measurement**, never
through discussion. A measurement that changes one goes into `DECISIONS.md` as a
decision first, and this document is updated after. Not the other way round.

Sections 4 to 8 are preferences; they can change, and the reason goes here.

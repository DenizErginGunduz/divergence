# DESIGN.md — the design language

`PRODUCT.md` records **what the screen says**; this document records **how it
looks**.

The rule underneath everything: **when a theme arrives tomorrow, the only thing
that should have to change is the token file.** Three layers are separated for
that, and mixing them is not allowed.

| layer | contents | can it change |
|---|---|---|
| **token** | palette, typeface, corners, spacing, shadow | **yes** — the theme file changes, nothing else |
| **functional** | density, alignment, tabular figures, colour meanings, the language of silence | **no** — only through a new measurement |
| **content** | card fields, columns, icon mapping | **yes** — it is data, not code |

---

## 1. Token layer

All CSS variables. Changing the theme means changing this block.

```
--bg            background           #090b0c
--surface       surface (card, row)  #131516
--border        divider              #1f2223
--text          primary text         #e8e8e8
--text-2        secondary            #c6c6c6
--text-3        faded / label        #878787
--text-4        silent row           #4a5052
--accent        the single accent    (the theme decides)
--font          body typeface        Inter var
--radius        corner               6px
--gap           base spacing         8px
```

**There is one accent colour.** DefiLlama uses a single blue (202 uses), Laevitas a
single teal (117 uses). Colour is not spent on decoration.

---

## 2. Functional layer — the theme does not touch these

These are not ornament; they carry readability and honesty. Changing one means
writing the reason into `DECISIONS.md` as a decision.

### 2.1 Numbers
- **Right-aligned.** Names left, numbers right. (On DefiLlama 89% of cells are
  right-aligned.)
- **`font-variant-numeric: tabular-nums` is required.** Neither reference we studied
  had it; in a product where people compare numbers column by column it is the
  cheapest readability gain available.
- **The same number of decimals within a column.** Not 0.0255 and 0.005, but
  0.0255 and 0.0050.

### 2.2 Colour meanings
The theme changes the palette, it **cannot change the meaning**:

| role | meaning | where |
|---|---|---|
| `--ok` | a check passed | the sum, monotonicity, simultaneity |
| `--warn` | a caveat applies, the number is still shown | expiry gap, index mismatch |
| `--muted` | cannot be computed yet | fields waiting on the archive |
| `--accent` | the measured quantity | the gap bar |

Green does not mean buy and red does not mean sell. **Colour is never used for
direction** — direction is written with a sign (`+0.0206`). This is the visual form
of the D-009 rule that nothing gets reduced to a single green or red score.

### 2.3 Density
- Table row **36–40px**. (DefiLlama uses 50px, but we carry more columns.)
- Two sizes: **12px** and **14px**. Two weights: **400** and **500**. 600 and above
  only in a card heading. In the reference, those four combinations carried about
  95% of the interface.
- Vertical rhythm inside a card is in multiples of `--gap`.

### 2.4 Silent rows
Faded (`--text-4`), **left in place**, never filtered out. The reason is always
concrete and numeric (see `PRODUCT.md` §5). The reason text is templated:
`not measurable · <criterion> <value>`

---

## 3. Content layer — data, not code

Card fields and columns live as **configuration**; changing them does not mean
opening a component. The schema:

```json
{
  "asset": "BTC",
  "label": "Bitcoin",
  "icon": "btc",
  "spot": 78483.28,
  "ladders": 6, "expiries": 8,
  "analyses": [
    {"id":"pricing","label":"Pricing","state":"live","detail":"26/28 buckets · model-free"},
    {"id":"flow","label":"Flow","state":"live","detail":"data-api live"},
    {"id":"cross","label":"Cross-platform","state":"live","detail":"Kalshi + Polymarket"}
  ],
  "note": "tails 4–8× richer on prediction"
}
```

`state` takes three values: `live` · `partial` · `none`. Adding a new analysis means
adding an element to the array; the card component does not change.

**Rule: no score, no badge, no ranking, no single-number confidence percentage on
a card.** A card reports a state, it does not pass judgement.

---

## 4. Asset icons

Every asset gets an icon (as on Polymarket). Three sources are tried in order:

1. **A local icon map** — under our own control, keyed by the `icon` field
2. **Polymarket's `icon` field** — already in the archive (`polymarket_events`), source
   on record
3. **Fallback** — the ticker inside a circle, `--surface` ground, `--text-2` text

**An icon is never required.** If one is missing the interface does not break, the
fallback takes over. No direct connection to a third-party CDN; if an external
image is ever used, its source and licence go into `DATA_SOURCES.md`.

---

## 5. Page order and opening

### 5.0 The two strips at the top — an answer, not navigation

**[0] Findings strip.** At the very top of the page, the answer to "what did this
tool find". It is a **grid**, not a slider (D-069): four findings on one row, two
on a narrow screen, then one.

- **It does not rotate.** An automatic carousel is a pattern mistake: most users
  never see the second card. We cannot put our best finding behind a timer. It was
  briefly a horizontally scrolling strip, and an infinitely scrolling one read
  worse than a grid — which is why it is a grid now.
- **Its contents are always computed**, never hand-written. Every card derives from
  a measurement and changes when the data changes. If a hand-written sentence
  leaks in here, the strip turns into a slogan board.
- Every card has to **stand on its own**; none of them may depend on the order.

**[0.5] Notable right now.** A three-to-four row showcase just above the asset
cards. Not navigation — concrete examples.

- It is called **"notable"**, NOT "opportunities" and NOT "signals". A showcase
  drifts into an opportunity list over time; the name is the first defence against
  that.
- **The selection rule is written down and computed:** rows whose gap clears the
  friction-plus-uncertainty band; if none of them do, the highest-ratio rows, and
  in that case each row is labelled "within trading costs".
- If it is empty it is hidden. The threshold is never relaxed to fill it.

### 5.1 Opening

```
[1] Asset cards        grid · filter chips stay visible
      ↓ click
[2] Ladder list        row = ladder · columns that can always be computed
      ↓ click (opens IN PLACE)
[3] Rung table         row = rung · gap/band bar
      ↓ click (opens IN PLACE)
[4] Detail card        one measurement · the full reasoning · constraint strip
```

**Opening in place is required.** Changing pages makes comparison with neighbouring
rows impossible, and that comparison is the actual work. Navigating tires the
reader; expanding does not.

---

## 6. Icon families — there are two

An icon says "look here", which makes it a claim. Every icon has to have a
**computable definition and a threshold**.

**Structural — lit today**, computed from a single snapshot:
- open interest ranking within a ladder
- spread status (measurable / not)
- evidence level (model-free / model-assuming)
- whether the gap clears the band
- freshness and simultaneity

**Temporal — `--muted` and "collecting" until the archive fills**:
- volume against its own 30-day median
- unusual wallet activity
- where the gap sits in its own history

No threshold-free label like "high volume". `volume 4.2× 30d median` instead.

---

## 7. Theme-change checklist

When a new theme arrives, in order:

1. The token block changes — no other file is opened.
2. Contrast check: is `--text-4` still **readable** on a silent row? A silent row
   should be faint, not invisible.
3. Can `--ok` / `--warn` / `--muted` be told apart? They must also be distinguishable
   under colour blindness — which is why icon shape travels with the colour and
   colour is never relied on alone.
4. Are tabular figures preserved? If the new typeface does not support `tnum`, it is
   not used.
5. Is the row height inside the 36–40px band?

A theme is not accepted until all five pass.

---

## 8. Deliberately left undecided

The accent colour itself, the typeface family (Inter is the default but not
binding), chart types, mobile breakpoints, animation. Those are settled when a
theme arrives; the skeleton works independently of them.

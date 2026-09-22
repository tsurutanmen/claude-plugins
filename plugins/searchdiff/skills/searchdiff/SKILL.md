---
name: searchdiff
description: Answer "did the SEO change work?" and "what happened to search traffic?" with Search Console data, using weekly blocks and a difference-in-differences against control pages instead of a before/after on the changed pages alone. Use when a user asks whether a title, description, or content change helped, when traffic dropped, or when reading a Search Console export.
metadata:
  trigger: Search Console data, CTR before/after, a traffic drop, "did the rewrite help", weekly click trends, GSC CSV export
  author: Tsuruta Lab (https://tsurutalab.org)
---

# searchdiff

Two questions come up with Search Console, and both are usually answered wrong.

1. "Traffic dropped. When, and how far back is it?" Answered by staring at a daily chart. Use weekly
   blocks from a fixed anchor: the day-of-week noise disappears and a cliff is one line.
2. "We rewrote the titles. Did it help?" Answered by comparing the changed pages before and after.
   That comparison contains the season, the algorithm update, and the change, all mixed. Use the
   pages that were *not* changed as the control and report the difference in differences.

## Install and get data

```
pip install "searchdiff[api]"
```

- From the UI: Performance > Export > the `Dates.csv` (site totals per day) or any CSV with
  `date,page,clicks,impressions[,position]` columns.
- From the API, with a service account added as a user of the property:
  `searchdiff fetch --site https://example.com/ --key sa.json --start 2026-06-01 --end 2026-08-31 --out pages.csv --coverage`

## Commands

```
searchdiff weeks daily.csv --anchor 2026-07-18
searchdiff effect pages.csv --change 2026-08-04 --treated "re:/blog/" --window 28 [--gap 7] [--control SPEC]
```

`--treated` and `--control` take a substring, a glob, `re:` a regex, or `@file` with one URL per line.
Control defaults to every page that is not treated.

## How to read `weeks`

- `CLIFF` marks a block whose clicks/day fell 30% or more from the previous block. Say the date.
- `of peak` is the block's clicks/day as a share of the best block. "At 64% of peak, flat for three
  weeks" is a sentence; "traffic is down" is not.
- The last block is partial; compare its `/day`, not its total. Search Console lags two to three days.

## How to read `effect`

Report the difference-in-differences line, not the treated group's own change:

- `ctr` in points: treated change minus control change. If the control moved by the same amount,
  the rewrite did nothing. Say so.
- `clicks/day` and `impr/day` as relative changes, so a 5-page group and a 500-page group compare.
- `position` in ranks, negative is better. A CTR gain with a position loss means the new title is
  clicked more where it still shows, which is a different claim.

The tool prints notes when the window runs past the data, when the treated group has too few clicks
to distinguish anything from noise, or when treated and control moved together. Repeat those notes
in the write-up.

## What it cannot tell

Difference in differences assumes the control would have moved like the treated pages had nothing
been changed. Pages of a different kind (a product page against a blog) break that. Prefer a control
of the same kind, `--control "re:/blog/"`, or a hand-picked `@file`. A change that takes days to be
re-indexed needs `--gap`.

## Coverage

`fetch --coverage` prints how much of the clicks the query dimension shows. Search Console hides
rare queries, so query-level sums are often 40% of the truth while page-level sums match the total.
Analyse by page unless the words are the point.

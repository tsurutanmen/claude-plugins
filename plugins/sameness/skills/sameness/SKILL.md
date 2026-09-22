---
name: sameness
description: Check whether the pages of one site look like one template, or like several unrelated sites. Use after building or editing two or more pages, before calling a site "done", or when a user says the site "looks AI-generated" or "all looks the same" and per-page tell detectors have nothing to say.
metadata:
  trigger: More than one page of a site was created or changed; a review of a whole site; a complaint that pages look identical or inconsistent
  author: Tsuruta Lab (https://tsurutalab.org)
---

# sameness

The two things people say about machine-made sites are "it screams AI" and "they all look the same".
Both are properties of a set of pages, not of one page. Per-page detectors (Tell Score, avoid-ai-design)
catch the purple gradient and the Inter font; they cannot see that five pages are one template with the
words swapped, or that a site has four different headers. This tool compares pages with each other.

## When to run it

- You generated or edited two or more pages of one site.
- A user asks whether the site looks templated, generic, or inconsistent.
- Before declaring a multi-page build finished.

## How

```
pip install sameness
sameness page1.html page2.html page3.html          # local files, linked CSS resolved next to them
sameness --site https://staging.example.com --max 20
sameness ... --json report.json --pairs
```

## How to read it

| line | healthy | act on |
|---|---|---|
| `sameness` | below about 0.7 for a site with pages of different kinds | above 0.85: the pages are one template. Vary the skeleton where the content differs (an article is not a landing page). |
| `near-clones` | groups made of one kind of page (all articles, all products) | a group that mixes kinds (home ~ about ~ pricing) |
| `shells` | 1 | 2 or more: unify header, nav and footer before touching anything else. This is the loudest inconsistency a reader sees. |
| `font sets` | 1 | 2 or more: one font stack for the site |
| `palette` | high | low with one shell means colours drift page to page |
| `same meta description` / `same <title>` | none | any: these are defaults that were never written. Write them. |
| `sym` | occasional | `3x3` on every page: the three-cards-three-bullets reflex |

## What to do with the result

1. Fix shells first (one header, one footer, one nav). Then fonts. These are what a reader notices.
2. For near-clone groups that mix page kinds, change the skeleton of the pages whose content is
   different in kind: an article gets a reading column, a catalogue gets a table, a landing page gets
   whatever the product needs, not the same hero-cards-CTA sequence.
3. Replace duplicated titles and descriptions with sentences specific to each page.
4. Re-run and report the before and after numbers, not adjectives.

## Limits

Markup and CSS text only; nothing is rendered. Layout produced by JavaScript, images, and actual visual
similarity are not measured. A high `sameness` among pages of one kind is normal and is not a defect.

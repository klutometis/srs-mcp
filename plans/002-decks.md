# 002 — Decks: remove from the LLM surface, replace with search

Status: **built.** `q` search on `due_cards`/`list_cards`; `deck` dropped from
`add_card` and `edit_card`; column and legacy read filters kept. 18 tests.

Supersedes item 3 of `001-cloze.md` ("expose the deck list"). That fix treated
fragmentation as an authoring-discipline problem. It isn't; the field is.

## What a deck actually is here

One `TEXT NOT NULL DEFAULT 'default'` column. Used in exactly three places:
equality filter in `due_cards`, equality filter in `list_cards`, scope for
`stats` (which also returns the distinct list). **No per-deck scheduling** —
no new-cards/day, no review cap, no per-deck FSRS params.

That last absence is the whole point. Per-deck *policy* is the one thing decks
do in Anki that a tag cannot. Without it, a deck here is precisely: a
single-valued, free-text, exact-match tag with no configuration attached.

No code passes `deck`. Not `seed.py` — `WESTERN_CANON` is `(front, back)`
two-tuples, so every curated card lands in `default`. Not Mneme, not
mcp-gateway. **Every deck name in the DB was invented by an LLM.**

## Three flaws, increasing severity

1. **No vocabulary control → fragmentation is the expected output.** Free-text
   field, stochastic writer, no read-back before write. 22 names / 153 cards;
   **10 names for Horace** covering 97 cards (63% of the deck), across 5
   separator conventions (`Horace`, `Horatius`, `Western Canon / Horatius`,
   `Western Canon::Horatius::Satires`, `Western Canon > Horatius`,
   `Horace - Epistles 1.1`, …), plus `Talks`/`talks`.

2. **Exact match makes the filter silently wrong.** `due_cards(deck="Horace")`
   returns 20 of 97 Horace cards — 21% recall, labelled confidently as your
   Horace cards. Worse than no filter: you cannot tell it under-returned.

3. **Single-valued is a category error for this content.** The Britannica
   cards are genuinely *both* talk-prep and Horace. Deck forces one, so the
   card is unreachable from its other handle. Measured: 5 squarely-Horace
   cards sitting in `Talks`.

## The column is ~redundant with the text

Substring search for `horac|horat` over front+back:

| retrieval method | Horace cards found |
|---|---|
| best single deck filter (`deck='Horace'`) | 20 |
| **text search** | **91** |
| (ground truth: cards in a Horace-named deck) | 97 |

(91 is the regex union `horac|horat`. A single literal `q` gets 89 for
`q='horac'` — "Horatius" doesn't contain "horac" — plus 3 more for `q='horat'`.
Both verified live against Neon. Still 89 vs 20.)

88% recall against the deck labels — and it *corrects* misfiles, catching the
5 in `Talks`. Misses 11, several of which are misfiled anyway (Lucretius cards
in `Western Canon::Horatius::Satires`).

Search trades precision for recall. At this deck size that's the right trade,
and measured precision was fine: 91 hits, ~all genuinely Horace.

## Decision

**Remove `deck` from the LLM surface; replace the capability with `q`.**

- `add_card`: drop the `deck` parameter. Everything → `default`. One less
  decision per call, and the decision was generating pure entropy.
- `edit_card`: drop it too. "Legacy values go inert once nothing writes them"
  only holds if *nothing* writes them; leaving the other write path open would
  keep an unconstrained free-text field in the surface for no gain. Repairing
  a legacy label is now a SQL job, which matches the no-merge-migration call.
- `due_cards` / `list_cards`: add `q`, a case-insensitive substring filter over
  front+back. This is what serves the real use case — "quiz me on Horace on the
  drive home" (Mneme, voice-first).
- **Keep the column and the existing filters.** Costs nothing, breaks nothing,
  preserves the only topical label the 11 text-unfindable cards have. Legacy
  values go inert once nothing writes them.
- **No merge migration.** Collapsing the 10 Horace decks into one destroys
  information to tidy a field we just stopped using.

Roughly the same size of change as the deck-listing fix it replaces (~15 lines).

## Built

- `_SEARCH_SQL` + `_like()`: `LOWER(front || ' ' || back) LIKE ? ESCAPE '\'`,
  one string valid on both backends. `_like()` escapes `\ % _` so a search for
  `100%` or `snake_case` is literal rather than matching everything.
- `q` on `due_cards` and `list_cards`, composable with the legacy `deck=`.
- `add_card`/`edit_card` docstrings now push short answers — the item-2 fix
  from `001-cloze.md`, free to land here since both docstrings were being
  rewritten anyway.
- `tests/` (the repo's first): 18 tests, SQLite-backed, conftest forcibly
  unsets `SRS_DATABASE_URL` so a developer's shell can't point the suite at
  the shared Neon deck and wipe it.
- Postgres path verified read-only against Neon (syntax, `ESCAPE`, and the
  89-vs-20 result); no writes, 153 cards untouched.

Mutation-checked: deleting the escape loop fails exactly the three wildcard
tests, so they discriminate rather than merely pass. (The first draft of the
`%` test passed under mutation — the fixture didn't contain a string that a
stray wildcard would over-match — and was rewritten until it failed.)

Not done: `stats()` still returns the fragmented `decks` list. It's the only
way to discover legacy labels for the legacy filter, and `add_card` can no
longer be tempted by it.

## What this gives up, honestly

Groupings the text does not state — "cards for Thursday's talk." Real, ~7%
here. If that need shows up, the right primitive is **tags**: multi-valued,
added deliberately, with the vocabulary shown at write time. Not single-valued
decks re-litigated.

## Counter-argument considered

A *controlled* 5-deck vocabulary would filter precisely, where `q` is fuzzy.
True. But it needs vocabulary enforcement, a merge migration, and ongoing
discipline from a stochastic writer — to beat search on a 153-card corpus
where search already wins 91 to 20.

# 001 — Cloze deletion

Status: **designed, deliberately not built.** See "Verdict" — the design is
cheap and sound, but it targets a step that isn't the bottleneck. Revisit
once review is happening.

## The idea

Author one sentence with holes in it instead of two fields:

```
nescit vox missa {{reverti}}
→ front: "nescit vox missa [...]"   back: "reverti"
```

## The one structural fact

The schema has **no note/card distinction**: one row = one front/back = one
FSRS state. Anki has cloze *because* it has that layer — one note, N cards,
each hiding a different deletion, each scheduled separately.

Every design below is really answering: do we want 1:N, and where does the
"1" live?

## Three tiers

### A. Authoring sugar, no schema change
`add_card` takes optional `back`; if omitted and the front contains `{{...}}`,
expand into N ordinary rows at insert time. Nothing else changes —
`due_cards`, `grade_card`, `edit_card`, `stats` never learn cloze exists,
because what lands in the table is plain cards.

- ~30 lines + the regex. An hour with the README.
- Loses: siblings don't know each other. Typo fix = N manual edits. No burying.

### B. Sugar + note identity  ← the sweet spot if we build it
Three columns: `note_id`, `cloze_src`, `cloze_ord`. `front`/`back` stay as a
**rendered cache**, so every existing tool and client keeps working unmodified.
`edit_card(card_id, cloze_src=...)` re-renders all siblings; `due_cards` can
bury siblings (dedupe on `note_id` — a seen-set, three lines).

- ~100 lines, one migration. `_migrate()` already has the idempotent
  both-backends pattern to copy. Half a day.

### C. Real `notes` table
Correct, Anki-shaped, out of proportion to a 350-line server. Every query
grows a join to buy a normalization a `note_id` column fakes fine.

## Syntax: markers, not arguments

A *single* cloze is already expressible today —
`add_card("nescit vox missa ___", "reverti")`. Markup buys (a) writing the
sentence once, (b) N cards from one sentence. If we only ever want one blank,
this is a docstring line, not a feature.

`add_cloze(text, hide=["vox missa"])` needs string matching → ambiguous the
moment a word repeats, and can't express "these two blanks are one card."
Markers are positional and unambiguous.

Make it a **superset of Anki's**, nearly free:

| form | meaning |
|---|---|
| `{{word}}` | auto-numbered — the ergonomic case |
| `{{c1::word}}` | explicit ordinal; same ordinal twice = one card, two blanks |
| `{{c1::word::hint}}` | hint shown in the blank |

Pasted Anki notes then just work. Caveat: `{{ }}` collides with
mustache/Jinja if anything downstream ever templates these strings; `[[...]]`
avoids it and loses Anki interop.

Verified parser (20 lines, `re.finditer` + `re.sub`), real output:

```
"{{c1::Nescit}} vox {{c2::missa}} {{c1::reverti}}"
 → ord 1: "[...] vox missa [...]"      back "Nescit, reverti"
 → ord 2: "Nescit vox [...] reverti"   back "missa"
```

## Decisions that will bite

- **What is `back`?** The word (`reverti`) or the restored sentence? Anki shows
  the sentence. Suggest: answer in `back`, full sentence alongside — grading
  against a bare word is cleaner, the sentence is what a human wants to see.
- **TTS.** These get read aloud (voice review is the point). `[...]` is
  unspeakable. Either a blank that reads, or return `type:"cloze"` from
  `due_cards` so the agent knows to say "blank" and read the answer back in
  context.
- **Sibling burying.** A 4-deletion sentence = 4 cards, same day, same
  sentence. Tier A can't bury. Matters more than it sounds.
- **Orphans on edit.** Drop `{{c2::…}}` from a note with history on ordinal 2 →
  suspend the orphan, don't delete. Matches the house style (suspend already
  exists as the non-destructive option).
- **Failure mode.** No `back` *and* no markers → error naming both fixes, or
  we get silent no-op card creation.
- **No tests exist in the repo.** The parser is a pure function with a pile of
  edge cases (nested/unbalanced braces, `::` hint-vs-answer ambiguity, marker
  spanning the whole string). Natural excuse for the first `tests/` — no DB
  needed.

## Verdict — why this is parked

Measured against the live Neon deck on 2026-08-19 (153 cards):

| signal | value |
|---|---|
| cards never reviewed | **111 / 153 (73%)** |
| max reps on *any* card | **3** |
| total reviews, all time | ~62, clustered on demo-rehearsal dates |
| cards created in August | 79 (newest 2026-08-18) |
| median `back` length | **264 chars**; 87% over 120 |
| every due card | 5+ weeks overdue |

Read together:

1. **Authoring isn't the bottleneck.** 79 cards last month. Cloze speeds up the
   step that already works.
2. **Review is broken.** 73% never reviewed once, nothing past 3 reps, the
   August cards have zero. This is a write-only card box.
3. **Cloze makes that worse before better.** One sentence → N cards. Multiplying
   cards into a 111-card backlog grows the backlog faster.
4. **The cards may be unreviewable by construction.** A 264-character answer has
   no crisp did-I-get-it moment, so grading feels bad and doesn't happen —
   especially by voice. These are notes wearing a flashcard costume.

The honest steelman *for* cloze: it's the one feature that structurally forces
a short answer. If the disease is essay-length backs, cloze is a vaccine that
makes the bad card impossible to write. Real — but you can already write
`add_card("nescit vox missa ___", "reverti")` today. The cards are long because
the *authoring instruction* says nothing about length, not because a feature is
missing. Cloze over today's authoring behaviour just yields essays with holes.

Addressable surface, for the record: 32% of cards contain a quoted multi-word
phrase (Latin tags, Britannica lines) — genuine cloze material. But they mostly
ask *about* the quote rather than asking you to produce it. The cloze-native
use case (reciting Odes 1.22 from memory) isn't what the deck is currently for.

## Sequence

1. **Make review happen.** A trigger + a surface. Infrastructure already
   exists (srs on `mcp-gateway`, Mneme voice, "review on the drive home" was
   the original demo dream); what's missing is anything that ever says *you
   have 111 cards due*. Not an srs-mcp feature — a nudge.
2. **Make cards reviewable.** Shrink the answers. This is a docstring/prompt
   change in `add_card`, near-zero code, biggest quality delta.
3. **Deck hygiene** (cheap sleeper, ~15 lines) — **see `002-decks.md`.** The
   deck has ~10 names for Horace across 5 separator conventions, so
   `due_cards(deck=…)` can't select "my Horace cards" (21% recall). The fix
   is *not* exposing the deck list, as originally written here: it's dropping
   `deck` from `add_card` and adding a `q` text filter, which retrieves 91 of
   97 Horace cards where the best deck filter gets 20.
4. **Then cloze** — Tier A or B, on cards that actually get reviewed, by which
   point we'll know which.

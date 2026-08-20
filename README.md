# srs-mcp

Agent-agnostic MCP server for **spaced-repetition learning** — **no Anki
GUI, no Xvfb, no AnkiConnect.** Bring your own agent; this brings the card
box + the scheduler.

It wraps **FSRS** (the [Free Spaced Repetition Scheduler](https://github.com/open-spaced-repetition/py-fsrs),
the same algorithm modern Anki uses) around a tiny SQLite store, so an
agent can author cards, see what's due, and record recall — entirely
headless.

## Why not headless Anki?

Driving the Anki *desktop* app headless means Qt + a virtual framebuffer
(Xvfb) + the AnkiConnect add-on — brittle and version-coupled. The
`anki` PyPI package can drive a real `.anki2` collection GUI-less if you
need interop with your phone's Anki. But if you just want spaced
repetition behind an API, you don't need Anki at all: FSRS is a library,
and this server is ~200 lines around it.

## Tools

- `add_card(front, back) -> {card_id, due}` — author + schedule a card. Keep `back` short — a word or a phrase; a card you can't grade in seconds is a note, not a flashcard
- `due_cards(q=None, limit=20) -> [{card_id, front, back, deck, due}]` — what's due now, optionally narrowed to a topic (`q="horace"`)
- `grade_card(card_id, rating) -> {card_id, rating, next_due, reps}` — record recall (`again`/`hard`/`good`/`easy`, or 1-4)
- `edit_card(card_id, front=None, back=None)` — edit content in place; schedule is preserved (fix typos / shorten a long answer instead of duplicating)
- `suspend_card(card_id)` / `unsuspend_card(card_id)` — shelve a card (kept with its history, removed from the due queue) / restore it
- `list_cards(q=None, limit=50)` — overview regardless of due date
- `delete_card(card_id)` — remove one (reset / cleanup)
- `stats(deck=None) -> {total, due_now, suspended, reviews, decks}`

### Finding cards: search, not decks

Cards are found by **searching their text** — `due_cards(q="horace")` — rather
than by filing them into decks up front. Nothing writes the `deck` field any
more; put the topic in the card itself ("Horace, Odes 1.11: …") and it stays
findable.

Decks were a single-valued, free-text, exact-match label with no per-deck
scheduling attached, so they bought nothing a search doesn't, and cost
accuracy: on the deck this was measured against, agents had invented **ten
names for Horace** across five separator conventions, so the best possible
`deck="Horace"` returned 20 of 97 Horace cards while `q="horac"` returns 89 —
including ones misfiled under `Talks`. The column and the `deck=` filter on
`due_cards`/`list_cards`/`stats` remain for cards labelled by older versions.
See `plans/002-decks.md`.

The review loop: `due_cards` → quiz the user with `front` → check against
`back` → `grade_card`. FSRS computes the next due date from the rating.

## Run

```bash
uv sync
# HTTP (default; for Railway / remote agents)
PORT=8000 uv run srs-mcp
# or stdio (local agent)
MCP_TRANSPORT=stdio uv run srs-mcp
```

## Storage

Two backends, chosen at startup:

- **Postgres (shared deck)** — set `SRS_DATABASE_URL` (or `DATABASE_URL`)
  to a Postgres connection string (e.g. a Neon DB). Every deployment that
  points at the same URL reads/writes **one shared deck**, so you can add
  and review cards from anywhere (local, Railway, etc.). FSRS card ids are
  large, so the `cards.card_id` column is `BIGINT` on Postgres. Requires
  the `psycopg` dependency (already declared).
- **SQLite (fallback)** — when no `*DATABASE_URL` is set, cards live in a
  SQLite file at `SRS_DB` (default `./srs.db`). Single-host / offline. In
  a SQLite-on-Railway setup, mount a volume at `/data` and keep
  `SRS_DB=/data/srs.db` so the box survives redeploys.

The schema is identical (table `cards`) and auto-created on first use.

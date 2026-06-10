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

- `add_card(front, back, deck="default") -> {card_id, due}` — author + schedule a card
- `due_cards(deck=None, limit=20) -> [{card_id, front, back, deck, due}]` — what's due now
- `grade_card(card_id, rating) -> {card_id, rating, next_due, reps}` — record recall (`again`/`hard`/`good`/`easy`, or 1-4)
- `list_cards(deck=None, limit=50)` — overview regardless of due date
- `delete_card(card_id)` — remove one (reset / cleanup)
- `stats(deck=None) -> {total, due_now, reviews, decks}`

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

Cards live in a SQLite file at `SRS_DB` (default `./srs.db`). In prod,
mount a Railway volume at `/data` and keep `SRS_DB=/data/srs.db` so the
box survives redeploys.

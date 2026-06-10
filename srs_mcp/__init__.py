"""srs-mcp — spaced-repetition learning over MCP, no Anki GUI required.

A small, agent-agnostic FSRS card box. Same algorithm modern Anki uses
(Free Spaced Repetition Scheduler), wrapped in five tools:

- add_card(front, back, deck)  : author a card; scheduled immediately.
- due_cards(deck, limit)       : what's due for review right now.
- grade_card(card_id, rating)  : record recall (again/hard/good/easy);
                                 FSRS computes the next due date.
- list_cards / stats           : inspect the box.
- delete_card                  : remove one (reset / cleanup).

Cards live in a SQLite file (SRS_DB, default ./srs.db). In prod, point
SRS_DB at a Railway volume (e.g. /data/srs.db) so they survive redeploys.
No GUI, no Xvfb, no AnkiConnect — just the FSRS scheduler + a tiny store.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fastmcp import FastMCP
from fsrs import Card, Rating, Scheduler

SRS_DB = Path(
    os.environ.get("SRS_DB") or (Path(__file__).resolve().parent.parent / "srs.db")
).resolve()
SRS_DB.parent.mkdir(parents=True, exist_ok=True)

mcp = FastMCP("srs-mcp")
_scheduler = Scheduler()

_RATINGS = {
    "again": Rating.Again,
    "hard": Rating.Hard,
    "good": Rating.Good,
    "easy": Rating.Easy,
    "1": Rating.Again,
    "2": Rating.Hard,
    "3": Rating.Good,
    "4": Rating.Easy,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(SRS_DB)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS cards (
            card_id INTEGER PRIMARY KEY,
            front   TEXT NOT NULL,
            back    TEXT NOT NULL,
            deck    TEXT NOT NULL DEFAULT 'default',
            fsrs    TEXT NOT NULL,
            due     TEXT NOT NULL,
            reps    INTEGER NOT NULL DEFAULT 0,
            created TEXT NOT NULL
        )"""
    )
    return conn


def _due_iso(card: Card) -> str:
    return card.due.astimezone(timezone.utc).isoformat()


@mcp.tool
def add_card(front: str, back: str, deck: str = "default") -> str:
    """Author a new flashcard and schedule it. `front` is the prompt/question,
    `back` is the answer. Optional `deck` groups cards (default 'default').
    Returns JSON {card_id, due}. The card is due immediately (first review)."""
    front = (front or "").strip()
    back = (back or "").strip()
    if not front or not back:
        raise ValueError("front and back are both required")
    card = Card()
    with _db() as conn:
        conn.execute(
            "INSERT INTO cards (card_id, front, back, deck, fsrs, due, reps, created) "
            "VALUES (?, ?, ?, ?, ?, ?, 0, ?)",
            (card.card_id, front, back, deck.strip() or "default",
             card.to_json(), _due_iso(card), _now()),
        )
    return json.dumps({"card_id": card.card_id, "due": _due_iso(card)})


@mcp.tool
def due_cards(deck: str | None = None, limit: int = 20) -> str:
    """List cards due for review now (due <= now), soonest first. Optionally
    filter by `deck`. Returns a JSON array of {card_id, front, back, deck, due}.
    Quiz the user with `front`, check against `back`, then call grade_card.
    Returns '[]' when nothing is due."""
    now = _now()
    q = "SELECT card_id, front, back, deck, due FROM cards WHERE due <= ?"
    args: list = [now]
    if deck:
        q += " AND deck = ?"
        args.append(deck)
    q += " ORDER BY due ASC LIMIT ?"
    args.append(max(1, int(limit)))
    with _db() as conn:
        rows = conn.execute(q, args).fetchall()
    return json.dumps([dict(r) for r in rows])


@mcp.tool
def grade_card(card_id: int, rating: str) -> str:
    """Record a review of a card. `rating` is how well it was recalled:
    'again' (forgot), 'hard', 'good', or 'easy' (1-4 also accepted). FSRS
    updates the schedule; returns JSON {card_id, rating, next_due, reps}."""
    key = str(rating).strip().lower()
    if key not in _RATINGS:
        raise ValueError("rating must be one of: again, hard, good, easy")
    with _db() as conn:
        row = conn.execute(
            "SELECT fsrs, reps FROM cards WHERE card_id = ?", (card_id,)
        ).fetchone()
        if row is None:
            raise FileNotFoundError(f"no card with id {card_id}")
        card = Card.from_json(row["fsrs"])
        card, _log = _scheduler.review_card(card, _RATINGS[key])
        reps = int(row["reps"]) + 1
        conn.execute(
            "UPDATE cards SET fsrs = ?, due = ?, reps = ? WHERE card_id = ?",
            (card.to_json(), _due_iso(card), reps, card_id),
        )
    return json.dumps(
        {"card_id": card_id, "rating": key, "next_due": _due_iso(card), "reps": reps}
    )


@mcp.tool
def list_cards(deck: str | None = None, limit: int = 50) -> str:
    """List cards (newest first) regardless of due date, for an overview.
    Optionally filter by `deck`. Returns JSON array of
    {card_id, front, back, deck, due, reps}."""
    q = "SELECT card_id, front, back, deck, due, reps FROM cards"
    args: list = []
    if deck:
        q += " WHERE deck = ?"
        args.append(deck)
    q += " ORDER BY created DESC LIMIT ?"
    args.append(max(1, int(limit)))
    with _db() as conn:
        rows = conn.execute(q, args).fetchall()
    return json.dumps([dict(r) for r in rows])


@mcp.tool
def delete_card(card_id: int) -> str:
    """Delete a card by id (reset / cleanup)."""
    with _db() as conn:
        cur = conn.execute("DELETE FROM cards WHERE card_id = ?", (card_id,))
    if cur.rowcount == 0:
        raise FileNotFoundError(f"no card with id {card_id}")
    return f"deleted {card_id}"


@mcp.tool
def stats(deck: str | None = None) -> str:
    """Summary of the card box: total cards, how many are due now, total
    reviews, and the deck list. Optionally scope counts to one `deck`."""
    now = _now()
    where = " WHERE deck = ?" if deck else ""
    args = [deck] if deck else []
    with _db() as conn:
        total = conn.execute(f"SELECT COUNT(*) c FROM cards{where}", args).fetchone()["c"]
        due = conn.execute(
            f"SELECT COUNT(*) c FROM cards WHERE due <= ?" + (" AND deck = ?" if deck else ""),
            [now] + args,
        ).fetchone()["c"]
        reps = conn.execute(
            f"SELECT COALESCE(SUM(reps),0) s FROM cards{where}", args
        ).fetchone()["s"]
        decks = [r["deck"] for r in conn.execute(
            "SELECT DISTINCT deck FROM cards ORDER BY deck"
        ).fetchall()]
    return json.dumps({"total": total, "due_now": due, "reviews": reps, "decks": decks})


def main() -> None:
    transport = os.environ.get("MCP_TRANSPORT", "http")
    if transport == "stdio":
        mcp.run()
    else:
        mcp.run(
            transport="http",
            host=os.environ.get("HOST", "0.0.0.0"),
            port=int(os.environ.get("PORT", "8000")),
        )


if __name__ == "__main__":
    main()

"""Topic search (`q`) replacing the deck filter -- see plans/002-decks.md."""

from __future__ import annotations

import inspect
import json

import pytest

import srs_mcp
from srs_mcp import add_card, due_cards, edit_card, list_cards, stats


def add(front: str, back: str) -> int:
    return json.loads(add_card(front, back))["card_id"]


def add_legacy(front: str, back: str, deck: str) -> int:
    """Insert a card carrying an old free-text deck label, the way pre-0.3
    versions did. Nothing in the tool surface can still write these."""
    card_id = add(front, back)
    with srs_mcp._db() as conn:
        conn.execute(
            srs_mcp._q("UPDATE cards SET deck = ? WHERE card_id = ?"), (deck, card_id)
        )
    return card_id


def fronts(payload: str) -> set[str]:
    return {c["front"] for c in json.loads(payload)}


# --- the surface itself ------------------------------------------------------


def test_add_card_takes_no_deck():
    assert "deck" not in inspect.signature(add_card).parameters


def test_edit_card_takes_no_deck():
    assert "deck" not in inspect.signature(edit_card).parameters


def test_new_cards_land_in_default():
    add("Horace, Odes 1.11", "carpe diem")
    assert json.loads(list_cards())[0]["deck"] == "default"


def test_edit_card_with_nothing_to_update_names_the_real_options():
    card_id = add("front", "back")
    with pytest.raises(ValueError, match="front, back"):
        edit_card(card_id)


# --- q: matching -------------------------------------------------------------


def test_q_matches_front_and_back_case_insensitively():
    add("Who wrote 'carpe diem'?", "Horace")  # topic only in the back
    add("Horace, Odes 1.11", "Seize the day")  # topic only in the front
    add("Catullus 85", "odi et amo")  # unrelated
    assert len(json.loads(due_cards(q="horace"))) == 2
    assert len(json.loads(due_cards(q="HORACE"))) == 2


def test_q_is_a_substring_match():
    add("Horatius Flaccus", "the poet")
    assert len(json.loads(due_cards(q="horat"))) == 1


def test_q_no_match_returns_empty():
    add("Catullus 85", "odi et amo")
    assert json.loads(due_cards(q="horace")) == []


def test_q_blank_is_treated_as_absent():
    add("Catullus 85", "odi et amo")
    assert len(json.loads(due_cards(q="   "))) == 1
    assert len(json.loads(due_cards())) == 1


def test_q_applies_to_list_cards_too():
    add("Horace, Odes 1.11", "carpe diem")
    add("Catullus 85", "odi et amo")
    assert fronts(list_cards(q="horace")) == {"Horace, Odes 1.11"}


def test_q_respects_limit():
    for i in range(5):
        add(f"Horace note {i}", "answer")
    assert len(json.loads(due_cards(q="horace", limit=3))) == 3


def test_q_still_excludes_suspended_cards():
    card_id = add("Horace, Odes 1.11", "carpe diem")
    srs_mcp.suspend_card(card_id)
    assert json.loads(due_cards(q="horace")) == []


# --- q: LIKE wildcards must not leak ----------------------------------------


def test_percent_in_query_is_literal():
    add("What share?", "100% of it")
    add("What price?", "1000 sesterces")  # matches if % stayed a wildcard
    assert fronts(due_cards(q="100%")) == {"What share?"}


def test_underscore_in_query_is_literal():
    add("Python naming", "snake_case")
    add("Other naming", "snakeXcase")  # would match if _ stayed a wildcard
    assert fronts(due_cards(q="snake_case")) == {"Python naming"}


def test_backslash_in_query_is_literal():
    add("Escape char", "a\\b")
    add("Unrelated", "ab")
    assert fronts(due_cards(q="a\\b")) == {"Escape char"}


# --- legacy deck filter ------------------------------------------------------


def test_legacy_deck_filter_still_works():
    add_legacy("Horace, Odes 1.11", "carpe diem", "Western Canon::Horatius")
    add("Catullus 85", "odi et amo")
    assert fronts(due_cards(deck="Western Canon::Horatius")) == {"Horace, Odes 1.11"}


def test_q_and_deck_compose():
    add_legacy("Horace, Odes 1.11", "carpe diem", "Talks")
    add_legacy("Catullus 85", "odi et amo", "Talks")
    assert fronts(due_cards(q="horace", deck="Talks")) == {"Horace, Odes 1.11"}


def test_stats_still_reports_legacy_decks():
    add_legacy("Horace, Odes 1.11", "carpe diem", "Western Canon > Horatius")
    assert "Western Canon > Horatius" in json.loads(stats())["decks"]


# --- the regression that motivated the change --------------------------------


def test_search_finds_the_topic_that_fragmented_deck_names_split():
    """The real deck had ten deck names for Horace, so no single exact-match
    `deck` value could retrieve him -- and five squarely-Horace cards sat in
    a 'Talks' deck. One `q` cuts across all of it."""
    for deck in [
        "Horace",
        "Horatius",
        "Western Canon / Horatius",
        "Western Canon::Horatius::Satires",
        "Western Canon > Horatius",
    ]:
        add_legacy(f"Horace, from {deck}", "an answer", deck)
    add_legacy("Horace on the Ars Poetica", "misfiled under talks", "Talks")
    add_legacy("Catullus 85", "odi et amo", "Western Canon")

    assert len(json.loads(due_cards(deck="Horace", limit=50))) == 1
    assert len(json.loads(due_cards(q="horace", limit=50))) == 6

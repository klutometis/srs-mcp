"""Reseed the SRS deck with a curated Western Canon set.

Wipes ALL existing cards, then adds the canonical starter deck. Used by
the demo reset (deck gets polluted during rehearsal — this restores a
clean, known set). Run on the box:  python -m srs_mcp.seed
"""

from __future__ import annotations

from srs_mcp import _db, add_card

# (front, back) — plain text (no markdown) so the TTS reads them cleanly.
WESTERN_CANON: list[tuple[str, str]] = [
    ("Who wrote The Western Canon, and what is his central, provocative claim?",
     "Harold Bloom - that aesthetic power, not politics or morality, is what makes a work canonical, with Shakespeare at its center."),
    ("In Lucretius's On the Nature of Things, what is everything made of, and why does he argue it?",
     "Atoms and void (Epicurean atomism) - to free us from the fear of death and of the gods."),
    ("What is Lucretius's clinamen?",
     "The 'swerve' - a tiny, unpredictable deviation of falling atoms that makes free will and the birth of worlds possible. Bloom borrowed it as a metaphor for poetic misreading."),
    ("Lucian of Samosata's A True History is remembered as a 'first' of what?",
     "An early ancestor of science fiction - a deliberately absurd travel tale featuring a voyage to the Moon and a war between its kingdoms."),
    ("In Plutarch's Parallel Lives, which Greek is paired with the Roman Brutus, and why does the Life of Brutus matter?",
     "Dion of Syracuse. The Life of Brutus is a major source for Caesar's assassination, and for Shakespeare's Julius Caesar."),
    ("What does Harold Bloom mean by 'the anxiety of influence'?",
     "Strong poets must creatively misread their great precursors (misprision) to clear imaginative space of their own - influence as struggle, not mere borrowing."),
    ("Who guides Dante through Hell and Purgatory in the Divine Comedy, and who takes over for Paradise?",
     "Virgil, author of the Aeneid, guides him through Hell and Purgatory; Beatrice leads him through Paradise."),
    ("Montaigne is credited with inventing which literary form, and what is its motto?",
     "The essay (essai, 'an attempt'). His motto: 'Que sais-je?' - 'What do I know?'"),
    ("What is the Epicurean tetrapharmakos, the 'four-part cure'?",
     "Don't fear god; don't worry about death; what is good is easy to get; what is terrible is easy to endure."),
    ("In Auerbach's Mimesis, what two styles of representing reality does he contrast in chapter one?",
     "Homer's scar of Odysseus (everything foregrounded, fully lit) versus the biblical binding of Isaac ('fraught with background,' withholding)."),
    ("Cervantes's Don Quixote is often called the first what, and why?",
     "The first modern novel - Bloom pairs it with Shakespeare at the canon's center; it invents interiority through the living dialogue of Quixote and Sancho."),
    ("In Goethe's Faust, what is the wager with Mephistopheles?",
     "Faust bets his soul that no passing moment will ever tempt him to say 'Stay, you are so beautiful.' Restless striving itself becomes his salvation."),
]


def reseed() -> int:
    """Delete all cards, then add the curated set. Returns the count added."""
    with _db() as conn:
        conn.execute("DELETE FROM cards")
    add = getattr(add_card, "fn", add_card)
    for front, back in WESTERN_CANON:
        add(front, back)
    return len(WESTERN_CANON)


def main() -> None:
    n = reseed()
    print(f"reseeded {n} cards (Western Canon)")


if __name__ == "__main__":
    main()

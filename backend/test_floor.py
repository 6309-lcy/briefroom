"""Fair speaker rotation: the quiet analyst must not be starved."""

from app.room import pick_panelist


def panel():
    return [
        {"id": "p0", "name": "Priya", "talkativeness": 0.55, "interrupt_p": 0.08},
        {"id": "p1", "name": "James", "talkativeness": 0.85, "interrupt_p": 0.62},
        {"id": "p2", "name": "Maya", "talkativeness": 0.4, "interrupt_p": 0.28},
    ]


def test_prefer_is_binding():
    got = pick_panelist(panel(), prefer="p2", last_speaker="p0", transcript=[], interrupt=False)
    assert got["id"] == "p2"


def test_everyone_speaks_before_repeat():
    people = panel()
    transcript = []
    last = ""
    seen = []
    for _ in range(6):
        choice = pick_panelist(people, prefer=None, last_speaker=last, transcript=transcript, interrupt=False)
        seen.append(choice["id"])
        transcript.append({"speaker_id": choice["id"]})
        last = choice["id"]
    first_three = set(seen[:3])
    second_three = set(seen[3:6])
    assert first_three == {"p0", "p1", "p2"}, first_three
    assert second_three == {"p0", "p1", "p2"}, second_three


def test_never_same_twice_in_a_row_when_others_exist():
    people = panel()
    last = "p1"
    for _ in range(20):
        choice = pick_panelist(
            people,
            prefer=None,
            last_speaker=last,
            transcript=[{"speaker_id": last}],
            interrupt=False,
        )
        assert choice["id"] != last
        last = choice["id"]


def test_pack_transcript_stays_under_budget():
    from app.graph.compose import pack_transcript
    from app.llm import estimate_tokens

    turns = []
    for i in range(80):
        turns.append(
            {
                "id": f"u{i}",
                "speaker_id": "user",
                "speaker_name": "Alex",
                "text": "I think the client should delay the rollout because " + ("margin " * 40),
                "phase": "discussion",
                "ts": i,
            }
        )
        turns.append(
            {
                "id": f"a{i}",
                "speaker_id": "p1",
                "speaker_name": "James",
                "text": "Hold on that's not what exhibit B says " + ("point " * 40),
                "phase": "discussion",
                "interrupt": i % 5 == 0,
                "ts": i + 0.5,
            }
        )
    packed = pack_transcript(turns, 1500)
    assert estimate_tokens(packed) <= 1500 + 40
    assert "Alex:" in packed
    assert "Candidate lines" in packed


def test_merge_competencies_fills_all_six():
    from app.graph.compose import _merge_competencies

    a = [{"id": "structure", "score": 4, "note": "opened with the ask"}]
    b = [{"id": "teamwork", "score": 2, "note": "talked over Priya"}]
    rows = _merge_competencies(a, b, {"speaking_pattern": "short"})
    ids = [r["id"] for r in rows]
    assert ids == [
        "structure",
        "commercial",
        "insight",
        "influence",
        "teamwork",
        "composure",
    ]
    assert rows[0]["score"] == 4
    assert rows[4]["score"] == 2
    assert all(1 <= r["score"] <= 5 for r in rows)


if __name__ == "__main__":
    test_prefer_is_binding()
    test_everyone_speaks_before_repeat()
    test_never_same_twice_in_a_row_when_others_exist()
    test_merge_competencies_fills_all_six()
    test_pack_transcript_stays_under_budget()
    print("ok")

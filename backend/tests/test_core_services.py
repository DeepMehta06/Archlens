"""Unit tests for the deterministic core: WhatsApp parsing, chunking, hedges, verification, RRF."""
from app.enums import VerificationStatus
from app.services.chunking import chunk_units, units_from_chat, units_from_plain
from app.services.evidence_verification import (
    locate_phrase,
    quote_from_units,
    resolve_units,
    verify_quote,
)
from app.services.hedging import find_hedges
from app.services.rrf import reciprocal_rank_fusion
from app.services.whatsapp_parser import parse_whatsapp

ANDROID = """12/03/2026, 14:05 - Messages and calls are end-to-end encrypted. No one outside of this chat can read them.
12/03/2026, 14:06 - Rahul: Bhai hume ek app chahiye
jisme patients appointment book kar sake
12/03/2026, 14:07 - Riya: Payment kaise lena hai?
12/03/2026, 14:08 - Rahul: UPI se lena hai, COD shayad baad me
12/03/2026, 14:09 - Rahul: <Media omitted>
"""

IOS = """[13/03/26, 2:05:33 PM] Rahul: Need refunds within 7 days
[13/03/26, 2:06:10 PM] Riya: Okay noted
"""


def test_android_export_is_parsed_with_multiline_system_and_media_handling():
    chat = parse_whatsapp(ANDROID)

    assert chat is not None
    assert chat.participants == ["Rahul", "Riya"]
    assert chat.skipped_system == 1
    assert chat.skipped_media == 1
    first = chat.content_messages[0]
    assert first.sender == "Rahul"
    assert first.text == "Bhai hume ek app chahiye\njisme patients appointment book kar sake"
    assert chat.day_first is True
    assert chat.date_ambiguous is True
    assert first.timestamp.day == 12 and first.timestamp.month == 3


def test_ios_export_with_twelve_hour_clock():
    chat = parse_whatsapp(IOS)

    assert chat is not None
    assert chat.content_messages[0].timestamp.hour == 14
    assert chat.content_messages[0].timestamp.year == 2026
    assert chat.day_first is True


def test_month_first_is_detected_when_second_component_exceeds_twelve():
    chat = parse_whatsapp("03/25/2026, 10:00 - A: hello there\n03/26/2026, 10:01 - B: hi back\n")

    assert chat is not None
    assert chat.day_first is False
    assert chat.content_messages[0].timestamp.month == 3
    assert chat.content_messages[0].timestamp.day == 25


def test_ambiguous_dates_are_flagged_not_hidden():
    chat = parse_whatsapp("03/04/2026, 10:00 - A: hello there\n03/04/2026, 10:01 - B: hi back\n")

    assert chat is not None
    assert chat.date_ambiguous is True


def test_plain_text_is_not_mistaken_for_whatsapp():
    assert parse_whatsapp("We need an app.\nIt should take UPI payments.\nDeadline is 8 weeks.") is None
    assert parse_whatsapp("") is None


def test_chunks_number_units_from_one_and_respect_the_size_target():
    chat = parse_whatsapp(ANDROID)
    units = units_from_chat(chat)

    chunks = chunk_units(units, target_chars=60)

    assert len(chunks) >= 2
    assert [u.n for u in chunks[0].units] == list(range(1, len(chunks[0].units) + 1))
    assert all(c.units and c.content_hash for c in chunks)
    assert chunks[0].text.startswith("Rahul: Bhai hume")


def test_plain_text_is_split_into_units_and_long_paragraphs_into_sentences():
    long_paragraph = " ".join(f"Sentence number {i} is here." for i in range(40))

    units = units_from_plain("Short line one.\n\n" + long_paragraph)

    assert units[0].text == "Short line one."
    assert len(units) > 5
    assert all(len(u.text) <= 400 for u in units)


def test_hedges_in_english_hinglish_and_devanagari():
    assert "shayad" in find_hedges("COD shayad baad me dekhte hain")
    assert "baad me" in find_hedges("COD shayad baad me dekhte hain")
    assert "not sure" in find_hedges("The client is Not Sure about cards")
    assert find_hedges("शायद कल आऊंगा") == ["शायद"]
    assert find_hedges("UPI se lena hai") == []
    assert find_hedges("The probabilistic model") == []


def test_exact_quote_verifies_and_a_fabricated_quote_does_not():
    source = "Rahul: UPI se lena hai,\n  COD   shayad baad me"

    ok, _ = verify_quote("COD shayad baad me", source)
    bad, note = verify_quote("COD zaroor chahiye", source)

    assert ok == VerificationStatus.VERIFIED
    assert bad == VerificationStatus.UNVERIFIED
    assert "not found" in note
    assert verify_quote("", source)[0] == VerificationStatus.UNVERIFIED


def test_unit_citations_resolve_and_invalid_numbers_are_reported():
    units = [{"n": 1, "text": "UPI se lena hai"}, {"n": 2, "text": "COD shayad"}]

    valid, invalid = resolve_units(units, [2, 2, 9, 1])

    assert [u["n"] for u in valid] == [2, 1]
    assert invalid == [9]
    assert quote_from_units(valid) == "COD shayad\nUPI se lena hai"


def test_phrase_highlight_must_exist_inside_the_cited_units():
    units = [{"n": 1, "text": "UPI se lena hai"}]

    assert locate_phrase("upi se lena", units) == "upi se lena"
    assert locate_phrase("credit card", units) is None
    assert locate_phrase(None, units) is None


def test_rrf_rewards_candidates_present_in_both_channels():
    fused = reciprocal_rank_fusion(
        {"bm25": ["a", "b", "c"], "dense": ["b", "d", "a"]}, k=60
    )

    order = [h.id for h in fused]
    assert order[0] == "b"
    assert order.index("a") < order.index("c")
    assert order.index("a") < order.index("d")
    top = fused[0]
    assert top.ranks == {"bm25": 2, "dense": 1}
    assert abs(top.score - (1 / 62 + 1 / 61)) < 1e-12


def test_rrf_handles_a_single_channel_and_empty_input():
    assert [h.id for h in reciprocal_rank_fusion({"bm25": ["x", "y"]})] == ["x", "y"]
    assert reciprocal_rank_fusion({"bm25": [], "dense": []}) == []


def test_rrf_ignores_duplicate_candidates_within_one_channel():
    fused = reciprocal_rank_fusion({"bm25": ["a", "a", "b"]}, k=60)

    assert [h.id for h in fused] == ["a", "b"]
    assert fused[1].ranks["bm25"] == 2


def test_rrf_channel_weight_changes_the_winner():
    from app.services.rrf import reciprocal_rank_fusion

    rankings = {"bm25": ["a", "b"], "dense": ["b", "a"]}
    assert reciprocal_rank_fusion(rankings)[0].id == "a"
    assert reciprocal_rank_fusion(rankings, weights={"dense": 2.0})[0].id == "b"

from retrieval.search import (
    MAX_SNIPPET_CHARS,
    _keyword_overlap_boost,
    _looks_noisy,
    _normalize_text,
)


def test_numeric_tables_are_noisy():
    assert _looks_noisy("12 34 56 78 90 11 22 33 44 55")
    assert _looks_noisy("   ")


def test_prose_is_not_noisy():
    assert not _looks_noisy("The trip to Goa is planned for the 12th of December.")


def test_keyword_boost_scales_with_overlap():
    full = _keyword_overlap_boost("trip goa", "Our trip to Goa was great")
    half = _keyword_overlap_boost("trip paris", "Our trip to Goa was great")
    none = _keyword_overlap_boost("invoice", "Our trip to Goa was great")

    assert full > half > none == 0.0


def test_normalize_text_collapses_whitespace_and_truncates():
    assert _normalize_text("a\n\n  b\tc") == "a b c"
    long_text = "word " * 500
    assert len(_normalize_text(long_text)) <= MAX_SNIPPET_CHARS + 3

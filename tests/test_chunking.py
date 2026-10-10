from ingestion.chunking import chunk_text


def test_empty_text_gives_no_chunks():
    assert chunk_text("") == []


def test_short_text_is_one_chunk():
    assert chunk_text("One sentence. Another one.") == ["One sentence. Another one."]


def test_long_text_is_split_with_overlap():
    sentences = [f"Sentence number {i} talks about topic {i}." for i in range(60)]
    chunks = chunk_text(" ".join(sentences), chunk_size=200, overlap=50)

    assert len(chunks) > 1
    # A chunk can exceed chunk_size only by the carried-over overlap.
    assert all(len(c) <= 200 + 50 + 1 for c in chunks)
    # Each chunk starts with the tail of the previous one.
    for prev, cur in zip(chunks, chunks[1:]):
        assert prev[-20:].strip() in cur


def test_sentences_are_not_cut():
    sentences = [f"Fact {i} is here." for i in range(50)]
    for chunk in chunk_text(" ".join(sentences), chunk_size=100, overlap=0):
        assert chunk.endswith(".")

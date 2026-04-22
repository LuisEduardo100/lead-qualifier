import json
import pytest
from unittest.mock import patch, MagicMock
from backend.models import AgentDocument, DocumentChunk


@pytest.mark.asyncio
async def test_search_no_active_document_returns_empty(db_session):
    from backend.services.rag import search_relevant_chunks

    result = await search_relevant_chunks("qualquer coisa", db_session)
    assert result == []


@pytest.mark.asyncio
async def test_search_returns_keyword_matched_chunks(db_session):
    from backend.services.rag import search_relevant_chunks

    doc = AgentDocument(filename="cat.pdf", file_path="/fake/cat.pdf", is_active=True)
    db_session.add(doc)
    await db_session.flush()
    db_session.add(DocumentChunk(document_id=doc.id, page_number=1, chunk_text="produto principal com desconto"))
    db_session.add(DocumentChunk(document_id=doc.id, page_number=2, chunk_text="outros itens disponíveis aqui"))
    await db_session.commit()

    result = await search_relevant_chunks("produto principal", db_session)
    assert len(result) >= 1
    assert any("produto" in r.lower() for r in result)


@pytest.mark.asyncio
async def test_search_ranks_better_matches_first(db_session):
    from backend.services.rag import search_relevant_chunks

    doc = AgentDocument(filename="rank.pdf", file_path="/fake/rank.pdf", is_active=True)
    db_session.add(doc)
    await db_session.flush()
    db_session.add(DocumentChunk(document_id=doc.id, page_number=1, chunk_text="solar energia paineis solares energia"))
    db_session.add(DocumentChunk(document_id=doc.id, page_number=2, chunk_text="energia elétrica"))
    await db_session.commit()

    result = await search_relevant_chunks("paineis solares energia", db_session)
    # Page 1 has more matching words → should appear first
    assert len(result) >= 1
    assert "solar" in result[0].lower() or "paineis" in result[0].lower()


@pytest.mark.asyncio
async def test_search_short_query_returns_top_k_without_filter(db_session):
    from backend.services.rag import search_relevant_chunks

    doc = AgentDocument(filename="top.pdf", file_path="/fake/top.pdf", is_active=True)
    db_session.add(doc)
    await db_session.flush()
    for i in range(5):
        db_session.add(DocumentChunk(document_id=doc.id, page_number=i + 1, chunk_text=f"chunk numero {i + 1}"))
    await db_session.commit()

    # All words <= 3 chars → no word filter → returns first top_k chunks
    result = await search_relevant_chunks("hi", db_session, top_k=3)
    assert len(result) == 3


@pytest.mark.asyncio
async def test_get_active_document_returns_none_when_empty(db_session):
    from backend.services.rag import get_active_document

    result = await get_active_document(db_session)
    assert result is None


@pytest.mark.asyncio
async def test_get_active_document_returns_active(db_session):
    from backend.services.rag import get_active_document

    doc = AgentDocument(filename="active.pdf", file_path="/fake/active.pdf", is_active=True)
    db_session.add(doc)
    await db_session.commit()

    result = await get_active_document(db_session)
    assert result is not None
    assert result.filename == "active.pdf"


def test_extract_chunks_from_pdf_returns_page_tuples():
    from backend.services.rag import extract_chunks_from_pdf

    mock_page1 = MagicMock()
    mock_page1.extract_text.return_value = "Texto da primeira página com conteúdo suficiente para ser indexado"
    mock_page2 = MagicMock()
    mock_page2.extract_text.return_value = "  "  # blank → excluded
    mock_page3 = MagicMock()
    mock_page3.extract_text.return_value = "Texto da terceira página com bastante conteúdo relevante aqui"

    mock_reader = MagicMock()
    mock_reader.pages = [mock_page1, mock_page2, mock_page3]

    with patch("pypdf.PdfReader", return_value=mock_reader):
        result = extract_chunks_from_pdf("/fake/file.pdf")

    assert len(result) == 2
    assert result[0][0] == 1
    assert result[1][0] == 3


def test_extract_chunks_skips_title_only_pages():
    """Chunks with fewer than _MIN_CHUNK_WORDS words are excluded at ingestion."""
    from backend.services.rag import extract_chunks_from_pdf

    mock_title = MagicMock()
    mock_title.extract_text.return_value = "CATÁLOGO DE ILUMINAÇÃO"  # 3 words — title only
    mock_content = MagicMock()
    mock_content.extract_text.return_value = (
        "Lustre de teto para sala de jantar em cristal com 6 lâmpadas LED disponível em dourado e cromado"
    )

    mock_reader = MagicMock()
    mock_reader.pages = [mock_title, mock_content]

    with patch("pypdf.PdfReader", return_value=mock_reader):
        result = extract_chunks_from_pdf("/fake/catalog.pdf")

    assert len(result) == 1
    assert result[0][0] == 2  # only the content page, page 1 (title) was skipped
    assert "lustre" in result[0][1].lower()


def test_extract_chunks_skips_exactly_min_words_minus_one():
    """A page with exactly _MIN_CHUNK_WORDS - 1 words is filtered out."""
    from backend.services.rag import extract_chunks_from_pdf, _MIN_CHUNK_WORDS

    short_text = " ".join(["palavra"] * (_MIN_CHUNK_WORDS - 1))
    long_text = " ".join(["palavra"] * _MIN_CHUNK_WORDS)

    mock_short = MagicMock()
    mock_short.extract_text.return_value = short_text
    mock_long = MagicMock()
    mock_long.extract_text.return_value = long_text

    mock_reader = MagicMock()
    mock_reader.pages = [mock_short, mock_long]

    with patch("pypdf.PdfReader", return_value=mock_reader):
        result = extract_chunks_from_pdf("/fake/boundary.pdf")

    assert len(result) == 1
    assert result[0][0] == 2


@pytest.mark.asyncio
async def test_semantic_search_filters_low_similarity(db_session):
    """Chunks with cosine similarity below _MIN_SIMILARITY are excluded from results."""
    from backend.services.rag import search_relevant_chunks, _MIN_SIMILARITY

    doc = AgentDocument(filename="sem.pdf", file_path="/fake/sem.pdf", is_active=True)
    db_session.add(doc)
    await db_session.flush()

    # Two chunks with pre-baked embeddings
    high_vec = [1.0, 0.0, 0.0]
    low_vec  = [0.0, 1.0, 0.0]   # orthogonal → similarity ≈ 0 with query

    db_session.add(DocumentChunk(
        document_id=doc.id, page_number=1,
        chunk_text="chunk relevante",
        embedding=json.dumps(high_vec),
    ))
    db_session.add(DocumentChunk(
        document_id=doc.id, page_number=2,
        chunk_text="chunk irrelevante",
        embedding=json.dumps(low_vec),
    ))
    await db_session.commit()

    # Query embedding aligned with high_vec → similarity 1.0 vs 0.0
    query_vec = [1.0, 0.0, 0.0]

    async def fake_embed(text):
        return query_vec

    import backend.services.rag as rag_mod
    original = rag_mod.embed_text
    rag_mod.embed_text = fake_embed
    try:
        result = await search_relevant_chunks("qualquer", db_session, top_k=3)
    finally:
        rag_mod.embed_text = original

    assert len(result) == 1
    assert "relevante" in result[0]
    assert "irrelevante" not in result[0]


@pytest.mark.asyncio
async def test_semantic_search_returns_empty_when_all_below_threshold(db_session):
    """Returns [] when all chunks are below the similarity threshold."""
    from backend.services.rag import search_relevant_chunks

    doc = AgentDocument(filename="low.pdf", file_path="/fake/low.pdf", is_active=True)
    db_session.add(doc)
    await db_session.flush()

    # Orthogonal chunk → similarity 0.0 with query
    db_session.add(DocumentChunk(
        document_id=doc.id, page_number=1,
        chunk_text="algo completamente diferente",
        embedding=json.dumps([0.0, 1.0, 0.0]),
    ))
    await db_session.commit()

    async def fake_embed(text):
        return [1.0, 0.0, 0.0]

    import backend.services.rag as rag_mod
    original = rag_mod.embed_text
    rag_mod.embed_text = fake_embed
    try:
        result = await search_relevant_chunks("sala de jantar", db_session, top_k=3)
    finally:
        rag_mod.embed_text = original

    assert result == []

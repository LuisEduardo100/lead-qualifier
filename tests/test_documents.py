import pytest
from backend.models import AgentDocument


@pytest.mark.asyncio
async def test_list_documents_empty(client, auth_headers):
    r = await client.get("/api/documents", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_list_documents_returns_data(client, auth_headers, db_session):
    doc = AgentDocument(
        filename="cat.pdf",
        file_path="/fake/cat.pdf",
        original_size=1024,
        page_count=3,
        is_active=True,
    )
    db_session.add(doc)
    await db_session.commit()

    r = await client.get("/api/documents", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["filename"] == "cat.pdf"
    assert data[0]["page_count"] == 3
    assert data[0]["is_active"] is True


@pytest.mark.asyncio
async def test_upload_non_pdf_rejected(client, auth_headers):
    r = await client.post(
        "/api/documents/upload",
        files={"file": ("report.docx", b"fake content", "application/octet-stream")},
        headers=auth_headers,
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_upload_pdf_success(client, auth_headers, monkeypatch, tmp_path):
    import backend.routers.documents as doc_mod

    monkeypatch.setattr(doc_mod, "DOCS_DIR", tmp_path)
    monkeypatch.setattr(doc_mod, "extract_chunks_from_pdf", lambda path: [(1, "Conteúdo página 1"), (2, "Conteúdo página 2")])

    r = await client.post(
        "/api/documents/upload",
        files={"file": ("catalogo.pdf", b"%PDF-fake-content", "application/pdf")},
        headers=auth_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["filename"] == "catalogo.pdf"
    assert data["page_count"] == 2


@pytest.mark.asyncio
async def test_upload_pdf_empty_chunks_rejected(client, auth_headers, monkeypatch, tmp_path):
    import backend.routers.documents as doc_mod

    monkeypatch.setattr(doc_mod, "DOCS_DIR", tmp_path)
    monkeypatch.setattr(doc_mod, "extract_chunks_from_pdf", lambda path: [])

    r = await client.post(
        "/api/documents/upload",
        files={"file": ("scanned.pdf", b"%PDF-fake", "application/pdf")},
        headers=auth_headers,
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_upload_pdf_replaces_active_document(client, auth_headers, db_session, monkeypatch, tmp_path):
    import backend.routers.documents as doc_mod

    old_doc = AgentDocument(
        filename="old.pdf", file_path="/fake/old.pdf", original_size=512, page_count=1, is_active=True
    )
    db_session.add(old_doc)
    await db_session.commit()

    monkeypatch.setattr(doc_mod, "DOCS_DIR", tmp_path)
    monkeypatch.setattr(doc_mod, "extract_chunks_from_pdf", lambda path: [(1, "Novo conteúdo")])

    r = await client.post(
        "/api/documents/upload",
        files={"file": ("new.pdf", b"%PDF-new", "application/pdf")},
        headers=auth_headers,
    )
    assert r.status_code == 200

    await db_session.refresh(old_doc)
    assert old_doc.is_active is False


@pytest.mark.asyncio
async def test_delete_document_not_found(client, auth_headers):
    r = await client.delete("/api/documents/99999", headers=auth_headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_document_success(client, auth_headers, db_session):
    doc = AgentDocument(
        filename="to_delete.pdf",
        file_path="/nonexistent/to_delete.pdf",
        original_size=100,
        page_count=1,
        is_active=False,
    )
    db_session.add(doc)
    await db_session.commit()
    doc_id = doc.id

    r = await client.delete(f"/api/documents/{doc_id}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["ok"] is True

    from sqlalchemy import select
    remaining = (await db_session.execute(
        select(AgentDocument).where(AgentDocument.id == doc_id)
    )).scalar_one_or_none()
    assert remaining is None

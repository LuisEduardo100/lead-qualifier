import base64
import logging
from pathlib import Path
from datetime import datetime, UTC

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import AgentDocument, DocumentChunk
from backend.auth import get_current_user
from backend.services.rag import extract_chunks_from_pdf

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["documents"])

DOCS_DIR = Path("data/documents")


@router.get("")
async def list_documents(db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    docs = (await db.execute(
        select(AgentDocument).order_by(AgentDocument.uploaded_at.desc())
    )).scalars().all()
    return [
        {
            "id": d.id,
            "filename": d.filename,
            "page_count": d.page_count,
            "original_size": d.original_size,
            "is_active": d.is_active,
            "uploaded_at": d.uploaded_at.isoformat(),
        }
        for d in docs
    ]


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "Apenas arquivos PDF são aceitos")

    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    safe_name = f"{datetime.now(UTC).timestamp():.0f}_{file.filename}"
    file_path = DOCS_DIR / safe_name
    content = await file.read()
    file_path.write_bytes(content)

    try:
        chunks = extract_chunks_from_pdf(str(file_path))
    except Exception as e:
        file_path.unlink(missing_ok=True)
        raise HTTPException(500, f"Falha ao processar PDF: {e}")

    if not chunks:
        file_path.unlink(missing_ok=True)
        raise HTTPException(400, "Não foi possível extrair texto do PDF. Verifique se não é um PDF escaneado sem OCR.")

    # Deactivate all existing documents
    existing = (await db.execute(select(AgentDocument))).scalars().all()
    for doc in existing:
        doc.is_active = False

    doc = AgentDocument(
        filename=file.filename,
        file_path=str(file_path),
        original_size=len(content),
        page_count=len(chunks),
        is_active=True,
    )
    db.add(doc)
    await db.flush()

    from backend.services.rag import embed_text
    import json as _json
    for page_num, text in chunks:
        try:
            vec = await embed_text(text)
            embedding = _json.dumps(vec)
        except Exception as e:
            logger.warning(f"Embedding failed for page {page_num}: {e}")
            embedding = None
        db.add(DocumentChunk(document_id=doc.id, page_number=page_num, chunk_text=text, embedding=embedding))

    await db.commit()
    logger.info(f"Document uploaded: {file.filename} — {len(chunks)} pages indexed")
    return {"id": doc.id, "filename": doc.filename, "page_count": doc.page_count}


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    doc = (await db.execute(
        select(AgentDocument).where(AgentDocument.id == doc_id)
    )).scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Documento não encontrado")

    try:
        Path(doc.file_path).unlink(missing_ok=True)
    except Exception as e:
        logger.warning(f"Could not delete file {doc.file_path}: {e}")

    await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == doc_id))
    await db.delete(doc)
    await db.commit()
    return {"ok": True}


@router.get("/{doc_id}/base64")
async def get_document_base64(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Returns the PDF as base64 for internal use (e.g. sending via Evolution API)."""
    doc = (await db.execute(
        select(AgentDocument).where(AgentDocument.id == doc_id)
    )).scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Documento não encontrado")

    file_path = Path(doc.file_path)
    if not file_path.exists():
        raise HTTPException(404, "Arquivo não encontrado no disco")

    encoded = base64.b64encode(file_path.read_bytes()).decode()
    return {"filename": doc.filename, "base64": encoded}

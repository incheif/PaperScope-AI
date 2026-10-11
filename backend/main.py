import os
import time
import uuid
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, UploadFile, File, Form, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel
from dotenv import load_dotenv

from parser import PDFParser
from rag import VectorIndex
from llm_service import LLMService

load_dotenv()

app = FastAPI(
    title="PaperScope AI API",
    description="Enterprise-grade academic document analysis & conversational RAG engine",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Multi-user session-aware storage: session_id -> { paper_id -> paper_obj }
SESSIONS_STORE: Dict[str, Dict[str, Any]] = {}
DEFAULT_SESSION_ID = "default"

def get_session_store(session_id: Optional[str] = None) -> Dict[str, Any]:
    sid = (session_id or "").strip() or DEFAULT_SESSION_ID
    if sid not in SESSIONS_STORE:
        SESSIONS_STORE[sid] = {}
    return SESSIONS_STORE[sid]

def find_paper_anywhere(paper_id: str, preferred_store: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if paper_id in preferred_store:
        return preferred_store[paper_id]
    for s in SESSIONS_STORE.values():
        if paper_id in s:
            return s[paper_id]
    return None

class ChatRequest(BaseModel):
    paper_id: Optional[str] = "all"
    message: str
    highlighted_text: Optional[str] = None
    highlight_page: Optional[int] = None
    history: Optional[List[Dict[str, str]]] = []
    provider: Optional[str] = "gemini"
    model: Optional[str] = "gemini-2.5-flash"
    api_key: Optional[str] = None
    top_k: Optional[int] = 5
    session_id: Optional[str] = None

class ExportRequest(BaseModel):
    paper_id: Optional[str] = "all"
    chat_history: Optional[List[Dict[str, str]]] = []
    session_id: Optional[str] = None

def resolve_credentials(header_gemini: Optional[str], header_groq: Optional[str], body_key: Optional[str] = None):
    candidate = (body_key or "").strip()
    gemini_key = (header_gemini or os.environ.get("GOOGLE_API_KEY", "")).strip()
    groq_key = (header_groq or os.environ.get("GROQ_API_KEY", "")).strip()

    if candidate:
        if candidate.startswith("gsk_"):
            groq_key = candidate
        else:
            gemini_key = candidate

    return gemini_key, groq_key

@app.get("/api/health")
async def health_check():
    has_gemini = bool(os.environ.get("GOOGLE_API_KEY"))
    has_groq = bool(os.environ.get("GROQ_API_KEY"))
    total_papers = sum(len([p for pid, p in s.items() if pid != "all"]) for s in SESSIONS_STORE.values())
    return {
        "status": "healthy",
        "version": "2.0.0",
        "active_sessions_count": len(SESSIONS_STORE),
        "active_papers_count": total_papers,
        "keys_configured": {
            "google_gemini": has_gemini,
            "groq": has_groq
        },
        "available_chunking_strategies": [
            {"id": "balanced", "name": "Balanced Paragraph (900 chars)", "description": "Standard balanced context for general academic papers"},
            {"id": "fine_grained", "name": "Fine-Grained Sentences (450 chars)", "description": "High-precision retrieval for metrics & formulas"},
            {"id": "coarse", "name": "Coarse Deep Context (1800 chars)", "description": "Extended context for theoretical methods & proofs"},
            {"id": "section_aware", "name": "Section-Aware Academic", "description": "Strict boundary isolation by paper section headers"}
        ],
        "available_models": [
            {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash (Ultra Fast & Recommended)", "provider": "gemini"},
            {"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro (Deep Reasoning)", "provider": "gemini"},
            {"id": "gemini-flash-latest", "name": "Gemini Flash Latest", "provider": "gemini"},
            {"id": "llama-3.3-70b-versatile", "name": "Llama 3.3 70B (Groq Fast)", "provider": "groq"}
        ]
    }

@app.post("/api/upload")
async def upload_papers(
    files: Optional[List[UploadFile]] = File(None),
    file: Optional[UploadFile] = File(None),
    x_gemini_key: Optional[str] = Header(None),
    x_groq_key: Optional[str] = Header(None),
    x_session_id: Optional[str] = Header(None),
    client_api_key: Optional[str] = Form(None),
    session_id: Optional[str] = Form(None),
    chunking_strategy: Optional[str] = Form("balanced"),
    chunk_size: Optional[int] = Form(None),
    chunk_overlap: Optional[int] = Form(None)
):
    upload_list = files or ([file] if file else [])
    if not upload_list:
        raise HTTPException(status_code=400, detail="No PDF files uploaded.")

    sid = (session_id or x_session_id or "").strip() or DEFAULT_SESSION_ID
    current_store = get_session_store(sid)

    gemini_key, groq_key = resolve_credentials(x_gemini_key, x_groq_key, client_api_key)
    llm = LLMService(google_api_key=gemini_key, groq_api_key=groq_key)

    processed_papers = []
    all_chunks = []

    for f in upload_list:
        if not f.filename.lower().endswith(".pdf"):
            continue

        file_bytes = await f.read()
        if len(file_bytes) == 0:
            continue

        paper_id = str(uuid.uuid4())[:8]
        pages_data = PDFParser.extract_text_by_pages(file_bytes)
        if not pages_data or all(len(p["text"]) == 0 for p in pages_data):
            continue

        meta = PDFParser.heuristic_paper_metadata(pages_data, f.filename)
        chunks = PDFParser.create_chunks(
            pages_data, 
            chunk_size=chunk_size, 
            chunk_overlap=chunk_overlap, 
            filename=f.filename, 
            paper_id=paper_id,
            strategy=chunking_strategy or "balanced"
        )

        vector_index = VectorIndex(chunks, google_api_key=gemini_key)
        
        # Intelligent sampling: pick Intro pages and Conclusion/Discussion page if available
        if len(pages_data) > 6:
            picked_indices = [0, 1, 2, 3, len(pages_data) - 2]
            sample_pages = [pages_data[i] for i in picked_indices if i < len(pages_data)]
        else:
            sample_pages = pages_data[:6]
        sample_text = "\n\n".join([f"--- Page {p['page']} ---\n{p['text']}" for p in sample_pages])
        breakdown = llm.analyze_paper(meta, sample_text)

        paper_obj = {
            "paper_id": paper_id,
            "filename": f.filename,
            "file_size": len(file_bytes),
            "total_pages": len(pages_data),
            "total_chunks": len(chunks),
            "chunking_strategy": chunking_strategy or "balanced",
            "metadata": meta,
            "breakdown": breakdown,
            "chunks": chunks,
            "pages_data": pages_data,
            "pdf_bytes": file_bytes,
            "vector_index": vector_index,
            "uploaded_at": time.time()
        }

        current_store[paper_id] = paper_obj
        processed_papers.append(paper_obj)
        all_chunks.extend(chunks)

    if not processed_papers:
        raise HTTPException(status_code=400, detail="Could not extract readable text from any uploaded PDF.")

    # If multiple papers are present in this user's session, create or update a unified cross-corpus session "all"
    if len(processed_papers) > 1:
        corpus_summary = (
            f"This collective dossier synthesizes {len(processed_papers)} academic research papers: "
            + ", ".join([f'"{p["breakdown"].get("title", p["filename"])}"' for p in processed_papers])
            + ". You can inquire about comparative methodology, cross-paper benchmark comparisons, or collective contributions."
        )

        corpus_breakdown = {
            "title": f"Corpus Synthesis & Comparative Review ({len(processed_papers)} Papers)",
            "authors": "Multiple Academic Investigators Across Documents",
            "publication_venue": "Multi-Document Research Dossier",
            "executive_summary": corpus_summary,
            "key_contributions": [
                f'[{p["filename"]}] {p["breakdown"].get("title", p["filename"])}: ' + (p["breakdown"].get("key_contributions", ["Key breakthrough"])[0])
                for p in processed_papers
            ],
            "methodology": (
                "Comparative cross-paper analytical evaluation examining theoretical paradigms, "
                "algorithmic architectures, and experimental implementations across all uploaded manuscripts."
            ),
            "results_and_benchmarks": (
                "Aggregate empirical metrics compiled across all uploaded manuscripts. "
                "Ask specific comparative questions to contrast baseline evaluations."
            ),
            "limitations": (
                "Heterogeneous evaluation domains, differing experimental protocols, and variable dataset distributions "
                "between independent research publications."
            ),
            "bibtex": "\n\n".join([p["breakdown"].get("bibtex", "") for p in processed_papers]),
            "suggested_questions": [
                "Compare the core methodologies and architectural differences between these papers.",
                "How do the empirical benchmark results compare between the papers?",
                "What contrasting assumptions or limitations are present across these works?",
                "Synthesize the collective breakthroughs and future directions from all papers."
            ]
        }

        current_store["all"] = {
            "paper_id": "all",
            "filename": f"All Papers ({len(processed_papers)} Documents)",
            "file_size": sum(p["file_size"] for p in processed_papers),
            "total_pages": sum(p["total_pages"] for p in processed_papers),
            "total_chunks": len(all_chunks),
            "metadata": {"title": f"Corpus Synthesis ({len(processed_papers)} Papers)", "abstract": corpus_summary},
            "breakdown": corpus_breakdown,
            "chunks": all_chunks,
            "vector_index": VectorIndex(all_chunks, google_api_key=gemini_key),
            "uploaded_at": time.time()
        }

    return {
        "papers": [
            {
                "paper_id": p["paper_id"],
                "filename": p["filename"],
                "total_pages": p["total_pages"],
                "total_chunks": p["total_chunks"],
                "chunking_strategy": p.get("chunking_strategy", "balanced"),
                "breakdown": p["breakdown"],
                "pages_data": p.get("pages_data", []),
                "has_pdf": "pdf_bytes" in p
            }
            for p in processed_papers
        ],
        "active_paper_id": "all" if len(processed_papers) > 1 else processed_papers[0]["paper_id"],
        "has_multiple": len(processed_papers) > 1,
        "session_id": sid
    }

@app.get("/api/papers")
async def list_papers(x_session_id: Optional[str] = Header(None)):
    store = get_session_store(x_session_id)
    return [
        {
            "paper_id": p["paper_id"],
            "filename": p["filename"],
            "title": p["breakdown"].get("title", p["filename"]),
            "total_pages": p["total_pages"],
            "total_chunks": p.get("total_chunks", len(p.get("chunks", []))),
            "uploaded_at": p["uploaded_at"]
        }
        for pid, p in store.items() if pid != "all"
    ]

@app.get("/api/paper/{paper_id}")
async def get_paper(paper_id: str, x_session_id: Optional[str] = Header(None)):
    store = get_session_store(x_session_id)
    p = find_paper_anywhere(paper_id, store)
    if not p:
        raise HTTPException(status_code=404, detail="Paper not found.")
    return {
        "paper_id": p["paper_id"],
        "filename": p["filename"],
        "total_pages": p["total_pages"],
        "total_chunks": p["total_chunks"],
        "breakdown": p["breakdown"],
        "pages_data": p.get("pages_data", []),
        "has_pdf": "pdf_bytes" in p
    }

@app.get("/api/paper/{paper_id}/pdf")
async def get_paper_pdf(paper_id: str, x_session_id: Optional[str] = Header(None)):
    store = get_session_store(x_session_id)
    p = find_paper_anywhere(paper_id, store)
    if not p or "pdf_bytes" not in p:
        raise HTTPException(status_code=404, detail="PDF binary not available for this session.")
    return Response(
        content=p["pdf_bytes"],
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{p["filename"]}"'}
    )

@app.post("/api/chat")
async def chat_with_paper(
    req: ChatRequest,
    x_gemini_key: Optional[str] = Header(None),
    x_groq_key: Optional[str] = Header(None),
    x_session_id: Optional[str] = Header(None)
):
    sid = req.session_id or x_session_id or DEFAULT_SESSION_ID
    store = get_session_store(sid)
    target_id = req.paper_id or "all"

    paper = find_paper_anywhere(target_id, store)
    if not paper:
        if "all" in store:
            target_id = "all"
            paper = store["all"]
        elif store:
            target_id = next(iter(store))
            paper = store[target_id]
        else:
            raise HTTPException(status_code=404, detail="No active paper session found. Please upload a paper.")

    vector_index: VectorIndex = paper["vector_index"]
    start_time = time.time()

    top_k_val = min(max(req.top_k or 5, 1), 30)
    top_chunks = vector_index.query(req.message, top_k=top_k_val)

    if req.highlighted_text:
        hl_chunk = {
            "chunk_id": 9999,
            "page": req.highlight_page or 1,
            "filename": paper.get("filename", ""),
            "section": "User Highlighted Passage",
            "text": f"USER HIGHLIGHTED PASSAGE FOR INQUIRY:\n\"{req.highlighted_text}\"",
            "is_reference": False,
            "score": 1.0
        }
        top_chunks = [hl_chunk] + [c for c in top_chunks if c.get("text") != req.highlighted_text][:top_k_val - 1]

    gemini_key, groq_key = resolve_credentials(x_gemini_key, x_groq_key, req.api_key)

    llm = LLMService(
        google_api_key=gemini_key,
        groq_api_key=groq_key,
        preferred_provider=req.provider or "gemini",
        preferred_model=req.model or "gemini-2.5-flash"
    )

    result = llm.answer_query(
        query=req.message,
        retrieved_chunks=top_chunks,
        conversation_history=req.history,
        model=req.model
    )

    elapsed = round(time.time() - start_time, 2)
    result["response_time"] = elapsed
    result["model_used"] = req.model
    result["target_paper_id"] = target_id
    result["retrieved_chunks_count"] = len(top_chunks)
    result["top_k_requested"] = top_k_val
    return result

@app.post("/api/export")
async def export_analysis(req: ExportRequest, x_session_id: Optional[str] = Header(None)):
    sid = req.session_id or x_session_id or DEFAULT_SESSION_ID
    store = get_session_store(sid)
    target_id = req.paper_id or "all"
    paper = find_paper_anywhere(target_id, store)
    if not paper and store:
        target_id = next(iter(store))
        paper = store[target_id]
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found.")

    bd = paper["breakdown"]
    title = bd.get("title", paper["filename"])
    
    md_lines = [
        f"# Research Paper Analysis: {title}",
        f"**Document:** `{paper['filename']}` | **Pages:** {paper['total_pages']}",
        "",
        "## Executive Summary",
        bd.get("executive_summary", "N/A"),
        "",
        "## Key Contributions & Findings",
    ]
    for contrib in bd.get("key_contributions", []):
        md_lines.append(f"- {contrib}")

    md_lines.extend([
        "",
        "## Methodology & Technical Architecture",
        bd.get("methodology", "N/A"),
        "",
        "## Experimental Results & Benchmarks",
        bd.get("results_and_benchmarks", "N/A"),
        "",
        "## Limitations & Future Work",
        bd.get("limitations", "N/A"),
        "",
        "## BibTeX Citation",
        "```bibtex",
        bd.get("bibtex", "@article{paper, title={Paper}}"),
        "```"
    ])

    if req.chat_history:
        md_lines.extend([
            "",
            "## Scholarly Co-Pilot Transcript & Cross-Questions",
            ""
        ])
        for msg in req.chat_history:
            role = msg.get("role", "user").capitalize()
            md_lines.append(f"**{role}:** {msg.get('content', '')}\n")

    report_content = "\n".join(md_lines)
    return PlainTextResponse(
        content=report_content,
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=Analysis_{target_id}.md"}
    )

@app.delete("/api/paper/{paper_id}")
async def delete_paper(paper_id: str, x_session_id: Optional[str] = Header(None)):
    store = get_session_store(x_session_id)
    if paper_id in store:
        del store[paper_id]
        return {"status": "success", "message": f"Paper {paper_id} removed."}
    for s in SESSIONS_STORE.values():
        if paper_id in s:
            del s[paper_id]
            return {"status": "success", "message": f"Paper {paper_id} removed."}
    return {"status": "not_found"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)

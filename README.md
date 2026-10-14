# PaperScope AI — Enterprise Academic Research Paper Analyser

[![Next.js](https://img.shields.io/badge/Frontend-Next.js%2016-black?style=flat-square&logo=next.js)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Gemini](https://img.shields.io/badge/LLM-Google%20Gemini%202.5-4285F4?style=flat-square&logo=google)](https://ai.google.dev/)
[![TypeScript](https://img.shields.io/badge/Language-TypeScript-3178C6?style=flat-square&logo=typescript)](https://www.typescriptlang.org/)
[![Python](https://img.shields.io/badge/Language-Python%203.13-3776AB?style=flat-square&logo=python)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Container-Docker-2496ED?style=flat-square&logo=docker)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)

An enterprise-grade, full-stack Retrieval-Augmented Generation (RAG) platform purpose-built for academic literature synthesis, multi-document cross-examination, and verifiable citation interrogation.

---

## Application Walkthrough

### Stage 1: Document Ingestion & Workspace Setup
Configure semantic chunking profiles, select inference models, and ingest single or multi-manuscript research corpuses via intuitive drag-and-drop or the native file selector.

![Stage 1: Ingestion & Workspace Setup](docs/screenshots/01-landing-workspace.png)

* **Adaptive Chunking Engine**: Choose between Balanced Paragraph (900c), Fine-Grained Passage (450c), Coarse Context (1800c), or Section-Aware Academic isolation.
* **Academic Manuscript Ingestion**: Ingest multi-column scientific PDFs (such as the frontier robotics papers provided in `sample_docs/`) with automated vector indexing.
* **Model & Session Configuration**: Enter your Gemini API key in-browser or run securely against backend environment variables.

---

### Stage 2: Split-Screen Academic Synthesis & Grounded Co-Pilot
View automated 5-part academic breakdowns alongside document metadata, publication venues, and one-click citation exports while conducting deep conversational inquiries with verified page-level citations (shown analyzing OpenVLA from `sample_docs/`).

![Stage 2: Split-Screen Academic Synthesis & Grounded Co-Pilot](docs/screenshots/02-paper-synthesis.png)

* **Automated 5-Part Breakdown**: Instant structured synthesis extracting Executive Summary, Key Contributions, Methodology & Design, Empirical Benchmarks, and Documented Limitations.
* **Conversational Co-Pilot**: Interactive inquiries with grounded page-level citations and proactive domain-specific follow-ups.
* **Multi-Paper Corpus Switcher**: Switch between individual paper monographs or analyze the unified multi-document corpus.
* **Tri-Mode Reader**: Toggle between Executive Analysis, Embedded Original PDF, and Page-by-Page Manuscript views.
* **BibTeX Generator**: Instant copyable BibTeX entry formatted to academic standards.

---

## Core Capabilities

| Capability | Description |
|---|---|
| **Multi-Document Synthesis** | Ingest multiple papers simultaneously to perform cross-document comparisons, synthesize conflicting methodologies, and discover cross-paper citations. |
| **Verifiable In-Text Citations** | Eliminates hallucination risk with strict source grounding, inline citation chips, and relevance scores. |
| **Configurable Chunking Profiles** | Tailor token segmentation to the paper's domain — fine-grained for metric ablation tables or coarse for mathematical proofs. |
| **Advanced Reasoning Engines** | Powered by Google Gemini 2.5 Flash for high-speed synthesis and Gemini 2.5 Pro for deep mathematical and theoretical reasoning. |
| **Flexible Workspace Layouts** | Work in Dual-Pane Split View, focused ChatGPT Mode, Reading Article View, or Full Original PDF Mode. |
| **Session Isolation & Privacy** | Multi-tenant session isolation keeps paper indices separate per user with optional client-side API key storage. |
| **Editorial Newspaper Aesthetic** | Designed with high-readability typography, obsidian dark mode toggle, and micro-animations. |

---

## System Architecture

```mermaid
graph TD
    subgraph Ingestion Pipeline
        A[User PDF Academic Upload] --> B[FastAPI /api/upload]
        B --> C[PDFParser: Page-by-Page Extraction]
        C --> D[Configurable Semantic Chunking]
        D --> E[Vector Index: Embeddings / Cosine Similarity]
        C --> F[Automatic Synthesis Engine: Google Gemini]
        F --> G[5-Part Breakdown: Executive, Methods, Benchmarks, Limitations, BibTeX]
    end

    subgraph Conversational RAG Pipeline
        H[User Research Query / Highlighted Passage] --> I[FastAPI /api/chat]
        I --> J[Vector Cosine Similarity & Re-Ranking]
        J --> K[Top-K Page-Attributed Chunks]
        K --> L[LLM Grounded Synthesis]
        L --> M[Response with Inline Citations & Follow-up Questions]
        M --> N[Next.js Interactive UI with Excerpt Verification Drawer]
    end
```

---

## Quick Start Guide

### Prerequisites
* **Node.js**: v18+ (tested on Node.js v24)
* **Python**: 3.9+ (tested on Python 3.13)
* **API Key (Optional)**: [Google AI Studio (Gemini)](https://aistudio.google.com/app/apikey). *Keys can also be entered directly in the web UI!*

---

### Option 1: Run with Docker Compose (Recommended)

Run the entire full-stack application with a single command:

```bash
docker compose up --build
```

* **Frontend**: `http://localhost:3000`
* **Backend API**: `http://localhost:8000`

---

### Option 2: Local Development Setup

#### 1. Backend Setup (FastAPI)

```bash
cd backend

# Install dependencies
python -m pip install -r requirements.txt

# (Optional) Copy environment template
cp .env.example .env

# Start FastAPI dev server (port 8001)
python main.py
```

The interactive OpenAPI documentation is available at `http://localhost:8001/docs`.

#### 2. Frontend Setup (Next.js)

```bash
cd frontend

# Install dependencies
npm install

# Start Next.js development server (port 3000)
npm run dev
```

Open your browser at `http://localhost:3000`.

---

## Environment Configuration

### Backend (`backend/.env`)

| Variable | Description | Default |
|---|---|---|
| `PORT` | FastAPI server port | `8001` |
| `HOST` | Bind host address | `0.0.0.0` |
| `GOOGLE_API_KEY` | Google Gemini API key (optional if provided in UI) | `""` |

### Frontend (`frontend/.env.local`)

| Variable | Description | Default |
|---|---|---|
| `NEXT_PUBLIC_BACKEND_URL` | Base URL pointing to the FastAPI backend | `http://localhost:8001` |

---

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/api/upload` | `POST` | Upload PDF files with chunking strategy & session tracking. Returns parsed metadata and 5-part synthesis. |
| `/api/chat` | `POST` | Query paper corpus with conversational history, highlighted text, and retrieve grounded responses with citations. |
| `/api/paper/{paper_id}/pdf` | `GET` | Stream original PDF file for the embedded browser reader. |
| `/api/paper/{paper_id}` | `DELETE` | Remove a paper from the active user session index. |
| `/api/health` | `GET` | Service health status and active session counts. |

---

## Cloud Deployment

### Deploying Frontend to Vercel
1. Push repository to GitHub.
2. In [Vercel](https://vercel.com), select **"Add New Project"** and import the repository.
3. Set **Root Directory** to `frontend`.
4. Configure environment variable:
   * `NEXT_PUBLIC_BACKEND_URL`: URL of your deployed FastAPI backend (e.g., `https://your-api.onrender.com`).
5. Click **Deploy**.

### Deploying Backend to Render / Railway
1. In Render, create a **"New Web Service"** and connect your repository.
2. Set **Root Directory** to `backend`.
3. Set **Runtime** to `Python 3`.
4. Set **Build Command**: `pip install -r requirements.txt`.
5. Set **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`.
6. Add environment variables:
   * `GOOGLE_API_KEY`: Your Gemini API key.

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

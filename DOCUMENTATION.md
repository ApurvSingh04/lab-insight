# Clinical Lab Results Analyzer — System Architecture & Technical Documentation

> **Project Goal:** Build a full-stack, AI-powered Web Application that ingests clinical laboratory test results (CSV or manual input), classifies severity (Normal / Warning / Critical), routes results by clinical urgency and medical specialty, and presents medically accurate explanations based on **Explainable AI (XAI)** principles.

---

## 1. System Architecture Overview

The system uses a decoupled, three-tier micro-architecture:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                             REACT FRONTEND                                  │
│  - Vite + React 18 (Dark-mode Glassmorphism UI)                              │
│  - Client-Side CSV Parsing (PapaParse)                                      │
│  - Live State Management (useReducer)                                       │
│  - SSE Stream Reader (Fetch API + ReadableStream)                           │
│  - Visual Explainable AI (Interactive Range Gauge & KPI Summary Bar)        │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ HTTP POST (SSE Event Stream)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          FASTAPI BACKEND SERVER                             │
│  - /analyze_labs_stream (Server-Sent Events)                                │
│  - Asyncio In-Memory Queue (LabQueue) for rate-limited rate pacing           │
│  - Google GenAI SDK (Gemini 3.6 Flash / 2.0 Flash)                          │
│  - Hybrid Execution: Deterministic Math + LLM Explainability                │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Python Import / MCP Protocol
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            MCP SERVER (FastMCP)                             │
│  - reference_range_lookup(test_name)                                       │
│  - classify_result_locally(test_name, value, min, max)                      │
│  - get_specialist_routing(test_name, severity)                              │
│  - get_clinical_urgency(severity, test_name, deviation_pct)                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Core Technical Components & Data Flow

### A. Step-by-Step Execution Workflow

1. **User Upload & Client-Side Ingestion:**
   - The user selects a CSV file containing lab results in `LabInput.jsx`.
   - `PapaParse` parses the file client-side instantly without blocking the network.
   - `useReducer` initializes skeleton cards in the UI (`status: "pending"`).
   - Top KPI counters show total test count immediately.

2. **Backend Streaming & Rate-Paced Queueing:**
   - The React frontend sends a single `POST /analyze_labs_stream` request with all parsed test objects.
   - `main.py` passes the array to `LabQueue` in `agent.py`.
   - `LabQueue` pushes items into an `asyncio.Queue` and starts an async worker loop.
   - The worker pops one lab result at a time, processes it, waits `RATE_LIMIT_DELAY_SECONDS` (13s for Gemini free tier rate limit of 5 req/min), and streams the result back as a Server-Sent Event (SSE data chunk).

3. **Hybrid Agent Analysis Pipeline (`Agent.analyze_single`):**
   - **Step 1 — Context Enrichment:** Compiles test value, units, reference bounds (`Min_Reference`, `Max_Reference`), and original dataset comments.
   - **Step 2 — Deterministic Pre-Classification (MCP):** Calls `classify_result_locally()` to perform exact numeric deviation calculations ($ deviation = \frac{|val - bound|}{bound} \times 100$).
   - **Step 3 — LLM Explanation Generation:** Invokes Google Gemini via `google-genai` SDK with strict JSON schema constraints to generate a 2-3 sentence XAI clinical explanation and recommended next steps.
   - **Step 4 — Specialist Routing (MCP):** Calls `get_specialist_routing()` to assign medical specialty (e.g., Hematology, Nephrology, Endocrinology, Hepatology, Cardiology).
   - **Step 5 — Clinical Urgency Assessment (MCP):** Calls `get_clinical_urgency()` to assign urgency codes (`STAT`, `EMERGENCY`, `URGENT`, `ROUTINE`) and action timeframes (`1 hour`, `24 hours`, etc.).

4. **Real-time Frontend UI Update:**
   - As each SSE data chunk arrives, `App.jsx` dispatches `UPDATE_RESULT`.
   - The pending skeleton card transitions to a full result card.
   - The top KPI counters (`Critical`, `Warning`, `Normal`) increment live.
   - The top progress bar updates (`X / N complete`).
   - The visual **Range Gauge** renders the exact position of the test value relative to the normal range segment.

---

## 3. Explainable AI (XAI) Design Principles

To ensure transparency and clinical trust, the application strictly avoids "black-box" outputs:

1. **Visual Deviation Gauge:** Every test card renders a visual scale where the normal reference interval is highlighted in green. A crisp white indicator dot shows the patient's value on the scale, making out-of-bounds deviation visually obvious.
2. **Explicit Reference Bounds:** Shows minimum, maximum, unit, and deviation percentage.
3. **Medical Rationale in Explanations:** Gemini is prompted to explicitly state *why* a result was flagged, what physiological system is affected, and what clinical risk it presents.
4. **Actionable Next Steps:** Gives concrete recommendations (e.g., "Emergency nephrology consult for acute kidney failure evaluation") rather than generic advice.

---

## 4. Model Context Protocol (MCP) Integration

The project includes an explicit **MCP Server** built with `FastMCP` (`mcp_server.py`), exposing four specialized tools:

```python
# Available MCP Tools:

1. reference_range_lookup(test_name: str) -> str
   Returns min, max, and unit for standard clinical lab tests.

2. classify_result_locally(test_name: str, value: str, min_ref: float, max_ref: float) -> str
   Performs pure numeric threshold checking without LLM overhead.

3. get_specialist_routing(test_name: str, severity: str) -> str
   Maps test categories to medical specialties (Hematology, Endocrinology, etc.).

4. get_clinical_urgency(severity: str, test_name: str, deviation_pct: float) -> str
   Provides triage urgency (STAT / URGENT / ROUTINE) and response SLAs.
```

---

## 5. Technology Stack Summary

### Backend
- **Framework:** FastAPI (Python 3.10+)
- **Server:** Uvicorn (ASGI)
- **AI SDK:** `google-genai` (Gemini 3.6 Flash / 2.0 Flash)
- **MCP Framework:** `mcp` (FastMCP)
- **Data Ingestion:** Pandas, Pydantic v2
- **Environment:** `python-dotenv`

### Frontend
- **Framework:** React 18 + Vite 5
- **State Management:** `useReducer` + React Context
- **CSV Ingestion:** `PapaParse`
- **Icons:** `lucide-react`
- **Styling:** Vanilla CSS (Glassmorphism, CSS Variables, Keyframe Animations)
- **HTTP/Streaming:** Fetch API + ReadableStream (SSE)

---

## 6. Directory & File Structure

```
clinical-lab-result-analyzer/
├── backend/
│   ├── main.py              # FastAPI application, endpoints (/analyze_labs_stream, etc.)
│   ├── agent.py             # Agent pipeline, LabQueue async processing, Gemini integration
│   ├── mcp_server.py        # FastMCP tools (Reference ranges, Routing, Urgency)
│   ├── diagnose.py          # Environment & API key diagnostic utility
│   └── requirements.txt     # Backend Python dependencies
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── LabInput.jsx         # CSV upload dropzone & file picker
│   │   │   ├── ResultsDisplay.jsx   # Stacked card layout, Range Gauge, KPI counters
│   │   │   └── SeverityBadge.jsx    # Severity status badges
│   │   ├── App.jsx                  # Main application state & SSE stream handler
│   │   ├── index.css                # Glassmorphism design system & component styles
│   │   └── main.jsx                 # React root entry point
│   ├── package.json                 # Frontend dependencies
│   └── vite.config.js               # Vite build configuration
├── test_data/
│   ├── test_data.csv                # Full Kaggle dataset (28 rows)
│   ├── test_batch_1.csv             # Batch 1 (9 rows)
│   ├── test_batch_2.csv             # Batch 2 (9 rows)
│   ├── test_batch_3.csv             # Batch 3 (9 rows)
│   └── test_synthetic_all_severities.csv # Synthetic test set (Critical, Warning, Normal)
└── DOCUMENTATION.md                # System documentation specification
```

---

## 7. API Specification

### `POST /analyze_labs_stream`
- **Request Body:** `{ "labs": [ { "test_name": str, "result": str, "unit": str, "reference_range": str, "min_reference": float, "max_reference": float } ] }`
- **Response:** `text/event-stream`
- **Stream Event Format:** `data: {"test_name": "...", "result": "...", "severity": "Critical", "explanation": "...", "next_steps": "...", "specialist": "Hematology", "urgency_label": "STAT"}`

---

## 8. Deployment & Running Instructions

### Backend Setup
```bash
cd backend
python -m venv ../venv
..\venv\Scripts\activate
pip install -r requirements.txt
python main.py
```
*Server runs on `http://localhost:8000`*

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
*Application opens on `http://localhost:5173`*

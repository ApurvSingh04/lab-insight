# Clinical Lab Results Analyzer

A full-stack, AI-powered Web Application designed to analyze clinical laboratory test results, classify their severity based on established reference ranges, route them by urgency and medical specialty, and generate AI-driven clinical explanations adhering to **Explainable AI (XAI)** principles.

📖 **For full technical specification, API documentation, and architecture diagrams, see [`DOCUMENTATION.md`](DOCUMENTATION.md).**

---

## Key Features

- **Explainable AI (XAI)**: Visual **Range Gauge** indicator showing the exact position of test values relative to reference bounds, combined with clear medical explanations.
- **Real-Time SSE Streaming & Rate-Paced Queueing**: Client-side CSV parsing (`PapaParse`) + backend `asyncio.Queue` streaming results via Server-Sent Events (SSE) to smoothly handle API rate limits.
- **Top KPI Summary Counters**: Live tracking of Total, Critical, Warning, and Normal test counts.
- **Model Context Protocol (MCP) Integration**: Explicit `FastMCP` tools (`reference_range_lookup`, `classify_result_locally`, `get_specialist_routing`, `get_clinical_urgency`).
- **Specialist Routing & Triage Urgency**: Automatic routing to medical specialties (Hematology, Nephrology, Endocrinology, etc.) with triage SLAs (`STAT`, `EMERGENCY`, `URGENT`, `ROUTINE`).
- **Premium UI**: Full-width glassmorphism design system built with React 18, Vite 5, and vanilla CSS.

---

## Tech Stack

- **Backend**: Python FastAPI, Uvicorn, Pydantic v2, Pandas, `google-genai` SDK (Gemini 3.6 Flash), `mcp` (FastMCP)
- **Frontend**: React 18, Vite 5, PapaParse, Lucide React, Glassmorphic Vanilla CSS
- **Protocol**: HTTP/SSE (Server-Sent Events)

---

## Quick Start

### 1. Environment Setup
Create `.env` in the project root:
```env
GEMINI_API_KEY=AIza...your_gemini_api_key_here
```

### 2. Backend Setup
```bash
cd backend
..\venv\Scripts\activate   # Or source venv/bin/activate
pip install -r requirements.txt
python main.py
```
*Backend runs on `http://localhost:8000`*

### 3. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
*Frontend runs on `http://localhost:5173`*

---

## Testing with Provided Data

Use the files in `test_data/`:
- `test_synthetic_all_severities.csv` — **Recommended for demo** (contains Critical, Warning, and Normal cases)
- `test_batch_1.csv`, `test_batch_2.csv`, `test_batch_3.csv` — Split batches from the 28-row Kaggle dataset


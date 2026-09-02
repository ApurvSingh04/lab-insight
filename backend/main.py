import os
import json
import io
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List
from dotenv import load_dotenv
import pandas as pd

load_dotenv()

from agent import Agent, LabResult, AnalyzedResult, LabQueue

app = FastAPI(title="Clinical Lab Results Analyzer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

agent = Agent()
lab_queue = LabQueue(agent)


class LabAnalysisRequest(BaseModel):
    labs: List[LabResult]
    patient_context: str = ""


# ── SSE streaming endpoint ──────────────────────────────────────────────────

@app.post("/analyze_labs_stream")
async def analyze_labs_stream(request: LabAnalysisRequest):
    """
    Accepts all labs, queues them sequentially, streams results back via SSE.
    The asyncio queue ensures API calls are spaced out to respect rate limits.
    """
    if not request.labs:
        raise HTTPException(status_code=400, detail="No lab results provided")

    async def event_generator():
        try:
            async for result in lab_queue.process_stream(request.labs, request.patient_context):
                # Serialize each result as an SSE data event
                data = json.dumps(result.model_dump())
                yield f"data: {data}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


# ── Single lab endpoint (kept for compatibility) ────────────────────────────

@app.post("/analyze_single_lab", response_model=AnalyzedResult)
async def analyze_single_lab(lab: LabResult):
    try:
        import asyncio
        result = await asyncio.get_event_loop().run_in_executor(
            None, agent.analyze_single, lab
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Bulk endpoint ───────────────────────────────────────────────────────────

@app.post("/analyze_labs", response_model=List[AnalyzedResult])
async def analyze_labs(request: LabAnalysisRequest):
    if not request.labs:
        raise HTTPException(status_code=400, detail="No lab results provided")
    try:
        results = []
        async for res in lab_queue.process_stream(request.labs, request.patient_context):
            if res.status in ("done", "error"):
                results.append(res)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── CSV bulk endpoint (kept for compatibility) ───────────────────────────────

@app.post("/analyze_labs_csv", response_model=List[AnalyzedResult])
async def analyze_labs_csv(file: UploadFile = File(...)):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")
    try:
        contents = await file.read()
        df = pd.read_csv(io.StringIO(contents.decode('utf-8')))

        labs = []
        for _, row in df.iterrows():
            test_name = row.get('Test_Name', row.get('Test Name', 'Unknown Test'))
            result = row.get('Result', row.get('Value', '0'))
            unit = row.get('Unit', '')
            reference_range = row.get('Reference_Range', row.get('Reference Range', ''))
            # Use dataset's own numeric bounds directly — no need to hardcode them
            min_ref = row.get('Min_Reference', row.get('Min Reference', None))
            max_ref = row.get('Max_Reference', row.get('Max Reference', None))
            dataset_status = row.get('Status', None)
            dataset_comment = row.get('Comment', None)

            if pd.isna(test_name) or pd.isna(result):
                continue

            def safe_float(val):
                try:
                    return float(val) if val and not pd.isna(val) else None
                except (ValueError, TypeError):
                    return None

            labs.append(LabResult(
                test_name=str(test_name),
                result=str(result),
                unit=str(unit) if not pd.isna(unit) else "",
                reference_range=str(reference_range) if reference_range and not pd.isna(reference_range) else None,
                min_reference=safe_float(min_ref),
                max_reference=safe_float(max_ref),
                dataset_status=str(dataset_status) if dataset_status and not pd.isna(dataset_status) else None,
                dataset_comment=str(dataset_comment) if dataset_comment and not pd.isna(dataset_comment) else None,
            ))

        if not labs:
            raise HTTPException(status_code=400, detail="No valid data found in CSV")

        results = []
        async for res in lab_queue.process_stream(labs, ""):
            if res.status in ("done", "error"):
                results.append(res)
        return results

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

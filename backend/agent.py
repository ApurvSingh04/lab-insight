import os
import json
import asyncio
from google import genai
from google.genai import types
from pydantic import BaseModel
from typing import List, Optional


RATE_LIMIT_DELAY_SECONDS = 13  # Free tier = 5 req/min → 1 per 12s

def get_gemini_client():
    api_key = os.getenv("GEMINI_API_KEY")
    return genai.Client(api_key=api_key)


class LabResult(BaseModel):
    test_name: str
    result: float | str
    unit: str
    reference_range: Optional[str] = None       # e.g. "15-150"
    min_reference: Optional[float] = None        # from dataset Min_Reference col
    max_reference: Optional[float] = None        # from dataset Max_Reference col
    dataset_status: Optional[str] = None         # dataset's own Status label
    dataset_comment: Optional[str] = None        # dataset's human comment


class AnalyzedResult(BaseModel):
    test_name: str
    result: float | str
    unit: str
    severity: str  # Normal, Warning, Critical
    explanation: str
    next_steps: str


class Agent:
    def __init__(self, mcp_client=None):
        self.mcp_client = mcp_client
        self.client = None

    def _get_client(self):
        if self.client is None:
            self.client = get_gemini_client()
        return self.client

    def get_reference_range(self, test_name: str) -> str:
        return None

    def analyze_single(self, lab: LabResult) -> AnalyzedResult:
        """Call Gemini API for a single lab result. Returns an AnalyzedResult."""
        client = self._get_client()

        # Build reference range context directly from dataset columns
        ref_context = ""
        if lab.reference_range:
            ref_context += f"Reference Range: {lab.reference_range} {lab.unit}\n"
        if lab.min_reference is not None and lab.max_reference is not None:
            ref_context += f"Min Normal: {lab.min_reference} | Max Normal: {lab.max_reference}\n"
            # Pre-classify locally using dataset's own numeric bounds
            try:
                val = float(str(lab.result).replace('+', '').replace('-', '0'))
                if val < lab.min_reference or val > lab.max_reference:
                    pct_off = max(
                        abs(val - lab.min_reference) / lab.min_reference,
                        abs(val - lab.max_reference) / lab.max_reference
                    ) * 100 if lab.min_reference and lab.max_reference else 0
                    local_hint = f"Critical" if pct_off > 30 else "Warning"
                else:
                    local_hint = "Normal"
                ref_context += f"Pre-classification (numeric): {local_hint}\n"
            except (ValueError, TypeError):
                pass  # Non-numeric result (e.g. Negatif/Normal text)
        if lab.dataset_status:
            ref_context += f"Lab's own Status label: {lab.dataset_status}\n"
        if lab.dataset_comment:
            ref_context += f"Lab's clinical comment: {lab.dataset_comment}\n"

        if not ref_context:
            ref_context = "Reference Range: Standard clinical range\n"

        prompt = f"""
        You are an expert clinical AI assistant. Analyze the following laboratory test result.

        Test Name: {lab.test_name}
        Result: {lab.result} {lab.unit}
        {ref_context}
        Based on the principles of Explainable AI, respond ONLY with a valid JSON object:
        - "severity": MUST be exactly one of: "Normal", "Warning", or "Critical"
        - "explanation": 2-3 sentences explaining what this result means and WHY it is
          classified as Normal/Warning/Critical. Be specific — mention the reference range
          and how far the value deviates if abnormal.
        - "next_steps": Specific, actionable clinical next steps.

        Return ONLY the JSON object. No markdown, no backticks.
        """

        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        response_text = response.text.strip()
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()

        ai_data = json.loads(response_text)

        return AnalyzedResult(
            test_name=lab.test_name,
            result=lab.result,
            unit=lab.unit,
            severity=ai_data.get("severity", "Normal"),
            explanation=ai_data.get("explanation", "No explanation provided."),
            next_steps=ai_data.get("next_steps", "Consult your doctor.")
        )

    def analyze_labs(self, labs: List[LabResult]) -> List[AnalyzedResult]:
        """Process all labs synchronously (for /analyze_labs bulk endpoint)."""
        results = []
        for lab in labs:
            try:
                results.append(self.analyze_single(lab))
            except Exception as e:
                results.append(AnalyzedResult(
                    test_name=lab.test_name,
                    result=lab.result,
                    unit=lab.unit,
                    severity="Unknown",
                    explanation=f"Error analyzing result: {str(e)}",
                    next_steps="Retry later."
                ))
        return results


class LabQueue:
    """
    Asyncio-based sequential queue for processing lab results one at a time.
    Ensures API calls are rate-limited automatically.
    """
    def __init__(self, agent: Agent):
        self.agent = agent
        self._queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: asyncio.Task | None = None

    def start(self):
        """Start the background worker coroutine."""
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker())

    async def _worker(self):
        """Worker: dequeues labs one by one, calls Gemini, puts result in response queue."""
        while True:
            lab, response_queue, is_last = await self._queue.get()
            try:
                result = await asyncio.get_event_loop().run_in_executor(
                    None, self.agent.analyze_single, lab
                )
                await response_queue.put(("result", result))
            except Exception as e:
                error_result = AnalyzedResult(
                    test_name=lab.test_name,
                    result=lab.result,
                    unit=lab.unit,
                    severity="Unknown",
                    explanation=f"Error: {str(e)}",
                    next_steps="Retry later."
                )
                await response_queue.put(("result", error_result))
            finally:
                self._queue.task_done()

            if is_last:
                await response_queue.put(("done", None))
                return

            # Rate limit: wait between calls
            await asyncio.sleep(RATE_LIMIT_DELAY_SECONDS)

    async def process_stream(self, labs: List[LabResult]):
        """
        Push all labs into the queue, start worker, and yield SSE events
        as each result is processed.
        """
        response_queue: asyncio.Queue = asyncio.Queue()

        for i, lab in enumerate(labs):
            is_last = (i == len(labs) - 1)
            await self._queue.put((lab, response_queue, is_last))

        self.start()

        while True:
            event_type, payload = await response_queue.get()
            if event_type == "done":
                break
            yield payload

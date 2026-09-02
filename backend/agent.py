import os
import json
import asyncio
from typing import List, Optional, Dict
from pydantic import BaseModel
from google import genai
from google.genai import types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

RATE_LIMIT_DELAY_SECONDS = 25  # Wait time between batches of 5

def get_gemini_client():
    api_key = os.getenv("GEMINI_API_KEY")
    return genai.Client(api_key=api_key)


class LabResult(BaseModel):
    test_name: str
    result: float | str
    unit: str
    reference_range: Optional[str] = None       
    min_reference: Optional[float] = None        
    max_reference: Optional[float] = None        
    dataset_status: Optional[str] = None         
    dataset_comment: Optional[str] = None        


class AnalyzedResult(BaseModel):
    test_name: str
    result: float | str
    unit: str
    severity: str  
    explanation: str
    next_steps: str
    status: str = "done"  
    range_source: str = "standard"
    original_severity: Optional[str] = None
    patient_context: Optional[str] = None
    min_reference: Optional[float] = None
    max_reference: Optional[float] = None
    original_min: Optional[float] = None
    original_max: Optional[float] = None
    urgency: Optional[str] = None
    routing_specialty: Optional[str] = None

class AdjustedBound(BaseModel):
    test_name: str
    min_reference: Optional[float] = None
    max_reference: Optional[float] = None
    rationale: Optional[str] = None

class CalibrationResponse(BaseModel):
    adjustments: List[AdjustedBound]

class Agent:
    def __init__(self):
        self.client = None
        self._mcp_server_params = StdioServerParameters(
            command="python",
            args=["mcp_server.py"],
        )

    def _get_client(self):
        if self.client is None:
            self.client = get_gemini_client()
        return self.client



    async def calibrate_thresholds(self, labs: List[LabResult], patient_context: str) -> Dict[str, AdjustedBound]:
        """Ask LLM to safely adjust numeric reference bounds based on patient context."""
        client = self._get_client()
        
        # Only calibrate tests that actually have numeric bounds
        valid_labs = [l for l in labs if l.min_reference is not None and l.max_reference is not None]
        if not valid_labs:
            return {}
            
        prompt = f"Patient Context: {patient_context}\n"
        prompt += "Based on this patient context, should any of these standard reference ranges be adjusted? Return a JSON array of adjustments. Each adjustment must include a 'rationale' explaining why the bound was moved.\n"
        prompt += "Tests:\n"
        for l in valid_labs:
            prompt += f"- {l.test_name} (Current range: {l.min_reference} - {l.max_reference} {l.unit})\n"
            
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None, 
                lambda: client.models.generate_content(
                    model="gemini-3.6-flash",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=CalibrationResponse,
                        temperature=0.2
                    )
                )
            )
            
            data = json.loads(response.text.strip())
            calibrations = {}
            for adj in data.get("adjustments", []):
                t_name = adj.get("test_name")
                calibrations[t_name] = adj
            return calibrations
        except Exception as e:
            print(f"Calibration failed: {e}")
            return {}

    def classify_locally(self, lab: LabResult, min_ref: float = None, max_ref: float = None) -> str:
        """Deterministic mathematical classification."""
        if not lab.result or lab.result == '0':
            pass 

        try:
            res_val = float(lab.result)
            if res_val < 0:
                return "data_error"

            mn = min_ref if min_ref is not None else lab.min_reference
            mx = max_ref if max_ref is not None else lab.max_reference
            
            if mn is not None and mx is not None:
                if res_val < mn:
                    # Guardrail: Warning<->Critical boundary is fixed to original bounds for safety
                    if lab.min_reference and res_val < lab.min_reference * 0.8:
                        return "Critical"
                    return "Warning"
                elif res_val > mx:
                    if lab.max_reference and res_val > lab.max_reference * 1.2:
                        return "Critical"
                    return "Warning"
                else:
                    return "Normal"
            else:
                return "unclassified"
        except (ValueError, TypeError):
            return "unclassified"

    def analyze_single(self, lab: LabResult, patient_context: str = "", range_source: str = "standard", adj_min: float = None, adj_max: float = None) -> AnalyzedResult:
        client = self._get_client()
        local_severity = self.classify_locally(lab, adj_min, adj_max)
        
        if local_severity == "data_error":
            return AnalyzedResult(
                test_name=lab.test_name, result=lab.result, unit=lab.unit,
                severity="data_error", explanation="Data Error: Value is physiologically impossible.",
                next_steps="Verify data entry.", status="done"
            )

        ref_context = ""
        if patient_context:
            ref_context += f"Patient Context: {patient_context}\n"
            
        mn = adj_min if adj_min is not None else lab.min_reference
        mx = adj_max if adj_max is not None else lab.max_reference
        
        if mn is not None and mx is not None:
            if range_source == "patient_adjusted":
                ref_context += f"Adjusted Reference Bounds (for patient context): {mn} to {mx}\n"
            else:
                ref_context += f"Standard Reference Bounds: {mn} to {mx}\n"
            ref_context += f"Mathematical Pre-classification: {local_severity}\n"
        
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
        - "urgency": MUST be exactly one of: "STAT" (Emergency), "URGENT" (Soon), or "ROUTINE".
        - "routing_specialty": The suggested medical specialty (e.g., "Cardiology", "Hematology", "General Practice").
        - "explanation": 2-3 sentences explaining what this result means and WHY it is
          classified as Normal/Warning/Critical. Be specific — mention the reference range
          and how far the value deviates if abnormal.
        - "next_steps": Short, crisp, and instructive actionable clinical next steps. MAXIMUM 60 characters (e.g., "Schedule hematology consult").
        Return ONLY the JSON object. No markdown, no backticks.
        """

        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )

        response_text = response.text.strip()
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()

        ai_data = json.loads(response_text)

        return AnalyzedResult(
            test_name=lab.test_name, result=lab.result, unit=lab.unit,
            severity=ai_data.get("severity", local_severity),
            explanation=ai_data.get("explanation", "No explanation provided."),
            next_steps=ai_data.get("next_steps", "Consult your doctor."),
            status="done",
            range_source=range_source,
            patient_context=patient_context,
            min_reference=mn,
            max_reference=mx,
            original_min=lab.min_reference,
            original_max=lab.max_reference,
            urgency=ai_data.get("urgency", "ROUTINE"),
            routing_specialty=ai_data.get("routing_specialty", "General Practice")
        )

class LabQueue:
    def __init__(self, agent: Agent):
        self.agent = agent

    async def process_stream(self, labs: List[LabResult], patient_context: str = ""):
        # 1. True Instant Yield (Standard Bounds)
        for lab in labs:
            local_sev = self.agent.classify_locally(lab)
            instant_result = AnalyzedResult(
                test_name=lab.test_name, result=lab.result, unit=lab.unit,
                severity=local_sev, explanation="AI is analyzing this result...",
                next_steps="...", status="processing_llm", range_source="standard",
                min_reference=lab.min_reference, max_reference=lab.max_reference,
                urgency="...", routing_specialty="..."
            )
            if local_sev == "data_error":
                instant_result.status = "done"
                instant_result.explanation = "Data Error: Value is physiologically impossible (e.g., negative concentration) or missing."
            yield instant_result

        # 2. MCP Fallback for missing references (Single Session)
        labs_missing = [l for l in labs if l.min_reference is None and l.result and float(l.result) >= 0]
        if labs_missing:
            try:
                from mcp.client.stdio import stdio_client
                from mcp import ClientSession
                async with stdio_client(self.agent._mcp_server_params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        for lab in labs_missing:
                            result = await session.call_tool("reference_range_lookup", arguments={"test_name": lab.test_name})
                            if result.content and len(result.content) > 0:
                                data = json.loads(result.content[0].text)
                                if "error" not in data:
                                    lab.min_reference = data["min"]
                                    lab.max_reference = data["max"]
                                    if not lab.unit:
                                        lab.unit = data["unit"]
                                    
                                    # Yield transition event
                                    new_sev = self.agent.classify_locally(lab)
                                    yield AnalyzedResult(
                                        test_name=lab.test_name, result=lab.result, unit=lab.unit,
                                        severity=new_sev, explanation="Fetched reference range from MCP...",
                                        next_steps="...", status="processing_llm", range_source="standard",
                                        min_reference=lab.min_reference, max_reference=lab.max_reference,
                                        urgency="...", routing_specialty="..."
                                    )
            except Exception as e:
                print(f"MCP Batch Error: {e}")

        valid_labs = [l for l in labs if self.agent.classify_locally(l) != "data_error"]
        if not valid_labs:
            return

        # 2. Parallel Threshold Calibration
        calibrations = {}
        if patient_context:
            raw_calibs = await self.agent.calibrate_thresholds(valid_labs, patient_context)
            # Guardrail 1: Clamp adjustments to max +/- 40% of standard bounds
            for t_name, adj in raw_calibs.items():
                lab_obj = next((l for l in valid_labs if l.test_name == t_name), None)
                if lab_obj and lab_obj.min_reference and lab_obj.max_reference:
                    safe_min = lab_obj.min_reference * 0.6
                    safe_max = lab_obj.max_reference * 1.4
                    final_min = max(safe_min, adj.get("min_reference") or lab_obj.min_reference)
                    final_max = min(safe_max, adj.get("max_reference") or lab_obj.max_reference)
                    calibrations[t_name] = {"min": final_min, "max": final_max, "rationale": adj.get("rationale", "Calibrating ranges for patient context...")}

        # 3. Yield Transition Animation events
        for lab in valid_labs:
            calib = calibrations.get(lab.test_name)
            if calib:
                adj_min, adj_max = calib["min"], calib["max"]
                new_sev = self.agent.classify_locally(lab, adj_min, adj_max)
                old_sev = self.agent.classify_locally(lab)
                transition_res = AnalyzedResult(
                    test_name=lab.test_name, result=lab.result, unit=lab.unit,
                    severity=new_sev, original_severity=old_sev if old_sev != new_sev else None,
                    explanation=f"Calibration: {calib.get('rationale')}",
                    next_steps="...", status="processing_llm", range_source="patient_adjusted",
                    patient_context=patient_context,
                    min_reference=adj_min, max_reference=adj_max,
                    original_min=lab.min_reference, original_max=lab.max_reference,
                    urgency="...", routing_specialty="..."
                )
                yield transition_res

        # Priority Sort based on the CURRENT (adjusted) severity
        SEVERITY_RANK = {"Critical": 0, "Warning": 1, "Normal": 2, "unclassified": 3}
        valid_labs.sort(key=lambda l: SEVERITY_RANK.get(
            self.agent.classify_locally(l, calibrations.get(l.test_name, {}).get("min"), calibrations.get(l.test_name, {}).get("max")), 99
        ))

        # 4. Process in Parallel Batches
        batch_size = 5
        for i in range(0, len(valid_labs), batch_size):
            batch = valid_labs[i:i+batch_size]
            tasks = []
            for lab in batch:
                calib = calibrations.get(lab.test_name)
                source = "patient_adjusted" if calib else "standard"
                mn = calib["min"] if calib else None
                mx = calib["max"] if calib else None
                
                tasks.append(
                    asyncio.get_event_loop().run_in_executor(
                        None, self.agent.analyze_single, lab, patient_context, source, mn, mx
                    )
                )
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for lab, res in zip(batch, results):
                if isinstance(res, Exception):
                    yield AnalyzedResult(
                        test_name=lab.test_name, result=lab.result, unit=lab.unit,
                        severity="Unknown", explanation=f"Error: {str(res)}",
                        next_steps="Retry later.", status="error"
                    )
                else:
                    yield res
            
            if i + batch_size < len(valid_labs):
                await asyncio.sleep(RATE_LIMIT_DELAY_SECONDS)

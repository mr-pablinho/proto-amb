import warnings
import os

# --- CRITICAL FIX: Suppress warnings BEFORE importing agents ---
# This ensures the warning is silenced before the library loads
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")
os.environ["GRPC_VERBOSITY"] = "ERROR" # Silences low-level gRPC logs
os.environ["GLOG_minloglevel"] = "2"   # Silences TensorFlow/JAX logs often used by GenAI
# -----------------------------------------------------------

import time
import json
import google.generativeai as genai
import config
from schemas import FileIndex, RoutingDecision, AuditResult
from pypdf import PdfReader
from typing import List, Type, Dict, Optional, Tuple, Any
from rich.console import Console

console = Console()

class RateLimitManager:
    def __init__(self):
        self.last_call = 0
        self.interval = 60 / config.RATE_LIMIT_CALLS

    def wait(self):
        now = time.time()
        elapsed = now - self.last_call
        if elapsed < self.interval:
            time.sleep(self.interval - elapsed)
        self.last_call = time.time()

rate_limiter = RateLimitManager()

def configure_genai():
    genai.configure(api_key=config.GOOGLE_API_KEY)

def extract_text_from_pdf(filepath: str) -> str:
    try:
        reader = PdfReader(filepath)
        text = ""
        for page in reader.pages:
            extract = page.extract_text()
            if extract:
                text += extract + "\n"
        return text[:30000] 
    except Exception as e:
        return f"Error reading PDF: {e}"

class BaseAgent:
    # --- CHANGED: Accept temperature in init ---
    def __init__(self, model_name, temperature):
        self.model_name = model_name
        self.temperature = temperature
        self.model = genai.GenerativeModel(model_name)

    def generate_structured(self, prompt: str, schema: Type) -> Tuple[Optional[Any], Dict]:
        rate_limiter.wait()
        usage = {"input_tokens": 0, "output_tokens": 0}
        
        try:
            # --- CHANGED: Pass temperature to generation_config ---
            response = self.model.generate_content(
                prompt,
                generation_config={
                    "response_mime_type": "application/json",
                    "temperature": self.temperature 
                }
            )
            
            if response.usage_metadata:
                usage["input_tokens"] = response.usage_metadata.prompt_token_count
                usage["output_tokens"] = response.usage_metadata.candidates_token_count
            
            if usage["input_tokens"] == 0:
                try:
                    count_resp = self.model.count_tokens(prompt)
                    usage["input_tokens"] = count_resp.total_tokens
                except:
                    pass

            return schema.model_validate_json(response.text), usage
            
        except Exception as e:
            console.print(f"[bold red]API Error:[/bold red] {e}")
            return None, usage

class CatalogerAgent(BaseAgent):
    def __init__(self):
        # Pass Specific Temp
        super().__init__(config.MODEL_CATALOGER, config.TEMP_CATALOGER)

    def analyze_file(self, filepath: str) -> Tuple[Optional[FileIndex], Dict]:
        import os
        filename = os.path.basename(filepath)
        content = extract_text_from_pdf(filepath)
        
        prompt = f"""
        You are a Forensic Document Analyst.
        Target File: {filename}
        
        Analyze the text below. Ignore the filename.
        1. List every Environmental Plan, Baseline Component, or Social Program.
        2. List every Table and Figure caption exactly as written.
        3. Summarize the content.
        4. Map topics to page ranges (approximate).

        Input Text:
        {content}
        
        **STRICT JSON OUTPUT**:
        Return a SINGLE JSON object.
        Required Structure:
        {{
            "filename": "{filename}",
            "topics_detected": ["Topic 1", "Topic 2"],
            "tables_and_figures": ["Table 1: ..."],
            "content_summary": "Summary text...",
            "page_ranges": {{"Topic 1": "1-3"}}
        }}
        """
        # Return tuple: (Result, Usage)
        result, usage = self.generate_structured(prompt, FileIndex)
        if result: 
            result.filename = filename 
        return result, usage

class RouterAgent(BaseAgent):
    def __init__(self):
        # Pass Specific Temp
        super().__init__(config.MODEL_ROUTER, config.TEMP_ROUTER)

    def route(self, requirement: str, project_index: List[Dict]) -> Tuple[Optional[RoutingDecision], Dict]:
        index_str = json.dumps(project_index, indent=2)
        
        prompt = f"""
        You are a Strategic Legal Librarian.
        
        **Goal**: Select the specific PDF files needed to verify this Audit Requirement/Query: 
        "{requirement}"
        
        **Project Index**:
        {index_str}
        
        **Logic**: 
        1. Search the index for topics matching the requirement.
        2. Identify Dependencies: If a requirement implies a need for both a Methodology (text) and Evidence (Annexes/Tables), select ALL files that complete the picture.
        3. Be strict on relevance.
        
        **OUTPUT FORMAT**:
        Return a single JSON object:
        {{
            "selected_filenames": ["file1.pdf", "file2.pdf"],
            "reasoning": "Explanation here"
        }}
        """
        return self.generate_structured(prompt, RoutingDecision)

class AuditorAgent(BaseAgent):
    def __init__(self):
        # Pass Specific Temp
        super().__init__(config.MODEL_AUDITOR, config.TEMP_AUDITOR)

    def audit(self, prompt_input: str, legal_context: str, file_contents: Dict[str, str]) -> Tuple[Optional[AuditResult], Dict]:
        
        combined_evidence = ""
        for fname, text in file_contents.items():
            combined_evidence += f"\n--- CONTENT OF FILE: {fname} ---\n{text}\n"

        prompt = f"""
        You are a Senior Environmental Auditor (Ecuador).
        
        {prompt_input}
        
        **Legal Context (Normativa)**:
        {legal_context}
        
        **Evidence (Full Text from Selected Files)**:
        {combined_evidence}
        
        **Constraint**: Verify if the technical evidence meets the legal threshold. 
        Output the AuditResult JSON. Reasoning must be in Spanish.
        
        **Instruction Guidelines**:
        - If status is "NO CUMPLE", provide a single sentence in Spanish starting with an infinitive verb (e.g., "Incluir...", "Presentar...", "Corregir...") that tells the proponent what must be done to comply.
        - If status is "CUMPLE", use "Ninguna acción requerida".

        Structure:
        {{
            "status": "CUMPLE" | "NO CUMPLE",
            "reasoning": "...",
            "legal_base": "...",
            "evidence_location": "...",
            "instruction": "..."
        }}
        """
        return self.generate_structured(prompt, AuditResult)
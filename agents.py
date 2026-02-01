import time
import json
import google.generativeai as genai
import config
from schemas import FileIndex, RoutingDecision, AuditResult
from pypdf import PdfReader
from typing import List, Type, Dict, Optional
from rich.console import Console

console = Console()

class RateLimitManager:
    """Simple rate limiter with exponential backoff."""
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
        return text[:30000] # Truncate for token limits in PoC
    except Exception as e:
        return f"Error reading PDF: {e}"

class BaseAgent:
    def __init__(self, model_name):
        self.model = genai.GenerativeModel(model_name)

    def generate_structured(self, prompt: str, schema: Type):
        rate_limiter.wait()
        try:
            # Using Gemini 1.5 JSON mode
            response = self.model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            return schema.model_validate_json(response.text)
        except Exception as e:
            console.print(f"[bold red]API Validation Error:[/bold red] {e}")
            # Optional: Print the raw text to debug what the AI actually sent
            # console.print(f"[dim]Raw response: {response.text}[/dim]")
            return None

class CatalogerAgent(BaseAgent):
    def __init__(self):
        super().__init__(config.MODEL_CATALOGER)

    def analyze_file(self, filepath: str) -> Optional[FileIndex]:
        import os
        filename = os.path.basename(filepath)
        content = extract_text_from_pdf(filepath)
        
        # IMPROVED PROMPT: Explicit JSON structure to prevent nesting errors
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
        You must return a SINGLE JSON object (not a list). Do not nest it under any root key like "data" or "index".
        
        Required Structure:
        {{
            "filename": "{filename}",
            "topics_detected": ["Topic 1", "Topic 2"],
            "tables_and_figures": ["Table 1: ..."],
            "content_summary": "Summary text...",
            "page_ranges": {{"Topic 1": "1-3"}}
        }}
        """
        result = self.generate_structured(prompt, FileIndex)
        # No need to manually set filename if the prompt enforces it, 
        # but we keep it safe:
        if result: 
            result.filename = filename 
        return result

class RouterAgent(BaseAgent):
    def __init__(self):
        super().__init__(config.MODEL_ROUTER)

    def route(self, requirement: str, project_index: List[Dict]) -> Optional[RoutingDecision]:
        index_str = json.dumps(project_index, indent=2)
        
        prompt = f"""
        You are a Strategic Legal Librarian.
        
        **Goal**: Select the specific PDF files needed to verify this Audit Requirement: "{requirement}".
        
        **Project Index**:
        {index_str}
        
        **Logic**: 
        1. Search the index for topics matching the requirement.
        2. Identify Dependencies: If a requirement implies a need for both a Methodology (text) and Evidence (Annexes/Tables), select ALL files that complete the picture.
        3. Be strict on relevance.
        
        **OUTPUT FORMAT**:
        Return a single JSON object matching this structure exactly:
        {{
            "selected_filenames": ["file1.pdf", "file2.pdf"],
            "reasoning": "Explanation here"
        }}
        """
        return self.generate_structured(prompt, RoutingDecision)

class AuditorAgent(BaseAgent):
    def __init__(self):
        super().__init__(config.MODEL_AUDITOR)

    def audit(self, requirement: str, legal_context: str, file_contents: Dict[str, str]) -> AuditResult:
        
        combined_evidence = ""
        for fname, text in file_contents.items():
            combined_evidence += f"\n--- CONTENT OF FILE: {fname} ---\n{text}\n"

        prompt = f"""
        You are a Senior Environmental Auditor (Ecuador).
        
        **Task**: Determine compliance for the requirement: "{requirement}".
        
        **Legal Context (Normativa)**:
        {legal_context}
        
        **Evidence (Full Text from Selected Files)**:
        {combined_evidence}
        
        **Constraint**: Verify if the technical evidence meets the legal threshold. 
        Output the AuditResult JSON. Reasoning must be in Spanish.
        
        Structure:
        {{
            "status": "CUMPLE" | "NO CUMPLE" | "PARCIAL",
            "reasoning": "...",
            "legal_base": "...",
            "evidence_location": "..."
        }}
        """
        return self.generate_structured(prompt, AuditResult)
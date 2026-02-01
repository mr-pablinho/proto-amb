from typing import List, Dict, Optional
from pydantic import BaseModel, Field

class FileIndex(BaseModel):
    """Output from the Cataloger Agent."""
    filename: str
    topics_detected: List[str] = Field(description="List of specific environmental plans or components found.")
    tables_and_figures: List[str] = Field(description="Explicit list of Tables (e.g., 'Table 1: Noise Limits') or Maps.")
    content_summary: str = Field(description="Detailed summary of the file content.")
    page_ranges: Dict[str, str] = Field(description="Mapping of topics to page ranges (e.g., {'Waste Plan': '4-8'}).")

class ProjectIndex(BaseModel):
    """The master index for the entire project."""
    files: List[FileIndex]

class RoutingDecision(BaseModel):
    """Output from the Router Agent."""
    selected_filenames: List[str] = Field(description="List of exact filenames relevant to the requirement.")
    reasoning: str = Field(description="Brief explanation of why these files were selected.")

class AuditResult(BaseModel):
    """Output from the Auditor Agent."""
    status: str = Field(description="CUMPLE, NO CUMPLE, or PARCIAL")
    reasoning: str = Field(description="Technical reasoning in Spanish.")
    legal_base: str = Field(description="The legal article used for verification.")
    evidence_location: str = Field(description="Where the evidence was found (Page/Section).")
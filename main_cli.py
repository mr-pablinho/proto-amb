import os
import json
import glob
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.status import Status
from rich.layout import Layout
from rich import box

import config
from agents import CatalogerAgent, RouterAgent, AuditorAgent, extract_text_from_pdf, configure_genai
from rag_engine import LegalRAG
from schemas import FileIndex

# Initialize UI
console = Console()

def load_or_build_index(cataloger: CatalogerAgent) -> list:
    """Manages the caching logic for the Deep Content Index."""
    if os.path.exists(config.INDEX_FILE) and not config.FORCE_REINDEX:
        console.print("[green]✓ Index found. Loading from cache...[/green]")
        with open(config.INDEX_FILE, "r") as f:
            data = json.load(f)
            return data
    
    console.print("[yellow]! Index missing or refresh requested. Starting Deep Content Scan...[/yellow]")
    pdf_files = glob.glob(os.path.join(config.PDF_DIR, "*.pdf"))
    
    project_index = []
    
    with console.status("[bold blue]Cataloger Agent working...") as status:
        for pdf in pdf_files:
            status.update(f"Scanning content of: {os.path.basename(pdf)}")
            file_index = cataloger.analyze_file(pdf)
            if file_index:
                project_index.append(file_index.model_dump())
    
    # Save cache
    with open(config.INDEX_FILE, "w") as f:
        json.dump(project_index, f, indent=2)
    
    return project_index

def display_index(index_data):
    table = Table(title="MAATE AI: Deep Content Index", box=box.ROUNDED)
    table.add_column("Filename", style="cyan", no_wrap=True)
    table.add_column("Topics Detected", style="magenta")
    table.add_column("Tables/Figures", style="green")
    
    for entry in index_data:
        topics = ", ".join(entry['topics_detected'][:3]) + "..."
        tables = ", ".join(entry['tables_and_figures'][:2])
        if len(entry['tables_and_figures']) > 2: tables += "..."
        table.add_row(entry['filename'], topics, tables)
    
    console.print(table)

def main():
    console.rule("[bold green]MAATE AI: Auditor Ambiental[/bold green]")
    configure_genai()
    
    # 1. Initialize Engines
    rag = LegalRAG()
    # Ingest dummy legal text (In real world, this loops over ./leyes)
    legal_text_raw = extract_text_from_pdf("./data/leyes/Reglamento_Ambiental_TULSMA.pdf")
    rag.ingest_text(legal_text_raw, "Reglamento TULSMA")
    
    # 2. Agents
    cataloger = CatalogerAgent()
    router = RouterAgent()
    auditor = AuditorAgent()
    
    # 3. Cataloging Phase
    project_index = load_or_build_index(cataloger)
    display_index(project_index)
    
    # 4. Audit Phase
    with open(config.CHECKLIST_FILE, "r", encoding='utf-8') as f:
        checklist = json.load(f)
        
    for item in checklist:
        req_id = item['id']
        req_text = item['requirement']
        
        console.rule(f"[bold]Auditing: {req_id}[/bold]")
        console.print(f"Requirement: {req_text}")
        
        # A. Routing
        with console.status("[bold cyan]Router Agent: Identifying dependencies...[/bold cyan]"):
            routing_decision = router.route(req_text, project_index)
        
        console.print(f"[dim]Selected Files: {routing_decision.selected_filenames}[/dim]")
        
        # Check if files exist
        if not routing_decision.selected_filenames:
            console.print("[red]No relevant files found in index. Skipping.[/red]")
            continue

        # B. Context & Content Loading
        legal_context = rag.retrieve_context(req_text)
        
        file_contents = {}
        for fname in routing_decision.selected_filenames:
            path = os.path.join(config.PDF_DIR, fname)
            if os.path.exists(path):
                file_contents[fname] = extract_text_from_pdf(path)
        
        # C. Audit Execution
        with console.status("[bold red]Auditor Agent: Verifying compliance...[/bold red]"):
            audit_result = auditor.audit(req_text, legal_context, file_contents)
            
        # D. Display Result
        color = "green" if audit_result.status == "CUMPLE" else "red"
        if audit_result.status == "PARCIAL": color = "yellow"
        
        r_panel = Panel(
            f"[bold]Status:[/bold] [{color}]{audit_result.status}[/{color}]\n"
            f"[bold]Legal Base:[/bold] {audit_result.legal_base}\n"
            f"[bold]Evidence:[/bold] {audit_result.evidence_location}\n\n"
            f"[italic]{audit_result.reasoning}[/italic]",
            title=f"Audit Result for {req_id}",
            border_style=color
        )
        console.print(r_panel)
        console.print("\n")

if __name__ == "__main__":
    main()
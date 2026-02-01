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
    # Check if index exists and we are not forcing a re-index
    if os.path.exists(config.INDEX_FILE) and not config.FORCE_REINDEX:
        console.print("[green]✓ Index found. Loading from cache...[/green]")
        try:
            with open(config.INDEX_FILE, "r") as f:
                data = json.load(f)
                # Simple check to ensure file isn't empty or corrupted
                if data: 
                    return data
        except json.JSONDecodeError:
            console.print("[yellow]! Cache file corrupted. Re-indexing...[/yellow]")

    console.print("[yellow]! Index missing, empty, or refresh requested. Starting Deep Content Scan...[/yellow]")
    
    # Ensure PDF directory exists
    if not os.path.exists(config.PDF_DIR):
        console.print(f"[bold red]Error:[/bold red] PDF Directory not found at {config.PDF_DIR}")
        return []

    pdf_files = glob.glob(os.path.join(config.PDF_DIR, "*.pdf"))
    
    if not pdf_files:
        console.print(f"[bold red]Error:[/bold red] No PDF files found in {config.PDF_DIR}")
        return []

    project_index = []
    
    with console.status("[bold blue]Cataloger Agent working...") as status:
        for pdf in pdf_files:
            status.update(f"Scanning content of: {os.path.basename(pdf)}")
            file_index = cataloger.analyze_file(pdf)
            if file_index:
                project_index.append(file_index.model_dump())
            else:
                console.print(f"[red]Failed to analyze {os.path.basename(pdf)}[/red]")
    
    # Save cache
    with open(config.INDEX_FILE, "w") as f:
        json.dump(project_index, f, indent=2)
    
    return project_index

def display_index(index_data):
    table = Table(title="MAATE AI: Deep Content Index", box=box.ROUNDED)
    table.add_column("Filename", style="cyan", no_wrap=True)
    table.add_column("Topics Detected", style="magenta")
    table.add_column("Tables/Figures", style="green")
    
    if not index_data:
        console.print("[red]Warning: Index is empty.[/red]")
        return

    for entry in index_data:
        topics = ", ".join(entry.get('topics_detected', [])[:3]) + "..."
        
        tables_list = entry.get('tables_and_figures', [])
        tables = ", ".join(tables_list[:2])
        if len(tables_list) > 2: tables += "..."
        
        table.add_row(entry.get('filename', 'Unknown'), topics, tables)
    
    console.print(table)

def main():
    console.rule("[bold green]MAATE AI: Auditor Ambiental[/bold green]")
    configure_genai()
    
    # 1. Initialize Engines
    rag = LegalRAG()
    
    # Ingest dummy legal text (Ensure this file exists via create_test_data.py)
    legal_path = os.path.join(config.LEGAL_DIR, "Reglamento_Ambiental_TULSMA.pdf")
    if os.path.exists(legal_path):
        legal_text_raw = extract_text_from_pdf(legal_path)
        rag.ingest_text(legal_text_raw, "Reglamento TULSMA")
    else:
        console.print(f"[yellow]Warning: Legal text not found at {legal_path}[/yellow]")
    
    # 2. Agents
    cataloger = CatalogerAgent()
    router = RouterAgent()
    auditor = AuditorAgent()
    
    # 3. Cataloging Phase
    project_index = load_or_build_index(cataloger)
    display_index(project_index)

    if not project_index:
        console.print("[bold red]CRITICAL: Project index is empty. Cannot proceed with audit.[/bold red]")
        return
    
    # 4. Audit Phase
    if not os.path.exists(config.CHECKLIST_FILE):
        console.print(f"[bold red]Error: Checklist file not found at {config.CHECKLIST_FILE}[/bold red]")
        return

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
        
        # --- SAFETY CHECK: Handle API Failures ---
        if not routing_decision:
            console.print("[bold red]Error: Router Agent failed to make a decision (API Error). Skipping.[/bold red]")
            continue
        # -----------------------------------------
        
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
            else:
                console.print(f"[yellow]Warning: Router selected {fname}, but file was not found on disk.[/yellow]")
        
        if not file_contents:
            console.print("[red]Error: Could not read content from selected files.[/red]")
            continue

        # C. Audit Execution
        with console.status("[bold red]Auditor Agent: Verifying compliance...[/bold red]"):
            audit_result = auditor.audit(req_text, legal_context, file_contents)
            
        if not audit_result:
             console.print("[bold red]Error: Auditor Agent failed to generate result. Skipping.[/bold red]")
             continue

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
import os
import json
import glob
import csv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.status import Status
from rich import box

import config
from agents import CatalogerAgent, RouterAgent, AuditorAgent, extract_text_from_pdf, configure_genai
from rag_engine import LegalRAG
from logger import AuditLogger

# Initialize UI and Logger
console = Console()
audit_logger = AuditLogger()

# --- HELPER: CSV TO JSON CONVERTER ---
def ensure_checklist_exists():
    """
    Checks if audit_checklist.json exists. If not, tries to build it 
    from the specific CSV file uploaded by the user.
    """
    json_path = config.CHECKLIST_FILE
    # Update this filename if your CSV name changes
    csv_path = "Checklist Borrador - Gemini 2.xlsx - Reformula la tabla generada ant.csv" 
    
    if os.path.exists(json_path):
        return True

    if not os.path.exists(csv_path):
        console.print(f"[yellow]Warning: Neither {json_path} nor {csv_path} found. Please ensure data exists.[/yellow]")
        return False

    console.print(f"[cyan]Info: Converting '{csv_path}' to JSON checklist...[/cyan]")
    
    checklist = []
    try:
        with open(csv_path, mode='r', encoding='utf-8-sig') as csvfile: # utf-8-sig handles Excel CSVs
            reader = csv.DictReader(csvfile)
            for i, row in enumerate(reader):
                # Map CSV columns to JSON fields
                req_text = row.get('Requisito', '').strip()
                if not req_text: continue # Skip empty rows

                item = {
                    "id": f"REQ-{i+1:03d}",
                    "chapter": row.get('Capítulo y Sección', ''),
                    "requirement": req_text,
                    "criteria": row.get('Criterio de Cumplimiento', ''),
                    "expected_evidence": row.get('Evidencia', '')
                }
                checklist.append(item)
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(checklist, f, indent=4, ensure_ascii=False)
        
        console.print(f"[green]✓ Conversion successful. {len(checklist)} requirements loaded.[/green]")
        return True
        
    except Exception as e:
        console.print(f"[bold red]Error converting CSV: {e}[/bold red]")
        return False

# --- CORE LOGIC ---

def load_or_build_index(cataloger: CatalogerAgent) -> list:
    """Manages the caching logic for the Deep Content Index."""
    if os.path.exists(config.INDEX_FILE) and not config.FORCE_REINDEX:
        console.print("[green]✓ Index found. Loading from cache...[/green]")
        try:
            with open(config.INDEX_FILE, "r") as f:
                data = json.load(f)
                if data: return data
        except json.JSONDecodeError:
            pass # Fall through to re-index

    console.print("[yellow]! Index missing or refresh requested. Starting Deep Content Scan...[/yellow]")
    
    pdf_files = glob.glob(os.path.join(config.PDF_DIR, "*.pdf"))
    if not pdf_files:
        console.print(f"[bold red]Error: No PDF files found in {config.PDF_DIR}[/bold red]")
        return []

    project_index = []
    
    # We use a status spinner for the active work, but print permanent logs for success
    with console.status("[bold blue]Cataloger Agent working...") as status:
        for pdf in pdf_files:
            filename = os.path.basename(pdf)
            status.update(f"Scanning content of: {filename}")
            
            file_index = cataloger.analyze_file(pdf)
            
            if file_index:
                project_index.append(file_index.model_dump())
                console.print(f"[green]✓ Indexed: {filename}[/green]")
            else:
                console.print(f"[red]x Failed to analyze: {filename}[/red]")
    
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
        tables = ", ".join(entry.get('tables_and_figures', [])[:2])
        if len(entry.get('tables_and_figures', [])) > 2: tables += "..."
        table.add_row(entry.get('filename', 'Unknown'), topics, tables)
    
    console.print(table)

def main():
    console.rule("[bold green]MAATE AI: Auditor Ambiental[/bold green]")
    configure_genai()
    
    # 0. Prepare Data
    if not ensure_checklist_exists():
        return

    # 1. Initialize RAG (Legal Context)
    rag = LegalRAG()
    legal_files = glob.glob(os.path.join(config.LEGAL_DIR, "*.pdf"))
    
    if not legal_files:
        console.print(f"[yellow]Warning: No legal files found in {config.LEGAL_DIR}[/yellow]")
    else:
        # Only ingest if database is empty (or if you manually cleared data/db)
        if rag.collection.count() == 0:
            console.print(f"[blue]Ingesting {len(legal_files)} Legal Framework files...[/blue]")
            
            with console.status("[bold blue]Indexing Legal Documents...[/bold blue]"):
                for legal_path in legal_files:
                    filename = os.path.basename(legal_path)
                    legal_text_raw = extract_text_from_pdf(legal_path)
                    
                    if len(legal_text_raw) > 100:
                        rag.ingest_text(legal_text_raw, source_name=filename)
                        console.print(f"[green]✓ Indexed: {filename}[/green]")
                    else:
                        console.print(f"[red]x Skipped (Empty/Unreadable): {filename}[/red]")
        else:
            console.print("[dim]Legal DB already exists. Using cached embeddings.[/dim]")
    
    # 2. Agents
    cataloger = CatalogerAgent()
    router = RouterAgent()
    auditor = AuditorAgent()
    
    # 3. Cataloging Phase
    project_index = load_or_build_index(cataloger)
    display_index(project_index)
    
    if not project_index:
        console.print("[bold red]CRITICAL: Project index is empty. Cannot proceed.[/bold red]")
        return

    # 4. Audit Phase
    with open(config.CHECKLIST_FILE, "r", encoding='utf-8') as f:
        checklist = json.load(f)
        
    for item in checklist:
        req_id = item['id']
        req_text = item['requirement']
        criteria = item.get('criteria', 'N/A')
        evidence_hint = item.get('expected_evidence', 'N/A')
        
        console.rule(f"[bold]Auditing: {req_id}[/bold]")
        console.print(f"Requirement: {req_text}")
        console.print(f"[dim cyan]Target Evidence: {evidence_hint}[/dim cyan]")
        
        # A. Smart Routing
        search_query = f"{req_text} (Evidence needed: {evidence_hint})"
        
        with console.status("[bold cyan]Router Agent: Identifying dependencies...[/bold cyan]"):
            # Tuple unpacking: result, usage
            routing_decision, router_usage = router.route(search_query, project_index)
        
        # Handle skipped/failed routing
        if not routing_decision or not routing_decision.selected_filenames:
            console.print("[red]No relevant files found in index. Skipping.[/red]")
            
            # LOGGING: Skipped
            audit_logger.log_requirement(
                req_id, req_text,
                router_data={
                    'model': config.MODEL_ROUTER,
                    'input': router_usage.get('input_tokens', 0),
                    'output': router_usage.get('output_tokens', 0),
                    'files': "None",
                    'reasoning': "No relevant files found (Filtered by Router)"
                },
                auditor_data={
                    'model': config.MODEL_AUDITOR,
                    'input': 0, 'output': 0, 'status': "SKIPPED", 'reasoning': "N/A"
                }
            )
            continue

        console.print(f"[dim]Selected Files: {routing_decision.selected_filenames}[/dim]")

        # B. Context & Content Loading
        legal_context = rag.retrieve_context(req_text)
        
        file_contents = {}
        for fname in routing_decision.selected_filenames:
            path = os.path.join(config.PDF_DIR, fname)
            if os.path.exists(path):
                file_contents[fname] = extract_text_from_pdf(path)
            else:
                console.print(f"[yellow]Warning: File {fname} missing from disk.[/yellow]")
        
        if not file_contents:
            continue

        # C. Audit Execution
        with console.status("[bold red]Auditor Agent: Verifying compliance...[/bold red]"):
            
            rich_prompt = f"""
            REQUIREMENT: {req_text}
            
            STRICT COMPLIANCE CRITERIA:
            {criteria}
            
            EXPECTED EVIDENCE DESCRIPTION:
            {evidence_hint}
            """
            
            # Tuple unpacking: result, usage
            audit_result, auditor_usage = auditor.audit(rich_prompt, legal_context, file_contents)
            
        if not audit_result:
             console.print("[bold red]Error: Auditor failed. Skipping.[/bold red]")
             continue

        # LOGGING: Success
        audit_logger.log_requirement(
            req_id, req_text,
            router_data={
                'model': config.MODEL_ROUTER,
                'input': router_usage.get('input_tokens', 0),
                'output': router_usage.get('output_tokens', 0),
                'files': str(routing_decision.selected_filenames),
                'reasoning': routing_decision.reasoning
            },
            auditor_data={
                'model': config.MODEL_AUDITOR,
                'input': auditor_usage.get('input_tokens', 0),
                'output': auditor_usage.get('output_tokens', 0),
                'status': audit_result.status,
                'reasoning': audit_result.reasoning
            }
        )

        # D. Display Result
        color = "green" if audit_result.status == "CUMPLE" else "red"
        if audit_result.status == "PARCIAL": color = "yellow"
        
        r_panel = Panel(
            f"[bold]Status:[/bold] [{color}]{audit_result.status}[/{color}]\n"
            f"[bold]Legal Base:[/bold] {audit_result.legal_base}\n"
            f"[bold]Evidence Found:[/bold] {audit_result.evidence_location}\n\n"
            f"[italic]{audit_result.reasoning}[/italic]",
            title=f"Audit Result for {req_id}",
            border_style=color
        )
        console.print(r_panel)
        console.print("\n")

if __name__ == "__main__":
    main()
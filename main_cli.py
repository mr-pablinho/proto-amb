import os
import json
import glob
import csv
import time
import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.status import Status
from rich import box

import config
from agents import CatalogerAgent, RouterAgent, AuditorAgent, extract_text_from_pdf, configure_genai
from rag_engine import LegalRAG
from logger import AuditLogger

# Initialize UI
console = Console()
# Initialize Logger (Now creates 3 files with timestamps)
audit_logger = AuditLogger()

# --- HELPER: INPUT FOLDER ---
def get_eia_folder_input():
    """Asks user for the EIA folder path and validates it."""
    console.rule("[bold cyan]Configuration[/bold cyan]")
    while True:
        folder_path = console.input("[bold green]Enter the path to the folder containing EIA PDFs:[/bold green] ").strip()
        
        # Handle quotes if user drags and drops folder in terminal
        folder_path = folder_path.replace('"', '').replace("'", "")
        
        if os.path.isdir(folder_path):
            pdf_count = len(glob.glob(os.path.join(folder_path, "*.pdf")))
            if pdf_count > 0:
                console.print(f"[green]✓ Found {pdf_count} PDF files in: {folder_path}[/green]")
                return folder_path
            else:
                console.print(f"[yellow]Warning: The folder '{folder_path}' exists but contains no PDFs.[/yellow]")
                confirm = console.input("Continue anyway? (y/n): ")
                if confirm.lower() == 'y': return folder_path
        else:
            console.print(f"[bold red]Error: Directory not found: {folder_path}[/bold red]")

# --- HELPER: CSV TO JSON CONVERTER ---
def ensure_checklist_exists():
    json_path = config.CHECKLIST_FILE
    csv_path = "Checklist Borrador - Gemini 2.xlsx - Reformula la tabla generada ant.csv" 
    
    if os.path.exists(json_path):
        return True

    if not os.path.exists(csv_path):
        console.print(f"[yellow]Warning: Neither {json_path} nor {csv_path} found.[/yellow]")
        return False

    console.print(f"[cyan]Info: Converting '{csv_path}' to JSON checklist...[/cyan]")
    checklist = []
    try:
        with open(csv_path, mode='r', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile)
            for i, row in enumerate(reader):
                req_text = row.get('Requisito', '').strip()
                if not req_text: continue
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
        return True
    except Exception as e:
        console.print(f"[bold red]Error converting CSV: {e}[/bold red]")
        return False

# --- CORE LOGIC ---

def load_or_build_index(cataloger: CatalogerAgent, pdf_dir: str) -> list:
    """Uses the provided pdf_dir instead of config default."""
    # Note: If PDF folder changes, we should probably force reindex or use separate cache files.
    # For PoC, we assume if index exists, it matches the project. 
    # To be safe, let's force reindex if the user changes folders in a real app.
    
    if os.path.exists(config.INDEX_FILE) and not config.FORCE_REINDEX:
        console.print("[green]✓ Index found. Loading from cache...[/green]")
        try:
            with open(config.INDEX_FILE, "r") as f:
                data = json.load(f)
                if data: return data
        except json.JSONDecodeError:
            pass 

    console.print("[yellow]! Index missing or refresh requested. Starting Deep Content Scan...[/yellow]")
    
    pdf_files = glob.glob(os.path.join(pdf_dir, "*.pdf"))
    project_index = []
    
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

def main():
    # 1. Start Global Timer
    global_start_time = time.time()
    run_start_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    console.rule("[bold green]MAATE AI: Auditor Ambiental[/bold green]")
    
    # 2. Get User Input (EIA Folder)
    eia_folder = get_eia_folder_input()
    # Update config dynamically
    config.PDF_DIR = eia_folder 
    
    configure_genai()
    
    if not ensure_checklist_exists(): return

    # 3. Initialize RAG & Collect Legal Files Metadata
    rag = LegalRAG()
    legal_files = glob.glob(os.path.join(config.LEGAL_DIR, "*.pdf"))
    legal_filenames = [os.path.basename(f) for f in legal_files]
    
    if not legal_files:
        console.print(f"[yellow]Warning: No legal files found in {config.LEGAL_DIR}[/yellow]")
    else:
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
            console.print("[dim]Legal DB already exists.[/dim]")
    
    # 4. Agents
    cataloger = CatalogerAgent()
    router = RouterAgent()
    auditor = AuditorAgent()
    
    # 5. Cataloging Phase
    project_index = load_or_build_index(cataloger, config.PDF_DIR)
    
    # 6. Audit Phase
    with open(config.CHECKLIST_FILE, "r", encoding='utf-8') as f:
        checklist = json.load(f)

    # Track processed files for metadata
    processed_files = [entry['filename'] for entry in project_index]
    
    console.print(f"\n[bold]Starting Audit of {len(checklist)} Requirements...[/bold]\n")

    for item in checklist:
        req_start_time = time.time() # Start Req Timer
        
        req_id = item['id']
        req_text = item['requirement']
        criteria = item.get('criteria', 'N/A')
        evidence_hint = item.get('expected_evidence', 'N/A')
        
        console.rule(f"[bold]Auditing: {req_id}[/bold]")
        console.print(f"Requirement: {req_text}")
        
        # A. Smart Routing
        search_query = f"{req_text} (Evidence needed: {evidence_hint})"
        
        with console.status("[bold cyan]Router Agent...[/bold cyan]"):
            routing_decision, router_usage = router.route(search_query, project_index)
        
        if not routing_decision or not routing_decision.selected_filenames:
            console.print("[red]Skipping: No relevant files found.[/red]")
            req_duration = time.time() - req_start_time
            
            audit_logger.log_requirement(
                req_id, req_text, req_duration,
                router_data={
                    'model': config.MODEL_ROUTER,
                    'input': router_usage.get('input_tokens', 0),
                    'output': router_usage.get('output_tokens', 0),
                    'files': "None", 'reasoning': "No relevant files found"
                },
                auditor_data={
                    'model': config.MODEL_AUDITOR,
                    'input': 0, 'output': 0, 'status': "SKIPPED", 'reasoning': "N/A"
                }
            )
            continue

        console.print(f"[dim]Selected: {routing_decision.selected_filenames}[/dim]")

        # B. Context & Content
        legal_context = rag.retrieve_context(req_text)
        file_contents = {}
        for fname in routing_decision.selected_filenames:
            path = os.path.join(config.PDF_DIR, fname)
            if os.path.exists(path):
                file_contents[fname] = extract_text_from_pdf(path)
        
        if not file_contents: continue

        # C. Auditor
        with console.status("[bold red]Auditor Agent...[/bold red]"):
            rich_prompt = f"""
            REQUIREMENT: {req_text}
            STRICT COMPLIANCE CRITERIA: {criteria}
            EXPECTED EVIDENCE DESCRIPTION: {evidence_hint}
            """
            audit_result, auditor_usage = auditor.audit(rich_prompt, legal_context, file_contents)

        # D. Logging & Display
        req_duration = time.time() - req_start_time # End Req Timer

        if not audit_result:
             console.print("[bold red]Auditor Error.[/bold red]")
             continue

        # Log to CSVs
        audit_logger.log_requirement(
            req_id, req_text, req_duration,
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

        color = "green" if audit_result.status == "CUMPLE" else "red"
        if audit_result.status == "PARCIAL": color = "yellow"
        
        console.print(Panel(
            f"[bold]Status:[/bold] [{color}]{audit_result.status}[/{color}]\n"
            f"[bold]Evidence:[/bold] {audit_result.evidence_location}\n"
            f"[italic]{audit_result.reasoning}[/italic]",
            title=f"Result {req_id} ({req_duration:.1f}s)", border_style=color
        ))
        console.print("\n")

    # 7. Finalize Metadata Log
    global_end_time = time.time()
    total_duration = global_end_time - global_start_time
    run_end_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    metadata = {
        "run_start": run_start_str,
        "run_end": run_end_str,
        "total_duration_seconds": round(total_duration, 2),
        "input_folder": eia_folder,
        "files_analyzed": processed_files,
        "legal_files_used": legal_filenames,
        "configuration": {
            "model_cataloger": config.MODEL_CATALOGER,
            "model_router": config.MODEL_ROUTER,
            "model_auditor": config.MODEL_AUDITOR,
            "rate_limit": config.RATE_LIMIT_CALLS
        }
    }
    
    audit_logger.log_metadata(metadata)
    console.print(f"[bold green]Audit Complete. Logs saved to ./logs/[/bold green]")
    console.print(f"Total Time: {total_duration:.2f} seconds")

if __name__ == "__main__":
    main()
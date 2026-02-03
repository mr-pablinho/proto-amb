import streamlit as st
import os
import tempfile
import json
import glob
import time
import pandas as pd

# Import project modules
import config
from agents import CatalogerAgent, RouterAgent, AuditorAgent, extract_text_from_pdf, configure_genai
from rag_engine import LegalRAG
from logger import AuditLogger

# --- CONFIGURACIÓN & SETUP ---
st.set_page_config(
    page_title="MAATE AI | Auditor Ambiental",
    page_icon="🌿",
    layout="wide"
)

# Inicializar Estado de la Sesión (Session State)
if "audit_results" not in st.session_state:
    st.session_state.audit_results = []
if "processing_complete" not in st.session_state:
    st.session_state.processing_complete = False
if "temp_dir" not in st.session_state:
    st.session_state.temp_dir = tempfile.mkdtemp()
if "project_index" not in st.session_state:
    st.session_state.project_index = []

# --- FUNCIONES AUXILIARES ---

def save_uploaded_files(uploaded_files):
    """Guarda los archivos subidos a un directorio temporal."""
    saved_paths = []
    # Limpiar directorio para evitar mezclar ejecuciones previas
    for f in os.listdir(st.session_state.temp_dir):
        os.remove(os.path.join(st.session_state.temp_dir, f))
        
    for uploaded_file in uploaded_files:
        file_path = os.path.join(st.session_state.temp_dir, uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        saved_paths.append(file_path)
    return saved_paths

def load_checklist():
    """Carga la lista de verificación (checklist), convirtiendo de CSV a JSON si es necesario."""
    json_path = config.CHECKLIST_FILE
    if os.path.exists(json_path):
        with open(json_path, "r", encoding='utf-8') as f:
            return json.load(f)
    return []

def load_local_cache():
    """
    Carga el índice JSON persistente generado por la CLI localmente.
    Retorna un diccionario: {'archivo.pdf': {datos_indice}}
    """
    if os.path.exists(config.INDEX_FILE):
        try:
            with open(config.INDEX_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Crear diccionario de búsqueda por nombre de archivo
                return {item['filename']: item for item in data}
        except Exception as e:
            st.warning(f"No se pudo cargar la caché local: {e}")
    return {}

# --- BARRA LATERAL (SIDEBAR) ---
with st.sidebar:
    # Usando un icono genérico de hoja/ambiente
    st.image("https://cdn-icons-png.flaticon.com/512/2913/2913465.png", width=50)
    st.title("Panel de Control")
    
    st.markdown("### 1. Configuración")
    api_key = st.text_input("Google API Key", type="password", help="Dejar vacío si ya está configurado en variables de entorno.")
    if api_key:
        config.GOOGLE_API_KEY = api_key
        configure_genai()
    
    st.markdown("### 2. Marco Legal")
    legal_docs = glob.glob(os.path.join(config.LEGAL_DIR, "*.pdf"))
    st.caption(f"Se encontraron {len(legal_docs)} documentos legales en el sistema.")
    
    st.divider()
    if st.button("Reiniciar Sesión"):
        st.session_state.audit_results = []
        st.session_state.processing_complete = False
        st.session_state.project_index = []
        st.rerun()

# --- PÁGINA PRINCIPAL ---
st.title("🌿 MAATE AI: Auditor Ambiental Automatizado")
st.markdown("""
Este sistema utiliza **Inteligencia Artificial Multi-Agente** para auditar Estudios de Impacto Ambiental (EIA) 
frente a la normativa ecuatoriana (COA/TULSMA).
""")

# 1. SECCIÓN DE CARGA DE ARCHIVOS
st.divider()
st.subheader("📂 1. Cargar Documentación EIA")
uploaded_files = st.file_uploader(
    "Arrastre y suelte sus archivos PDF aquí (Plan de Manejo, Anexos, Fichas, etc.)", 
    type=["pdf"], 
    accept_multiple_files=True
)

if uploaded_files:
    st.info(f"Cargados {len(uploaded_files)} archivos listos para procesar.")

# 2. SECCIÓN DE PROCESAMIENTO
st.divider()
st.subheader("🚀 2. Proceso de Auditoría")

start_btn = st.button("Iniciar Auditoría de Cumplimiento", type="primary", disabled=not uploaded_files)

if start_btn:
    # A. Configurar Entorno
    configure_genai()
    saved_paths = save_uploaded_files(uploaded_files)
    config.PDF_DIR = st.session_state.temp_dir # Apuntar config al directorio temporal
    
    # Inicializar Agentes
    cataloger = CatalogerAgent()
    router = RouterAgent()
    auditor = AuditorAgent()
    rag = LegalRAG()
    
    progress_bar = st.progress(0)
    status_container = st.status("Inicializando Sistema...", expanded=True)

    try:
        # B. Ingesta del Marco Legal
        with status_container:
            st.write("📚 Verificando Base de Conocimiento Legal (RAG)...")
            if rag.collection.count() == 0:
                legal_files = glob.glob(os.path.join(config.LEGAL_DIR, "*.pdf"))
                for l_file in legal_files:
                    txt = extract_text_from_pdf(l_file)
                    rag.ingest_text(txt, source_name=os.path.basename(l_file))
            st.write("✅ Contexto Legal Listo.")

        # C. Catalogación de Archivos (CON CACHÉ INTELIGENTE)
        with status_container:
            st.write("🔍 Catalogando Documentos del Proyecto (Análisis Forense)...")
            
            # Cargar caché local de la CLI para ahorrar tokens
            local_cache = load_local_cache()
            if local_cache:
                st.toast(f"Cargados {len(local_cache)} archivos desde caché local.", icon="💾")
            
            project_index = []
            file_count = len(saved_paths)
            
            for idx, pdf_path in enumerate(saved_paths):
                fname = os.path.basename(pdf_path)
                
                # Verificar si el archivo existe en caché local
                if fname in local_cache:
                    st.write(f"📑 Encontrado en caché: {fname} (Omitiendo escaneo)")
                    project_index.append(local_cache[fname])
                else:
                    st.write(f"🕵️ Escaneando nuevo archivo: {fname}...")
                    f_index, _ = cataloger.analyze_file(pdf_path)
                    if f_index:
                        project_index.append(f_index.model_dump())
                
                progress_bar.progress((idx + 1) / file_count * 0.1) # Primer 10% es catalogación
            
            st.session_state.project_index = project_index
            st.write(f"✅ Indexados {len(project_index)} archivos.")

        # D. Ejecutar Bucle de Auditoría
        checklist = load_checklist()
        results = []
        total_reqs = len(checklist)
        
        for i, item in enumerate(checklist):
            req_id = item['id']
            req_text = item['requirement']
            criteria = item.get('criteria', 'N/A')
            evidence_hint = item.get('expected_evidence', 'N/A')

            with status_container:
                st.markdown(f"**Auditando {req_id}:** {req_text[:80]}...")
            
            # --- AGENTE ENRUTADOR (ROUTER) ---
            # Nota: Mantenemos el prompt interno en inglés si el modelo rinde mejor, 
            # pero la UI es totalmente español.
            search_query = f"{req_text} (Evidence needed: {evidence_hint})"
            routing_decision, _ = router.route(search_query, project_index)
            
            if not routing_decision or not routing_decision.selected_filenames:
                results.append({
                    "id": req_id,
                    "requirement": req_text,
                    "status": "SKIPPED",
                    "reasoning": "El Enrutador no encontró archivos relevantes para este requisito.",
                    "evidence_location": "N/A",
                    "files_used": []
                })
                continue
            
            # --- PREPARAR DATOS ---
            legal_context = rag.retrieve_context(req_text)
            file_contents = {}
            for fname in routing_decision.selected_filenames:
                path = os.path.join(st.session_state.temp_dir, fname)
                if os.path.exists(path):
                    file_contents[fname] = extract_text_from_pdf(path)
            
            if not file_contents:
                continue

            # --- AGENTE AUDITOR ---
            rich_prompt = f"""
            REQUIREMENT: {req_text}
            STRICT COMPLIANCE CRITERIA: {criteria}
            EXPECTED EVIDENCE DESCRIPTION: {evidence_hint}
            """
            audit_result, _ = auditor.audit(rich_prompt, legal_context, file_contents)

            if audit_result:
                results.append({
                    "id": req_id,
                    "requirement": req_text,
                    "status": audit_result.status,
                    "reasoning": audit_result.reasoning, # El agente ya retorna esto en español
                    "evidence_location": audit_result.evidence_location,
                    "files_used": routing_decision.selected_filenames
                })
            
            # Actualizar Progreso
            progress = 0.1 + ((i + 1) / total_reqs * 0.9)
            progress_bar.progress(progress)

        st.session_state.audit_results = results
        st.session_state.processing_complete = True
        status_container.update(label="¡Auditoría Completa!", state="complete", expanded=False)

    except Exception as e:
        st.error(f"Ocurrió un error: {e}")

# 3. VISUALIZACIÓN DE RESULTADOS
if st.session_state.processing_complete:
    st.divider()
    st.subheader("📊 Informe de Cumplimiento")
    
    df = pd.DataFrame(st.session_state.audit_results)
    if not df.empty:
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Requisitos", len(df))
        col2.metric("Cumplimiento Total (CUMPLE)", len(df[df['status'] == 'CUMPLE']))
        col3.metric("No Conformidades / Parciales", len(df[df['status'].isin(['NO CUMPLE', 'PARCIAL'])]))
    
    for res in st.session_state.audit_results:
        color = "grey"
        icon = "⚪"
        estilo_estado = res['status']
        
        if res['status'] == "CUMPLE":
            color = "green" 
            icon = "✅"
        elif res['status'] == "NO CUMPLE": 
            color = "red"
            icon = "❌"
        elif res['status'] == "PARCIAL": 
            color = "orange"
            icon = "⚠️"
        elif res['status'] == "SKIPPED":
            estilo_estado = "OMITIDO (Sin Información)"
            
        with st.expander(f"{icon} [{res['id']}] {estilo_estado}: {res['requirement']}"):
            st.markdown(f"**Razonamiento Técnico:**\n{res['reasoning']}")
            st.markdown(f"**Ubicación de la Evidencia:** `{res['evidence_location']}`")
            st.caption(f"Archivos Analizados: {', '.join(res['files_used'])}")
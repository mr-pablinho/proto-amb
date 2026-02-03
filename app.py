import streamlit as st
import os
import tempfile
import json
import glob
import time
import pandas as pd

# Importar módulos del proyecto
import config
from agents import CatalogerAgent, RouterAgent, AuditorAgent, extract_text_from_pdf, configure_genai
from rag_engine import LegalRAG
from logger import AuditLogger

# --- CONFIGURACIÓN & SETUP ---
st.set_page_config(
    page_title="🤖 MAATE AI",
    layout="centered"
)

# --- SISTEMA DE TIPOGRAFÍA (VERSIÓN SEGURA) ---
st.markdown("""
<style>
    /* 1. IMPORTAR FUENTES */
    @import url('https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@400;700&family=Roboto:wght@300;400;500;700&family=Space+Grotesk:wght@300;400;500;600;700&display=swap');

    /* 2. APLICAR FUENTES SOLO A ELEMENTOS DE TEXTO (NO A ICONOS) */
    
    /* Cuerpo y textos generales */
    html, body, p, li, label, .stMarkdown, .stText {
        font-family: 'Roboto', sans-serif !important;
    }
    
    /* Inputs y Botones */
    input, textarea, select, button {
        font-family: 'Roboto', sans-serif !important;
    }
    
    /* Encabezados */
    h1, h2, h3, h4, h5, h6, .stTitle {
        font-family: 'Space Grotesk', sans-serif !important;
        font-weight: 600 !important;
        letter-spacing: -0.5px;
    }

    /* 3. LOGS Y CÓDIGO (Roboto Mono) */
    code, .stCodeBlock, .stJson {
        font-family: 'Roboto Mono', monospace !important;
    }
    
    /* Widget de Estado (Logs) - Específico */
    div[data-testid="stStatusWidget"] div p {
        font-family: 'Roboto Mono', monospace !important;
        font-size: 0.9em !important;
    }
    /* Título del Widget de Estado */
    div[data-testid="stStatusWidget"] header p {
        font-family: 'Space Grotesk', sans-serif !important;
        font-weight: 600 !important;
    }

    /* 4. MÉTRICAS (Números grandes) */
    [data-testid="stMetricValue"] {
        font-family: 'Space Grotesk', sans-serif !important;
    }

    /* LIMPIEZA */
    .stDeployButton {display:none;}
    footer {visibility: hidden;}
    #MainMenu {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# Inicializar Estado
if "audit_results" not in st.session_state:
    st.session_state.audit_results = []
if "processing_complete" not in st.session_state:
    st.session_state.processing_complete = False
if "temp_dir" not in st.session_state:
    st.session_state.temp_dir = tempfile.mkdtemp()

# --- FUNCIONES AUXILIARES ---

def save_uploaded_files(uploaded_files):
    saved_paths = []
    # Limpiar directorio temporal para nueva ejecución
    for f in os.listdir(st.session_state.temp_dir):
        os.remove(os.path.join(st.session_state.temp_dir, f))
        
    for uploaded_file in uploaded_files:
        file_path = os.path.join(st.session_state.temp_dir, uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        saved_paths.append(file_path)
    return saved_paths

def load_checklist():
    json_path = config.CHECKLIST_FILE
    if os.path.exists(json_path):
        with open(json_path, "r", encoding='utf-8') as f:
            return json.load(f)
    return []

def load_local_cache():
    if os.path.exists(config.INDEX_FILE):
        try:
            with open(config.INDEX_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return {item['filename']: item for item in data}
        except Exception:
            pass
    return {}

# --- INTERFAZ DE USUARIO ---

# Encabezado
st.title("🤖 MAATE AI (PoC)")
st.subheader("**Sistema Automatizado de Verificación Normativa**")

# 1. CARGA DE ARCHIVOS
st.divider()
st.subheader("1. Carga de Documentación")

# Verificación silenciosa de API Key
if not config.GOOGLE_API_KEY:
    st.error("⚠️ Falta configuración de API Key en .env")
    st.stop()

uploaded_files = st.file_uploader(
    "Seleccione los archivos PDF (Plan de Manejo, Anexos, Fichas):", 
    type=["pdf"], 
    accept_multiple_files=True
)

if uploaded_files:
    st.caption(f"✅ {len(uploaded_files)} archivos listos para procesar.")

# 2. EJECUCIÓN
st.divider()
st.subheader("2. Proceso de Auditoría")

start_btn = st.button("Iniciar Verificación", type="primary", disabled=not uploaded_files)

if start_btn:
    # Preparación
    configure_genai()
    saved_paths = save_uploaded_files(uploaded_files)
    config.PDF_DIR = st.session_state.temp_dir 
    
    cataloger = CatalogerAgent()
    router = RouterAgent()
    auditor = AuditorAgent()
    rag = LegalRAG()
    
    # Placeholder de Acción Actual
    current_action_display = st.info("🚀 Iniciando protocolos del sistema...")
    
    # Caja de Logs
    with st.status("📝 Registro de Operaciones", expanded=True) as status_box:
        
        try:
            # A. MARCO LEGAL
            current_action_display.info("📚 Paso 1/3: Verificando Normativa Legal...")
            status_box.update(label="📚 Cargando contexto legal...", state="running")
            time.sleep(2)

            if rag.collection.count() == 0:
                legal_files = glob.glob(os.path.join(config.LEGAL_DIR, "*.pdf"))
                for l_file in legal_files:
                    st.write(f"Leyendo: {os.path.basename(l_file)}")
                    txt = extract_text_from_pdf(l_file)
                    rag.ingest_text(txt, source_name=os.path.basename(l_file))
            st.write("✅ Marco legal cargado.")

            # B. CATALOGACIÓN
            current_action_display.info("🔍 Paso 2/3: Analizando estructura de documentos...")
            status_box.update(label="🔍 Indexando documentos...", state="running")
            
            local_cache = load_local_cache()
            project_index = []
            
            for pdf_path in saved_paths:
                fname = os.path.basename(pdf_path)
                st.write(f"Analizando: **{fname}**")
                time.sleep(2)

                if fname in local_cache:
                    st.caption(f"└─ Recuperado de memoria caché.")
                    project_index.append(local_cache[fname])
                else:
                    f_index, _ = cataloger.analyze_file(pdf_path)
                    if f_index:
                        project_index.append(f_index.model_dump())
            
            st.session_state.project_index = project_index
            st.write(f"✅ Indexación terminada ({len(project_index)} archivos).")

            # C. AUDITORÍA
            current_action_display.info("⚖️ Paso 3/3: Cruzando requisitos contra evidencia...")
            
            checklist = load_checklist()
            results = []
            total = len(checklist)
            
            for i, item in enumerate(checklist):
                req_id = item['id']
                req_text = item['requirement']
                criteria = item.get('criteria', 'N/A')
                evidence_hint = item.get('expected_evidence', 'N/A')

                status_box.update(label=f"⚖️ Auditando punto {i+1} de {total}: {req_id}", state="running")
                st.markdown(f"**{req_id}:** {req_text[:60]}...")
                
                # Router
                search_query = f"{req_text} (Evidence needed: {evidence_hint})"
                routing_decision, _ = router.route(search_query, project_index)
                
                if not routing_decision or not routing_decision.selected_filenames:
                    st.caption("⚠️ Sin archivos relevantes.")
                    results.append({
                        "id": req_id, "requirement": req_text, "status": "SKIPPED",
                        "reasoning": "No se encontraron documentos relacionados.",
                        "evidence_location": "N/A", "files_used": []
                    })
                    continue

                # Preparar archivos
                legal_context = rag.retrieve_context(req_text)
                file_contents = {}
                for fname in routing_decision.selected_filenames:
                    path = os.path.join(st.session_state.temp_dir, fname)
                    if os.path.exists(path):
                        file_contents[fname] = extract_text_from_pdf(path)

                if not file_contents:
                    continue

                # Auditor
                rich_prompt = f"REQUIREMENT: {req_text}\nCRITERIA: {criteria}\nEVIDENCE: {evidence_hint}"
                audit_result, _ = auditor.audit(rich_prompt, legal_context, file_contents)

                if audit_result:
                    icon = "✅" if audit_result.status == "CUMPLE" else "❌"
                    st.caption(f"└─ Resultado: {icon} {audit_result.status}")
                    
                    results.append({
                        "id": req_id,
                        "requirement": req_text,
                        "status": audit_result.status,
                        "reasoning": audit_result.reasoning,
                        "evidence_location": audit_result.evidence_location,
                        "files_used": routing_decision.selected_filenames
                    })
                
                time.sleep(2)

            st.session_state.audit_results = results
            st.session_state.processing_complete = True
            
            status_box.update(label="✅ Proceso completado. Despliegue para ver logs.", state="complete", expanded=False)
            current_action_display.success("¡Auditoría Finalizada!")
            time.sleep(2)
            current_action_display.empty()

        except Exception as e:
            current_action_display.error(f"Error: {e}")
            status_box.update(label="❌ Error crítico", state="error")

# 3. RESULTADOS
if st.session_state.processing_complete:
    st.divider()
    st.subheader("3. Informe de Cumplimiento")
    
    df = pd.DataFrame(st.session_state.audit_results)
    if not df.empty:
        col1, col2, col3 = st.columns(3)
        col1.metric("Requisitos", len(df))
        col2.metric("Cumplimiento", len(df[df['status'] == 'CUMPLE']))
        col3.metric("No Conformidad", len(df[df['status'].isin(['NO CUMPLE', 'PARCIAL'])]))
    
    st.write("")
    
    for res in st.session_state.audit_results:
        icon = "⚪"
        estilo_estado = res['status']
        
        if res['status'] == "CUMPLE":
            icon = "✅"
        elif res['status'] == "NO CUMPLE": 
            icon = "❌"
        elif res['status'] == "PARCIAL": 
            icon = "⚠️"
        elif res['status'] == "SKIPPED":
            icon = "⏭️"
            estilo_estado = "OMITIDO"
            
        with st.expander(f"{icon}  **{res['id']}** | {estilo_estado}"):
            st.markdown(f"**Requisito:**")
            st.markdown(res['requirement'])
            st.markdown("---")
            st.markdown(f"**Dictamen:**")
            st.markdown(res['reasoning'])
            st.caption(f"📍 Evidencia: {res['evidence_location']} | 📂 Archivos: {', '.join(res['files_used'])}")
import streamlit as st
import os
import tempfile
import json
import glob
import time
import datetime
import pandas as pd
import random

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
if "total_time" not in st.session_state:
    st.session_state.total_time = 0

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
            data = json.load(f)
            
            # Aplicar muestreo aleatorio si está configurado
            if config.AUDIT_CHECKLIST_LIMIT and isinstance(config.AUDIT_CHECKLIST_LIMIT, int):
                if config.AUDIT_CHECKLIST_LIMIT < len(data):
                    random.seed(config.RANDOM_SEED)
                    sampled_data = random.sample(data, config.AUDIT_CHECKLIST_LIMIT)
                    # Ordenar por ID para mantener el orden ascendente original
                    return sorted(sampled_data, key=lambda x: x['id'])
            return data
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
sleep_time = 1
# Encabezado
st.title("🤖 MAATE AI")
st.markdown("**Sistema Automatizado de Verificación Normativa (PoC)**")

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

force_reindex = st.toggle("Forzar re-indexación", value=False, help="Ignora la caché local y vuelve a analizar todos los documentos.")
start_btn = st.button("Iniciar Verificación", type="primary", disabled=not uploaded_files)


if start_btn:
    start_time = time.time()
    # Preparación
    configure_genai()
    saved_paths = save_uploaded_files(uploaded_files)
    config.PDF_DIR = st.session_state.temp_dir 
    
    cataloger = CatalogerAgent()
    router = RouterAgent()
    auditor = AuditorAgent()
    rag = LegalRAG()
    audit_logger = AuditLogger()
    total_run_cost = 0.0
    run_start_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Contenedores para Pasos (Persistentes)
    step1_container = st.empty()
    step2_container = st.empty()
    step3_container = st.empty()
    
    try:
        # --- PASO 1: MARCO LEGAL ---
        with step1_container.container():
            st.info("📚 Paso 1/3: Verificando Normativa Legal...")
            with st.status("Detalles del Marco Legal", expanded=True) as s1:
                if rag.collection.count() == 0:
                    legal_files = glob.glob(os.path.join(config.LEGAL_DIR, "*.pdf"))
                    for l_file in legal_files:
                        st.write(f"Leyendo: {os.path.basename(l_file)}")
                        txt = extract_text_from_pdf(l_file)
                        rag.ingest_text(txt, source_name=os.path.basename(l_file))
                st.write("✅ Marco legal cargado correctamente.")
                s1.update(label="📚 Marco Legal Listo", state="complete", expanded=False)
        
        # --- PASO 2: CATALOGACIÓN ---
        with step2_container.container():
            st.info("🔍 Paso 2/3: Analizando estructura de documentos...")
            with st.status("Detalles de Indexación", expanded=True) as s2:
                local_cache = load_local_cache()
                project_index = []
                for pdf_path in saved_paths:
                    fname = os.path.basename(pdf_path)
                    st.write(f"Analizando: ```{fname}```")
                    if fname in local_cache and not force_reindex:
                        st.caption(f"└─ Recuperado de memoria caché.")
                        project_index.append(local_cache[fname])
                    else:
                        f_index, usage = cataloger.analyze_file(pdf_path)
                        if f_index:
                            project_index.append(f_index.model_dump())
                            cost = audit_logger.log_catalog(
                                fname, "SUCCESS", config.MODEL_CATALOGER,
                                usage['input_tokens'], usage['output_tokens']
                            )
                            total_run_cost += cost
                        else:
                            audit_logger.log_catalog(
                                fname, "FAILED", config.MODEL_CATALOGER,
                                0, 0
                            )
                st.session_state.project_index = project_index
                st.write(f"✅ Indexación terminada ({len(project_index)} archivos).")
                s2.update(label="🔍 Documentos Indexados", state="complete", expanded=False)

        # --- PASO 3: AUDITORÍA ---
        with step3_container.container():
            st.info("⚖️ Paso 3/3: Cruzando requisitos contra evidencia...")
            with st.status("Detalles de la Auditoría", expanded=True) as s3:
                checklist = load_checklist()
                st.session_state.audit_results = []
                total = len(checklist)
                
                for i, item in enumerate(checklist):
                    req_id = item['id']
                    req_text = item['requirement']
                    criteria = item.get('criteria', 'N/A')
                    evidence_hint = item.get('expected_evidence', 'N/A')

                    req_start_time = time.time()
                    s3.update(label=f"⚖️ Auditando {i+1}/{total}: {req_id}", state="running")
                    st.markdown(f"**{req_id}:** {req_text[:60]}...")
                    
                    search_query = f"{req_text} (Evidence needed: {evidence_hint})"
                    routing_decision, router_usage = router.route(search_query, project_index)
                    
                    if not routing_decision or not routing_decision.selected_filenames:
                        st.caption("⚠️ Sin archivos relevantes.")
                        req_duration = time.time() - req_start_time
                        cost = audit_logger.log_requirement(
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
                        total_run_cost += cost
                        st.session_state.audit_results.append({
                            "id": req_id, "requirement": req_text, "status": "SKIPPED",
                            "reasoning": "No se encontraron documentos relacionados.",
                            "evidence_location": "N/A", "files_used": []
                        })
                        continue

                    legal_context = rag.retrieve_context(req_text)
                    file_contents = {}
                    for fname in routing_decision.selected_filenames:
                        path = os.path.join(st.session_state.temp_dir, fname)
                        if os.path.exists(path):
                            file_contents[fname] = extract_text_from_pdf(path)

                    if file_contents:
                        rich_prompt = f"REQUIREMENT: {req_text}\nCRITERIA: {criteria}\nEVIDENCE: {evidence_hint}"
                        audit_result, auditor_usage = auditor.audit(rich_prompt, legal_context, file_contents)

                        req_duration = time.time() - req_start_time
                        if audit_result:
                            cost = audit_logger.log_requirement(
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
                            total_run_cost += cost
                            icon = "✅" if audit_result.status == "CUMPLE" else "❌"
                            st.caption(f"└─ Resultado: {icon} {audit_result.status}")
                            st.session_state.audit_results.append({
                                "id": req_id, "requirement": req_text, "status": audit_result.status,
                                "reasoning": audit_result.reasoning,
                                "evidence_location": audit_result.evidence_location,
                                "files_used": routing_decision.selected_filenames
                            })
                
                # Metadata Final
                st.session_state.total_time = time.time() - start_time
                st.session_state.processing_complete = True
                
                run_end_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                legal_filenames = [os.path.basename(f) for f in glob.glob(os.path.join(config.LEGAL_DIR, "*.pdf"))]
                processed_files = [entry['filename'] for entry in st.session_state.project_index]
                
                metadata = {
                    "run_start": run_start_str,
                    "run_end": run_end_str,
                    "total_duration_seconds": round(st.session_state.total_time, 2),
                    "total_cost_estimated_usd": round(total_run_cost, 6),
                    "input_folder": "Streamlit Upload",
                    "files_analyzed": processed_files,
                    "legal_files_used": legal_filenames,
                    "configuration": {
                        "model_cataloger": config.MODEL_CATALOGER,
                        "model_router": config.MODEL_ROUTER,
                        "model_auditor": config.MODEL_AUDITOR,
                        "rate_limit": config.RATE_LIMIT_CALLS,
                        "sampling_limit": config.AUDIT_CHECKLIST_LIMIT
                    }
                }
                audit_logger.log_metadata(metadata)
                
                s3.update(label="⚖️ Auditoría Finalizada", state="complete", expanded=False)
    except Exception as e:
        st.error(f"Error crítico durante el proceso: {e}")

    # Mensaje Final (Fuera de contenedores)
    if st.session_state.processing_complete:
        st.success("El proceso ha concluido con éxito")

# 3. RESULTADOS
if st.session_state.audit_results:
    st.divider()
    st.subheader("3. Informe de Cumplimiento")
    
    df = pd.DataFrame(st.session_state.audit_results)
    if not df.empty:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Requisitos", len(df))
        col2.metric("Cumplimiento", len(df[df['status'] == 'CUMPLE']))
        col3.metric("No Conformidad", len(df[df['status'].isin(['NO CUMPLE', 'PARCIAL'])]))
        col4.metric("Tiempo Total", f"{st.session_state.total_time:.1f}s")
    
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
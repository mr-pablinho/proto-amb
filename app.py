import streamlit as st
import pandas as pd
import os
import time
import config

# Importamos la lógica legal (RAG Local)
from legal_engine import get_legal_vector_store, get_legal_basis

# Importamos la lógica del Agente Inteligente (Router + Analyzer)
# ASEGÚRATE DE HABER ACTUALIZADO eia_analyzer.py CON EL CÓDIGO DEL PASO ANTERIOR
from eia_analyzer import summarize_project_chapters, route_query, analyze_requirement_smart

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="MAATE AI Compliance Gatekeeper",
    page_icon="🇪🇨",
    layout="wide"
)

# --- ESTILOS CSS PERSONALIZADOS ---
st.markdown("""
    <style>
    .stProgress > div > div > div > div {
        background-color: #009933;
    }
    .status-box {
        padding: 10px;
        border-radius: 5px;
        border: 1px solid #ddd;
        margin-bottom: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# --- TÍTULO Y DESCRIPCIÓN ---
st.title("🇪🇨 MAATE AI: Revisor de Cumplimiento Ambiental")
st.markdown("""
**Arquitectura:** RAG Jerárquico (Router Agent).
El sistema cataloga el proyecto, identifica los capítulos relevantes para cada requisito y realiza la auditoría cruzando información con la Base Legal (COA, TULSMA, RAOHE).
""")

# --- SIDEBAR: CONFIGURACIÓN ---
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/2/2ea/Flag_of_Ecuador.svg/1200px-Flag_of_Ecuador.svg.png", width=50)
    st.header("Configuración")
    
    # Gestión de API KEY
    api_key_input = st.text_input("Google API Key", type="password", value=config.GOOGLE_API_KEY or "")
    if api_key_input:
        os.environ["GOOGLE_API_KEY"] = api_key_input
        config.GOOGLE_API_KEY = api_key_input
    
    st.divider()
    
    st.subheader("1. Cargar Proyecto")
    project_path = st.text_input("Ruta de carpeta (EIA):", placeholder="C:/MisDocumentos/Proyecto_Minero")
    
    st.subheader("2. Checklist de Auditoría")
    default_checks = [
        "Plan de Manejo Ambiental: Programa de Prevención y Mitigación",
        "Inventario Forestal (si aplica tala)",
        "Gestión de Desechos Peligrosos y Especiales",
        "Participación Ciudadana (Actas y Registros)",
        "Análisis de Riesgos Endógenos y Exógenos",
        "Certificado de Intersección (SNAP)",
        "Cronograma Valorado de Ejecución",
        "Plan de Cierre y Abandono"
    ]
    selected_checks = st.multiselect("Requisitos a verificar:", default_checks, default=default_checks[:3])
    
    st.divider()
    run_btn = st.button("🚀 Iniciar Auditoría", type="primary")
    
    if st.button("🧹 Limpiar Memoria"):
        st.session_state.clear()
        st.rerun()

# --- LÓGICA PRINCIPAL ---

if run_btn and project_path and config.GOOGLE_API_KEY:
    if not os.path.exists(project_path):
        st.error(f"❌ La ruta no existe: {project_path}")
        st.stop()

    # 1. INICIALIZAR BASE LEGAL (RAG LOCAL)
    # Esto es rápido gracias a ChromaDB local
    with st.spinner("⚖️ Cargando Normativa Ambiental (TULSMA, COA, RAOHE)..."):
        try:
            vector_db = get_legal_vector_store()
            st.toast("Base legal lista", icon="✅")
        except Exception as e:
            st.error(f"Error cargando leyes: {e}")
            st.stop()

    # 2. CATALOGACIÓN DEL PROYECTO (SOLO UNA VEZ)
    # Usamos Session State para no volver a leer los PDFs si ya lo hicimos
    if 'project_summaries' not in st.session_state or st.session_state.get('last_path') != project_path:
        
        st.info("📂 Proyecto nuevo detectado. Iniciando catalogación inteligente (esto toma unos segundos)...")
        progress_text = "Leyendo y resumiendo capítulos..."
        my_bar = st.progress(0, text=progress_text)
        
        try:
            # Llamada al agente catalogador
            summaries, full_contents = summarize_project_chapters(project_path)
            
            # Guardar en memoria de sesión
            st.session_state['project_summaries'] = summaries
            st.session_state['full_contents'] = full_contents
            st.session_state['last_path'] = project_path
            
            my_bar.progress(100, text="Catalogación completada.")
            time.sleep(1)
            my_bar.empty()
            
        except Exception as e:
            st.error(f"Error leyendo el proyecto: {e}")
            st.stop()
    else:
        st.success("📂 Usando catálogo de proyecto en memoria (Cache).")

    # Mostrar el "Mapa Mental" que creó la IA
    with st.expander("Ver Catálogo Inteligente del Proyecto (Archivos detectados)", expanded=False):
        st.json(st.session_state['project_summaries'])

    # 3. EJECUCIÓN DE LA AUDITORÍA
    st.divider()
    st.subheader(f"📋 Auditoría en curso ({len(selected_checks)} requisitos)")
    
    results_data = []
    audit_progress = st.progress(0)
    status_box = st.empty() # Contenedor dinámico para mensajes
    
    for i, req in enumerate(selected_checks):
        
        # --- FASE A: BÚSQUEDA LEGAL ---
        with status_box.container():
            st.write(f"**Requisito {i+1}/{len(selected_checks)}:** {req}")
            st.caption("1️⃣ Buscando base legal aplicable...")
            
        legal_context = get_legal_basis(req, vector_db)
        
        # --- FASE B: ENRUTAMIENTO (ROUTER) ---
        with status_box.container():
            st.caption("2️⃣ Agente Enrutador: Seleccionando capítulos relevantes...")
            
        routing_decision = route_query(req, st.session_state['project_summaries'])
        selected_files = routing_decision.get('relevant_files', [])
        reasoning_router = routing_decision.get('reasoning', 'N/A')
        
        # Feedback visual de qué decidió leer
        st.toast(f"Para '{req}' leeré: {len(selected_files)} archivos.", icon="👀")
        
        # --- FASE C: ANÁLISIS PROFUNDO (ANALYZER) ---
        with status_box.container():
            st.caption(f"3️⃣ Auditando contenido en: {selected_files}...")
        
        try:
            # Enviamos solo los archivos seleccionados y el contexto legal
            evaluation = analyze_requirement_smart(
                req, 
                legal_context, 
                st.session_state['full_contents'], 
                selected_files
            )
            
            # Pequeña pausa para no saturar si usas la versión Flash muy rápido
            time.sleep(2)

        except Exception as e:
            evaluation = {
                "estado": "ERROR TÉCNICO",
                "base_legal": "N/A",
                "evidencia": "Fallo en el análisis",
                "razonamiento": str(e)
            }

        # Guardar resultados
        results_data.append({
            "Requisito": req,
            "Estado": evaluation.get("estado", "INDEFINIDO"),
            "Base Legal": evaluation.get("base_legal", "No citada"),
            "Archivos Auditados": ", ".join(selected_files),
            "Evidencia Hallada": evaluation.get("evidencia", "Sin evidencia"),
            "Razonamiento AI": evaluation.get("razonamiento", "Sin razonamiento"),
            "Razón Selección Archivos": reasoning_router
        })
        
        audit_progress.progress((i + 1) / len(selected_checks))

    status_box.success("✅ Auditoría Finalizada.")

    # 4. VISUALIZACIÓN DE RESULTADOS
    df = pd.DataFrame(results_data)

    # Función para colorear la tabla
    def color_coding(val):
        val = str(val).upper()
        if 'NO CUMPLE' in val:
            return 'background-color: #ffcccc; color: #990000; font-weight: bold'
        elif 'CUMPLE' in val:
            return 'background-color: #ccffcc; color: #006600; font-weight: bold'
        elif 'ERROR' in val:
            return 'background-color: #ffffcc; color: #999900'
        return ''

    st.dataframe(
        df.style.applymap(color_coding, subset=['Estado']),
        use_container_width=True,
        column_config={
            "Razonamiento AI": st.column_config.TextColumn("Análisis Detallado", width="large"),
            "Evidencia Hallada": st.column_config.TextColumn("Evidencia", width="medium"),
        }
    )

    # Botón de Descarga
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        "📥 Descargar Informe CSV",
        csv,
        "reporte_auditoria_maate.csv",
        "text/csv",
        key='download-csv'
    )

elif run_btn and not project_path:
    st.warning("⚠️ Por favor ingresa la ruta de la carpeta del proyecto.")
elif run_btn and not config.GOOGLE_API_KEY:
    st.warning("⚠️ Por favor ingresa tu Google API Key.")
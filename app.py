import streamlit as st
import pandas as pd
import os
import config
from legal_engine import get_legal_vector_store, get_legal_basis
from eia_analyzer import load_project_content, analyze_requirement

# Configuración de página
st.set_page_config(page_title="MAATE AI Compliance Gatekeeper", layout="wide")

st.title("🇪🇨 MAATE AI: Revisor Automático de EIAs")
st.markdown("""
Esta herramienta utiliza **Inteligencia Artificial Híbrida** (RAG + Long Context) para auditar Estudios de Impacto Ambiental 
frente al COA, RCOA, TULSMA y RAOHE.
""")

# Sidebar
with st.sidebar:
    st.header("Configuración")
    
    api_key_input = st.text_input("Google API Key", type="password", value=config.GOOGLE_API_KEY)
    if api_key_input:
        config.GOOGLE_API_KEY = api_key_input
        os.environ["GOOGLE_API_KEY"] = api_key_input
    
    st.divider()
    
    st.subheader("1. Cargar Proyecto")
    project_path = st.text_input("Ruta de la carpeta del Proyecto:", placeholder="C:/ruta/a/mi_proyecto_eia")
    
    st.subheader("2. Checklist de Auditoría")
    # Lista de requisitos predefinidos (se puede expandir)
    default_checks = [
        "Plan de Manejo Ambiental: Programa de Prevención y Mitigación",
        "Inventario Forestal (si aplica tala)",
        "Gestión de Desechos Peligrosos y Especiales",
        "Participación Ciudadana (Actas y Registros)",
        "Análisis de Riesgos Endógenos y Exógenos",
        "Certificado de Intersección (SNAP)"
    ]
    selected_checks = st.multiselect("Seleccione requisitos a verificar:", default_checks, default=default_checks[:3])
    
    run_btn = st.button("🔍 Iniciar Auditoría", type="primary")

# Main Logic
if run_btn and project_path and config.GOOGLE_API_KEY:
    if not os.path.exists(project_path):
        st.error("La ruta de la carpeta no existe.")
    else:
        # 1. Inicializar Base Legal
        with st.spinner("📚 Cargando Normativa Ambiental (COA, RCOA, TULSMA...)..."):
            try:
                vector_db = get_legal_vector_store()
                st.success("Base legal indexada correctamente.")
            except Exception as e:
                st.error(f"Error cargando leyes: {e}")
                st.stop()

        # 2. Cargar Proyecto (Long Context)
        with st.spinner("🏗️ Leyendo y catalogando archivos del proyecto..."):
            try:
                project_text, file_list = load_project_content(project_path)
                st.info(f"Proyecto cargado: {len(file_list)} archivos procesados.")
                with st.expander("Ver archivos detectados"):
                    st.write(file_list)
            except Exception as e:
                st.error(f"Error leyendo proyecto: {e}")
                st.stop()

        # 3. Ejecutar Análisis
        st.divider()
        st.subheader("📋 Resultados de la Auditoría")
        
        results_data = []
        progress_bar = st.progress(0)
        
        for i, req in enumerate(selected_checks):
            st.write(f"**Analizando:** {req}...")
            
            # A. Buscar Ley Aplicable (RAG)
            legal_context = get_legal_basis(req, vector_db)
            
            # B. Verificar Cumplimiento (Gemini Pro)
            evaluation = analyze_requirement(req, legal_context, project_text)
            
            results_data.append({
                "Requisito": req,
                "Estado": evaluation.get("estado"),
                "Base Legal": evaluation.get("base_legal"),
                "Evidencia Hallada": evaluation.get("evidencia"),
                "Razonamiento AI": evaluation.get("razonamiento")
            })
            
            progress_bar.progress((i + 1) / len(selected_checks))
        
        # 4. Mostrar Tabla
        df = pd.DataFrame(results_data)
        
        # Estilizar la tabla (Color coding)
        def color_status(val):
            color = 'red' if 'NO' in str(val).upper() else 'green'
            return f'color: {color}; font-weight: bold'

        st.dataframe(df.style.applymap(color_status, subset=['Estado']), use_container_width=True)
        
        # Opción de descarga
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("Descargar Informe CSV", csv, "reporte_maate.csv", "text/csv")

elif run_btn:
    st.warning("Por favor ingrese la API Key y la ruta del proyecto.")
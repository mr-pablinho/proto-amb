import os
import json
from langchain_community.document_loaders import PyPDFLoader
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from typing import List
import config

# --- 1. MODELOS DE DATOS ---

class ChapterSummary(BaseModel):
    filename: str = Field(description="Nombre del archivo")
    topics: List[str] = Field(description="Lista de temas principales tratados")
    contains_tables: bool = Field(description="Si contiene tablas de datos")
    key_entities: List[str] = Field(description="Entidades clave mencionadas")
    summary: str = Field(description="Resumen denso del contenido")

class RoutingDecision(BaseModel):
    relevant_files: List[str] = Field(description="Lista exacta de nombres de archivos necesarios")
    reasoning: str = Field(description="Por qué se eligieron estos archivos")

class ComplianceResult(BaseModel):
    estado: str = Field(description="CUMPLE, NO CUMPLE, o NO APLICA")
    base_legal: str = Field(description="Artículos de ley citados")
    evidencia: str = Field(description="Cita textual del documento del proyecto")
    razonamiento: str = Field(description="Explicación del análisis")

# --- 2. LÓGICA DE CATALOGACIÓN (RESUMEN) ---

def summarize_project_chapters(folder_path):
    """
    Lee cada PDF y genera una 'Ficha Técnica'.
    Usa el modelo RÁPIDO (Flash).
    """
    # CORRECCIÓN AQUÍ: Usamos la variable de config, no el nombre fijo
    llm = ChatGoogleGenerativeAI(
        model=config.FAST_MODEL_NAME, 
        temperature=0, 
        google_api_key=config.GOOGLE_API_KEY
    )
    
    parser = JsonOutputParser(pydantic_object=ChapterSummary)
    
    summaries = []
    file_contents = {} 

    print("--- 🗂️  Iniciando Catalogación Inteligente ---")
    
    files = [f for f in os.listdir(folder_path) if f.endswith(".pdf")]
    
    prompt = PromptTemplate(
        template="""
        Eres un Bibliotecario Técnico experto en Estudios de Impacto Ambiental.
        Analiza el siguiente texto de un capítulo de un proyecto:
        
        TEXTO DEL ARCHIVO '{filename}':
        {text_sample} 
        
        Tu tarea es crear una Ficha Técnica JSON.
        Identifica temas clave (Agua, Suelo, Residuos, Social, Legal, Forestal, etc.).
        
        {format_instructions}
        """,
        input_variables=["filename", "text_sample"],
        partial_variables={"format_instructions": parser.get_format_instructions()}
    )
    
    chain = prompt | llm | parser

    for filename in files:
        print(f"   ... Catalogando: {filename}")
        path = os.path.join(folder_path, filename)
        try:
            loader = PyPDFLoader(path)
            docs = loader.load()
            
            # Unir texto
            full_text = "\n".join([d.page_content for d in docs])
            file_contents[filename] = full_text 
            
            # Muestra de texto (primeros 40k caracteres para el resumen rápido)
            text_sample = full_text[:40000] 
            
            summary = chain.invoke({"filename": filename, "text_sample": text_sample})
            summary['filename'] = filename 
            summaries.append(summary)
            
        except Exception as e:
            print(f"   ❌ Error resumiendo {filename}: {e}")
            summaries.append({
                "filename": filename, 
                "topics": ["Error"], 
                "contains_tables": False, 
                "key_entities": [], 
                "summary": "No procesable"
            })

    return summaries, file_contents

# --- 3. EL AGENTE ENRUTADOR (ROUTER) ---

def route_query(requirement, all_summaries):
    """
    Decide qué archivos son relevantes.
    Usa el modelo RÁPIDO (Flash).
    """
    # CORRECCIÓN AQUÍ: Usamos la variable de config
    llm = ChatGoogleGenerativeAI(
        model=config.FAST_MODEL_NAME, 
        temperature=0, 
        google_api_key=config.GOOGLE_API_KEY
    )
    
    parser = JsonOutputParser(pydantic_object=RoutingDecision)
    context_str = json.dumps(all_summaries, indent=2)
    
    prompt = PromptTemplate(
        template="""
        Eres un Gestor de Proyectos Ambientales. Tienes el siguiente catálogo de archivos:
        
        {summaries}
        
        Tu misión es encontrar evidencia para: "{requirement}"
        
        Selecciona ÚNICAMENTE los archivos relevantes.
        {format_instructions}
        """,
        input_variables=["summaries", "requirement"],
        partial_variables={"format_instructions": parser.get_format_instructions()}
    )
    
    chain = prompt | llm | parser
    return chain.invoke({"summaries": context_str, "requirement": requirement})

# --- 4. EL AGENTE AUDITOR (ANALYZER) ---

def analyze_requirement_smart(requirement, legal_context, project_file_contents, selected_filenames):
    """
    Analiza SOLO los archivos seleccionados.
    Usa el modelo POTENTE (Pro).
    """
    # Aquí usamos el modelo PRO definido en config
    llm = ChatGoogleGenerativeAI(
        model=config.MODEL_NAME, 
        temperature=0,
        google_api_key=config.GOOGLE_API_KEY
    )
    parser = JsonOutputParser(pydantic_object=ComplianceResult)

    specific_context = ""
    for fname in selected_filenames:
        if fname in project_file_contents:
            # Recortamos excesos si es muy grande, aunque PRO soporta mucho
            specific_context += f"\n--- ARCHIVO: {fname} ---\n{project_file_contents[fname]}\n"
    
    if not specific_context:
        return {
            "estado": "NO DETERMINABLE",
            "base_legal": "N/A",
            "evidencia": "El sistema no encontró archivos relevantes.",
            "razonamiento": "Router no seleccionó archivos."
        }

    prompt = PromptTemplate(
        template="""
        Eres un Auditor del MAATE.
        
        LEY: {legal_context}
        
        DOCUMENTOS PROYECTO: {project_context}
        
        REQUISITO: {requirement}
        
        Verifica cumplimiento.
        {format_instructions}
        """,
        input_variables=["legal_context", "project_context", "requirement"],
        partial_variables={"format_instructions": parser.get_format_instructions()}
    )

    chain = prompt | llm | parser
    return chain.invoke({
        "legal_context": legal_context,
        "project_context": specific_context,
        "requirement": requirement
    })
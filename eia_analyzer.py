import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
import config

# Definir estructura de salida estructurada
class ComplianceResult(BaseModel):
    estado: str = Field(description="CUMPLE, NO CUMPLE, o NO APLICA")
    base_legal: str = Field(description="Artículos específicos de la ley citados")
    evidencia: str = Field(description="Ubicación o cita textual del documento del proyecto")
    razonamiento: str = Field(description="Explicación breve del análisis")

def load_project_content(folder_path):
    """
    Carga TODO el texto de los PDFs del proyecto.
    Optimizado para Gemini 1.5 Pro (Contexto Largo).
    """
    full_text = ""
    file_map = [] # Para saber qué texto viene de qué archivo

    print(f"--- Leyendo proyecto desde: {folder_path} ---")
    
    files = [f for f in os.listdir(folder_path) if f.endswith(".pdf")]
    
    for filename in files:
        path = os.path.join(folder_path, filename)
        loader = PyPDFLoader(path)
        docs = loader.load()
        
        file_content = ""
        for doc in docs:
            file_content += doc.page_content + "\n"
        
        full_text += f"\n--- INICIO ARCHIVO: {filename} ---\n{file_content}\n--- FIN ARCHIVO: {filename} ---\n"
        file_map.append(filename)
        
    return full_text, file_map

def analyze_requirement(requirement, legal_context, project_full_text):
    """
    El 'Compliance Agent'. Compara Ley (RAG) vs Proyecto (Long Context).
    """
    llm = ChatGoogleGenerativeAI(
        model=config.MODEL_NAME,
        temperature=0,
        google_api_key=config.GOOGLE_API_KEY
    )

    parser = JsonOutputParser(pydantic_object=ComplianceResult)

    prompt_template = PromptTemplate(
        template="""
        Eres un Auditor Ambiental experto del Ministerio del Ambiente de Ecuador (MAATE).
        Tu tarea es verificar rigurosamente si un proyecto cumple con la normativa.

        CONTEXTO LEGAL (Extraído de COA, RCOA, TULSMA, RAOHE, etc.):
        {legal_context}

        DOCUMENTACIÓN DEL PROYECTO (Texto completo extraído):
        {project_context}

        REQUISITO A EVALUAR:
        {requirement}

        INSTRUCCIONES:
        1. Analiza el 'CONTEXTO LEGAL' para entender qué exige la ley sobre el requisito.
        2. Busca en la 'DOCUMENTACIÓN DEL PROYECTO' evidencia de cumplimiento.
        3. Si es un proyecto hidrocarburífero, prioriza RAOHE. Si es forestal, A.M. 134.
        4. Sé estricto. Si no hay evidencia clara, es 'NO CUMPLE'.
        
        Responde EXCLUSIVAMENTE en formato JSON con las siguientes claves:
        {format_instructions}
        """,
        input_variables=["legal_context", "project_context", "requirement"],
        partial_variables={"format_instructions": parser.get_format_instructions()}
    )

    chain = prompt_template | llm | parser

    try:
        result = chain.invoke({
            "legal_context": legal_context,
            "project_context": project_full_text,
            "requirement": requirement
        })
        return result
    except Exception as e:
        return {
            "estado": "ERROR",
            "base_legal": "N/A",
            "evidencia": "Error procesando solicitud",
            "razonamiento": str(e)
        }
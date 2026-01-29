import os
import shutil
# Importamos la gestión de Embeddings Locales (HuggingFace)
from langchain_huggingface import HuggingFaceEmbeddings
# Importamos el cargador de PDFs
from langchain_community.document_loaders import PyPDFLoader
# Importamos el divisor de texto
from langchain_text_splitters import RecursiveCharacterTextSplitter
# Importamos la base de datos vectorial Chroma
from langchain_chroma import Chroma
# Importamos nuestra configuración
import config

def get_legal_vector_store():
    """
    Gestiona la creación y carga de la base de datos vectorial de leyes.
    Utiliza un modelo local para evitar límites de API de Google.
    """
    
    # 1. Configurar el Modelo de Embeddings Local
    # Usamos 'all-MiniLM-L6-v2', es ligero, rápido y muy efectivo para español/inglés técnico.
    # Se descargará automáticamente la primera vez (aprox 80MB).
    print("--- ⚙️ Inicializando modelo de Embeddings Local (HuggingFace) ---")
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    # 2. Verificar si ya existe la base de datos
    if os.path.exists(config.VECTOR_DB_PATH) and os.listdir(config.VECTOR_DB_PATH):
        # Pequeña validación para asegurar que no esté corrupta
        try:
            vectorstore = Chroma(
                persist_directory=config.VECTOR_DB_PATH, 
                embedding_function=embeddings
            )
            # Hacemos una prueba rápida
            if vectorstore._collection.count() > 0:
                print("--- ✅ Cargando Base Legal existente desde disco ---")
                return vectorstore
        except Exception:
            print("--- ⚠️ Base de datos corrupta detectada. Re-indexando... ---")
            shutil.rmtree(config.VECTOR_DB_PATH) # Borrar si está dañada
    
    # 3. Si no existe, comenzamos el proceso de indexado (ETL)
    print("--- 📚 Indexando Base Legal (Localmente - Sin límites de API) ---")
    docs = []
    
    # Verificar carpeta de leyes
    if not os.path.exists(config.LEGAL_DOCS_PATH):
        os.makedirs(config.LEGAL_DOCS_PATH)
        raise FileNotFoundError(f"Por favor coloca los PDFs de leyes en la carpeta '{config.LEGAL_DOCS_PATH}'")

    files_found = [f for f in os.listdir(config.LEGAL_DOCS_PATH) if f.endswith(".pdf")]
    if not files_found:
        raise FileNotFoundError(f"No hay archivos PDF en la carpeta '{config.LEGAL_DOCS_PATH}'")

    # A. Cargar PDFs
    for filename in files_found:
        print(f"   📖 Leyendo archivo: {filename}...")
        file_path = os.path.join(config.LEGAL_DOCS_PATH, filename)
        try:
            loader = PyPDFLoader(file_path)
            loaded_docs = loader.load()
            # Añadir metadatos clave para citar la fuente después
            for doc in loaded_docs:
                doc.metadata["source_law"] = filename
            docs.extend(loaded_docs)
        except Exception as e:
            print(f"   ❌ Error leyendo {filename}: {e}")

    print(f"   ✅ Se leyeron {len(docs)} páginas en total.")

    # B. Dividir texto (Chunking)
    # Usamos un tamaño de chunk optimizado para modelos locales (1000 tokens aprox)
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, 
        chunk_overlap=200,
        separators=["\nArt.", "\nTITULO", "\nCAPITULO", "\n\n", " ", ""]
    )
    splits = text_splitter.split_documents(docs)
    print(f"--- ✂️ Total de fragmentos procesados: {len(splits)} ---")

    # C. Crear Vector Store (Embeddings)
    print("--- 🧠 Generando Embeddings y guardando en ChromaDB... ---")
    
    # Al ser local, podemos enviarlo todo de golpe. Chroma gestiona los lotes internamente.
    vectorstore = Chroma.from_documents(
        documents=splits, 
        embedding=embeddings, 
        persist_directory=config.VECTOR_DB_PATH
    )
    
    print("--- ✅ Indexación completada exitosamente. ---")
    return vectorstore

def get_legal_basis(query, vectorstore):
    """
    Busca los fragmentos legales más relevantes para un requisito.
    """
    # MMR (Maximal Marginal Relevance) ayuda a buscar diversidad en las respuestas
    # para no traer 5 veces el mismo artículo si está repetido.
    retriever = vectorstore.as_retriever(
        search_type="mmr", 
        search_kwargs={"k": 5, "fetch_k": 20}
    )
    
    try:
        docs = retriever.invoke(query)
        # Formateamos el texto para que el LLM entienda de dónde viene cada cita
        context_text = "\n\n".join([
            f"--- FUENTE: {d.metadata.get('source_law', 'Desconocido')} ---\nCONTENIDO LEGISLATIVO:\n{d.page_content}" 
            for d in docs
        ])
        return context_text
    except Exception as e:
        return f"Error recuperando base legal: {str(e)}"
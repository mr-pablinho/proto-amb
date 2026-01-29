import os
import time  # <--- IMPORTANTE: Necesario para hacer pausas
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
import config

def get_legal_vector_store():
    """
    Inicializa o carga el Vector Store con las leyes, respetando los límites de la API.
    """
    embeddings = GoogleGenerativeAIEmbeddings(
        model=config.EMBEDDING_MODEL, 
        google_api_key=config.GOOGLE_API_KEY,
        task_type="retrieval_document" # Optimización para búsqueda
    )

    # 1. Si ya existe la base de datos, la cargamos y terminamos rápido
    if os.path.exists(config.VECTOR_DB_PATH) and os.listdir(config.VECTOR_DB_PATH):
        print("--- ✅ Cargando Base Legal existente (Sin consumo de API) ---")
        return Chroma(persist_directory=config.VECTOR_DB_PATH, embedding_function=embeddings)
    
    # 2. Si no existe, comenzamos el proceso de indexado
    print("--- 📚 Indexando Base Legal (Modo Lento para evitar bloqueo de API) ---")
    docs = []
    
    if not os.path.exists(config.LEGAL_DOCS_PATH):
        os.makedirs(config.LEGAL_DOCS_PATH)
        raise FileNotFoundError(f"Coloca los PDFs en '{config.LEGAL_DOCS_PATH}'")

    # Cargar PDFs
    for filename in os.listdir(config.LEGAL_DOCS_PATH):
        if filename.endswith(".pdf"):
            print(f"   Leyendo: {filename}...")
            file_path = os.path.join(config.LEGAL_DOCS_PATH, filename)
            loader = PyPDFLoader(file_path)
            loaded_docs = loader.load()
            for doc in loaded_docs:
                doc.metadata["source_law"] = filename
            docs.extend(loaded_docs)

    # Dividir texto (Chunking)
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1500, # Un poco más pequeño para asegurar calidad
        chunk_overlap=200,
        separators=["\nArt.", "\nTITULO", "\nCAPITULO", "\n\n", " "]
    )
    splits = text_splitter.split_documents(docs)
    print(f"--- Total de fragmentos a procesar: {len(splits)} ---")

    # 3. CREACIÓN DEL VECTOR STORE POR LOTES (La Solución)
    # Inicializamos la DB vacía primero
    vectorstore = Chroma(
        embedding_function=embeddings, 
        persist_directory=config.VECTOR_DB_PATH
    )

    # Definimos el tamaño del lote (batch). 
    # La API gratuita suele tolerar unas 15-20 peticiones por minuto de forma segura.
    batch_size = 20 
    
    total_batches = len(splits) // batch_size + 1
    
    for i in range(0, len(splits), batch_size):
        batch = splits[i:i+batch_size]
        if not batch: continue
        
        print(f"   Procesando lote {i//batch_size + 1}/{total_batches}...")
        
        try:
            # Añadimos los documentos a la base de datos
            vectorstore.add_documents(batch)
            
            # --- EL SECRETO: PAUSA DE SEGURIDAD ---
            # Esperamos 5 segundos entre lotes para enfriar la API.
            # Si tienes muchos docs, esto tardará, pero no fallará.
            time.sleep(5) 
            
        except Exception as e:
            print(f"   ⚠️ Error en el lote {i}: {e}")
            print("   Esperando 60 segundos por si es un bloqueo temporal...")
            time.sleep(60)
            # Reintentar el mismo lote (lógica simple)
            try:
                vectorstore.add_documents(batch)
            except:
                print("   ❌ Lote fallido definitivamente. Saltando...")

    print("--- ✅ Indexación completada ---")
    return vectorstore

def get_legal_basis(query, vectorstore):
    # (El resto de la función sigue igual)
    retriever = vectorstore.as_retriever(search_type="mmr", search_kwargs={"k": 5})
    docs = retriever.invoke(query)
    context_text = "\n\n".join([f"Fuente: {d.metadata['source_law']}\nContenido: {d.page_content}" for d in docs])
    return context_text
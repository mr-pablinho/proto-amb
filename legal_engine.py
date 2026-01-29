import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
import config

def get_legal_vector_store():
    """
    Inicializa o carga el Vector Store con las leyes.
    """
    embeddings = GoogleGenerativeAIEmbeddings(
        model=config.EMBEDDING_MODEL, 
        google_api_key=config.GOOGLE_API_KEY
    )

    # Si ya existe la base de datos persistente, la cargamos
    if os.path.exists(config.VECTOR_DB_PATH) and os.listdir(config.VECTOR_DB_PATH):
        print("--- Cargando Base Legal existente ---")
        return Chroma(persist_directory=config.VECTOR_DB_PATH, embedding_function=embeddings)
    
    print("--- Indexando Base Legal (Esto puede tardar unos minutos) ---")
    docs = []
    
    # Iterar sobre los archivos en la carpeta leyes
    if not os.path.exists(config.LEGAL_DOCS_PATH):
        os.makedirs(config.LEGAL_DOCS_PATH)
        raise FileNotFoundError(f"Por favor coloca los PDFs de leyes en la carpeta '{config.LEGAL_DOCS_PATH}'")

    for filename in os.listdir(config.LEGAL_DOCS_PATH):
        if filename.endswith(".pdf"):
            file_path = os.path.join(config.LEGAL_DOCS_PATH, filename)
            loader = PyPDFLoader(file_path)
            loaded_docs = loader.load()
            # Añadir metadatos del nombre del archivo para citar la fuente
            for doc in loaded_docs:
                doc.metadata["source_law"] = filename
            docs.extend(loaded_docs)

    # Chunking optimizado para textos legales (mantener contexto de artículos)
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=2000,
        chunk_overlap=200,
        separators=["\nArt.", "\nTITULO", "\nCAPITULO", "\n\n", " "]
    )
    splits = text_splitter.split_documents(docs)

    # Crear Vector Store
    vectorstore = Chroma.from_documents(
        documents=splits, 
        embedding=embeddings, 
        persist_directory=config.VECTOR_DB_PATH
    )
    return vectorstore

def get_legal_basis(query, vectorstore):
    """
    Busca los artículos legales relevantes para un requisito específico.
    """
    retriever = vectorstore.as_retriever(search_type="mmr", search_kwargs={"k": 5})
    docs = retriever.invoke(query)
    
    context_text = "\n\n".join([f"Fuente: {d.metadata['source_law']}\nContenido: {d.page_content}" for d in docs])
    return context_text
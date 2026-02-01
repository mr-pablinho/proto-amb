import chromadb
import os
from chromadb.utils import embedding_functions
from config import DB_DIR

class LegalRAG:
    def __init__(self):
        # Persistent Client
        self.client = chromadb.PersistentClient(path=DB_DIR)
        
        # Embedding Function (Local)
        self.ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        
        self.collection = self.client.get_or_create_collection(
            name="legal_framework",
            embedding_function=self.ef
        )

    def ingest_text(self, text: str, source_name: str):
        """Splits text into chunks and stores in ChromaDB."""
        # Simple chunking for PoC
        chunks = [text[i:i+1000] for i in range(0, len(text), 1000)]
        ids = [f"{source_name}_{i}" for i in range(len(chunks))]
        metadatas = [{"source": source_name, "chunk_id": i} for i in range(len(chunks))]
        
        self.collection.upsert(
            documents=chunks,
            ids=ids,
            metadatas=metadatas
        )

    def retrieve_context(self, query: str, n_results: int = 2) -> str:
        """Retrieves relevant legal context."""
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results
        )
        if results['documents']:
            return "\n\n".join(results['documents'][0])
        return "No legal context found."
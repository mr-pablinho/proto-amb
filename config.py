import os
from dotenv import load_dotenv

# Cargar variables de entorno si existen
load_dotenv()

# Configuración centralizada
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
MODEL_NAME = "gemini-1.5-pro" # Usamos Pro por la ventana de contexto amplia
EMBEDDING_MODEL = "models/embedding-001"

# Rutas
LEGAL_DOCS_PATH = "leyes"
VECTOR_DB_PATH = "chroma_db"
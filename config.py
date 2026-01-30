import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

MODEL_NAME = "gemini-2.5-pro" 
FAST_MODEL_NAME = "gemini-2.5-flash"

EMBEDDING_MODEL = "all-MiniLM-L6-v2"  

LEGAL_DOCS_PATH = "leyes"
VECTOR_DB_PATH = "chroma_db"

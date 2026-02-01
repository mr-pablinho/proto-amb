import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY not found in .env")

# Model Definitions (Feb 2026 Standards)
MODEL_CATALOGER = "gemini-2.5-flash"
MODEL_ROUTER = "gemini-2.5-flash"
MODEL_AUDITOR = "gemini-2.5-pro"

# Paths
DATA_DIR = "./data"
PDF_DIR = os.path.join(DATA_DIR, "proyecto_eia")
LEGAL_DIR = os.path.join(DATA_DIR, "leyes")
DB_DIR = os.path.join(DATA_DIR, "db")
INDEX_FILE = os.path.join(DATA_DIR, "project_index.json")
CHECKLIST_FILE = os.path.join(DATA_DIR, "audit_checklist.json")

FORCE_REINDEX = False  
RATE_LIMIT_CALLS = 20
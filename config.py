import os
from dotenv import load_dotenv  # <--- NEW IMPORT

# Load environment variables from .env file
load_dotenv()  # <--- NEW CALL

# API Configuration
# Now os.getenv will successfully find the key inside .env
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY not found. Please check your .env file.")

# Model Definitions
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

# Operational Flags
FORCE_REINDEX = True  
RATE_LIMIT_CALLS = 20
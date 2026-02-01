import os

# API Configuration
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "YOUR_API_KEY_HERE")

# Model Definitions
MODEL_CATALOGER = "gemini-1.5-flash"
MODEL_ROUTER = "gemini-1.5-flash"
MODEL_AUDITOR = "gemini-1.5-pro"

# Paths
DATA_DIR = "./data"
PDF_DIR = os.path.join(DATA_DIR, "proyecto_eia")
LEGAL_DIR = os.path.join(DATA_DIR, "leyes")
DB_DIR = os.path.join(DATA_DIR, "db")
INDEX_FILE = os.path.join(DATA_DIR, "project_index.json")
CHECKLIST_FILE = os.path.join(DATA_DIR, "audit_checklist.json")

# Operational Flags
FORCE_REINDEX = False  # Set to True to ignore cache and re-scan PDFs
RATE_LIMIT_CALLS = 20  # Requests per minute
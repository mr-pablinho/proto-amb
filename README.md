# MAATE AI: Auditor Ambiental (PoC)

**MAATE AI** is a high-precision, terminal-based AI agent designed to automate the compliance review of complex Environmental Impact Studies (EIA) for the Ministry of Environment in Ecuador (MAATE).

It uses a "Content-First" architecture to ignore generic filenames and index the actual content of PDF files, allowing it to find specific tables, maps, and plans buried in large documentation sets.

## 🚀 Key Features

* **Deep Content Indexing**: The **Cataloger Agent** scans every PDF to detect specific Environmental Plans, Baseline Components, and Table Captions, ignoring generic filenames like `Chapter_1.pdf`.
* **Semantic & Logical Routing**: The **Router Agent** (Gemini 2.5 Flash) intelligently selects the exact files needed for a requirement, understanding dependencies (e.g., "Noise Plan" requires both the methodology text and the monitoring logs in the Annexes).
* **Strict Auditing**: The **Auditor Agent** (Gemini 2.5 Pro) acts as a Senior Environmental Auditor, verifying technical evidence against the specific legal articles from the TULSMA/COA.
* **Multi-File Legal Context**: Automatically ingests and references multiple legal frameworks (COA, RCOA, TULSMA).
* **Financial & Performance Logging**: Tracks every token used, estimating the exact cost per audit requirement in a detailed CSV log.

## 🛠️ Technical Stack

* **LLMs**: Google Gemini 2.5 Flash (Routing/Cataloging) & Gemini 2.5 Pro (Auditing).
* **Vector Database**: ChromaDB (Local persistence for legal RAG).
* **Orchestration**: Python 3.10+.
* **UI**: `rich` library for terminal dashboards and status spinners.
* **Data Validation**: `pydantic` for structured JSON outputs.

## 📂 Project Structure

```text
.
├── data/
│   ├── proyecto_eia/        # Place your EIA PDF files here
│   ├── leyes/               # Place Legal PDFs (COA, TULSMA) here
│   ├── db/                  # ChromaDB Vector Store (Auto-generated)
│   ├── cheklist/            # Place your Checklist CSV file here
│   ├── project_index.json   # Cached Deep Content Index (Auto-generated)
│   └── audit_checklist.json # The requirements to audit (Auto-generated from CSV)
├── logs/                   # Detailed CSV logs and Metadata reports
├── agents.py               # The 3 AI Agents (Cataloger, Router, Auditor)
├── config.py               # API Keys, Temperatures, and Paths
├── logger.py               # Financial and Operational logging logic
├── main_cli.py             # Main entry point
├── rag_engine.py           # Vector DB logic
└── requirements.txt        # Dependencies

```

## ⚙️ Setup & Installation

1. **Clone the repository**:
```bash
git clone [https://github.com/your-username/maate-ai.git](https://github.com/your-username/maate-ai.git)
cd maate-ai

```

2. **Install dependencies**:
```bash
pip install -r requirements.txt

```

3. **Configure Environment**:
Create a `.env` file in the root directory:
```env
GOOGLE_API_KEY="your_google_gemini_api_key"

```

4. **Prepare Data**:
* Put your EIA PDF files in `data/proyecto_eia/`.
* Put your Legal PDF files in `data/leyes/`.
* Ensure your Checklist CSV is in the root folder (named `Checklist Borrador...csv`).

## ▶️ Usage

Run the main orchestrator:

```bash
python main_cli.py
```

1. The system will ask for the folder containing your EIA PDFs.
2. It will index the Legal Framework (if not already cached).
3. It will scan and catalog the EIA files (if not already cached).
4. It will iterate through the checklist, displaying real-time compliance results.

## 📊 Outputs

Check the `./logs/` folder after a run:

* `audit_report_USER_timestamp.csv`: A clean, high-level report for the end-user.
* `audit_detailed_timestamp.csv`: Technical log including token usage, costs, and reasoning.
* `audit_catalog_timestamp.csv`: Cost log for the initial PDF indexing phase.
* `run_metadata_timestamp.json`: Summary of the run configuration and total costs.

## ⚠️ Notes

* **Cost**: This tool uses paid API models. Estimated cost is ~$0.15 - $0.50 per full audit depending on document size.
* **Temperature**: All models are set to `0.0` for maximum determinism and strictness.

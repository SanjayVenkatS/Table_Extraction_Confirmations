# ADI PDF Processing Pipeline

Focused, cloud-powered pipeline for turning raw regulatory or compliance PDF documents into structured artifacts using Azure Document Intelligence: Markdown content, extracted tables, and comprehensive metadata. The current objective is simple and clear: batch-process PDFs with Azure Document Intelligence API and emit clean, reproducible outputs for downstream analysis.

> Scope: This repository is intentionally trimmed to PDF → structured artifacts using Azure Document Intelligence.

## What This Pipeline Does (ADI-Centric)

1. Bulk ingest a directory of `.pdf` files.
2. Drive Azure Document Intelligence to parse layout, text, and tables.
3. Produce a unified `document.md` preserving document structure.
4. Extract every detected table as independent markdown files.
5. Generate comprehensive `metadata.json` with processing details.
6. Log every step with structured logging for traceability.

If all you need is "Give Azure DI PDFs; get structured outputs," this is it.

## Layout Overview

```
run_pipeline.py            # CLI entry point (ADI batch processor)
config/config.yaml         # Central configuration (Azure + paths + logging)
core/                      # Config loader, logger, exceptions, models
processing/pdfextraction.py # Azure Document Intelligence extraction orchestration
inputs/                    # Source PDF directory
outputs/                   # Produced artifacts (one subfolder per PDF)
```

### Output Folder Structure (Per PDF)
```
outputs/<DOCUMENT_NAME>/
  document.md              # Full markdown representation
  metadata.json            # Processing metadata and document details
  tables/                  # Individual table markdown (table_1.md, ...)
```

Note: Each output subfolder is named after the original PDF file (filename without extension, sanitized for filesystem safety).

## Prerequisites

- Python 3.8+ (recommended 3.10+)
- Windows PowerShell (examples use PowerShell syntax)
- Azure Document Intelligence resource with API endpoint and key
- Optional: virtual environment

## Quick Start (Setup For Codebase)

```powershell
# From repository root
python -m venv .venv
./.venv/Scripts/Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt

# Set Azure credentials 
Create a .env file in the project directory with the below entries.

```
# Azure Document Intelligence Configuration
AZURE_ENDPOINT = https://your-resource.cognitiveservices.azure.com/
AZURE_API_KEY = your-api-key
```

# Run ADI batch processing
python run_pipeline.py --input-dir data/inputs --output-dir data/outputs
```

All `.pdf` files under `--input-dir` are processed; each gets its own output subfolder.

## Environment Setup (Detailed)
1. Clone repo / open root in PowerShell.
2. Create & activate venv:
```powershell
python -m venv .venv
./.venv/Scripts/Activate.ps1
```
3. Upgrade pip (optional):
```powershell
python -m pip install --upgrade pip
```
4. Install dependencies:
```powershell
pip install -r requirements.txt
```
5. Configure Azure credentials (see Azure Setup section below)
6. Validate environment (optional):
```powershell
python --version
pip --version
```
Deactivate later with:
```powershell
deactivate
```

## Azure Document Intelligence Setup

### Prerequisites
1. Azure subscription
2. Azure Document Intelligence resource created

Update `config/config.yaml`:
```yaml
azure:
  endpoint: "https://your-resource.cognitiveservices.azure.com/"
  api_key: "your-api-key"
  api_model: "prebuilt-layout"
  mode: "markdown"
```

Or set environment variables:
```powershell
$env:AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT = "https://your-resource.cognitiveservices.azure.com/"
$env:AZURE_DOCUMENT_INTELLIGENCE_API_KEY = "your-api-key"
```

## Configuration (`config/config.yaml`)

All runtime behavior is driven by YAML. Keys relevant to ADI PDF processing:

```yaml
# Azure Document Intelligence Configuration
azure:
  api_model: "prebuilt-layout"
  mode: "markdown"

# File Paths Configuration
paths:
  input_folder: "inputs"
  output_folder: "outputs"

# Processing Settings
processing:
  combined_content_filename: "document.md"
  metadata_filename: "metadata.json"
  tables_folder_name: "tables"
  save_individual_tables: true
  table_filename_prefix: "table_"
  page_number_format: "<!-- page_number: page_{} -->"
  
# File encoding
encoding: "utf-8"

# Logging
logging:
  show_processing_messages: true
  show_table_save_confirmations: true
  show_error_details: true
```

### How It Drives Azure Document Intelligence
- `run_pipeline.py` loads logging configuration and applies environment variables early.
- `pdfextraction.py` reads Azure configuration to initialize the API client.
- `--output-dir` defaults to `paths.output_folder` but can be overridden.

### Tuning Quick Reference
- Enable table extraction: `save_individual_tables: true`.
- Custom table naming: modify `table_filename_prefix`.
- Verbose logging: set all `logging` options to `true`.
- Different API model: change `azure.api_model` (e.g., "prebuilt-document").

### Missing Keys Safety
Absent values fall back to internal defaults. Missing sections are ignored without crashing the core PDF processing flow.

## Running the ADI Pipeline

```powershell
python run_pipeline.py --input-dir <PATH_TO_PDF_DIRECTORY> --output-dir <OUTPUT_BASE_DIR>
```

Required:
- `--input-dir`: Directory containing PDF files to process.

Optional:
- `--output-dir`: Base output directory (defaults to `outputs` from config).

Example:
```powershell
python run_pipeline.py --input-dir inputs --output-dir outputs
```

Result:

```
Processed N PDF files into: outputs
```

## Processing Workflow

The following diagram illustrates the complete PDF processing pipeline:

📊 **View the complete system flowchart:**
- [Flowchart Image (PNG)](system-design/Flowchart_ADI_Extraction.png) - Static image version


## Output Details

| Artifact | Description |
|----------|-------------|
| `document.md` | Full Azure DI markdown rendition of the PDF with converted tables. |
| `tables/table_X.md` | Individual extracted tables in markdown format. |
| `metadata.json` | Processing metadata including page count, source info, and extraction details. |

## Logging & Resilience
Each PDF is processed independently. Failures are logged (with stack traces) without halting other files. The pipeline continues processing remaining PDFs even if some fail.

## Troubleshooting Quick Table

| Issue | Cause | Fix |
|-------|-------|-----|
| PDF directory not found | Wrong path | Verify with `Get-ChildItem`. |
| Azure API authentication error | Missing/invalid credentials | Check Azure endpoint and API key. |
| Empty output | Unsupported PDF features / API error | Inspect logs; verify PDF opens normally. |
| Permission denied | Restricted folder | Move to user path or run elevated. |

Diagnostics:
```powershell
Get-ChildItem -Path inputs -Filter *.pdf
Get-ChildItem -Path outputs
```

## Suggested Tests (Not Included Yet)
1. Unit test directory processing with mock PDFs.
2. Assert creation of expected artifact subfolders.
3. Validate `metadata.json` schema (fields: `filename`, `page_number`, `source`).
4. Integration test with Azure DI API (requires valid credentials).

## FAQ

**Do I need Azure credentials?** Yes. Azure Document Intelligence requires an active Azure subscription and API key.

**Can I use absolute paths?** Yes. Example: `python run_pipeline.py --input-dir C:\Data\PDFs`.

**How to clean outputs?** Remove the folder: `Remove-Item -Recurse -Force outputs`.

## License
Add license information here (MIT/Apache 2.0/etc.). If omitted, clarify usage restrictions.

## Contributing
1. Fork & create a feature branch.
2. Keep changes atomic and documented.
3. Add tests for any new behavior.
4. Open PR referencing related issues / roadmap item.

---
Questions or improvement ideas? Open an issue. Happy ADI processing!
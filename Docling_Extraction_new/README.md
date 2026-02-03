# Docling PDF Processing Pipeline

Focused, high‑performance pipeline for turning raw PDF documents into structured Docling artifacts: Markdown, tables (markdown + images), extracted page/picture images, and coordinate metadata. The current objective is simple and clear: batch‑process PDFs with Docling and emit clean, reproducible outputs for downstream analysis.

## ✅ What This Pipeline Does (Docling‑Centric)

1. Bulk ingest a directory of `.pdf` files.
2. Drive Docling to parse layout, tables, and images.
3. Produce a unified `document.md` preserving hierarchical structure.
4. Render every detected table as independent markdown + optional raster snapshot.
5. Export page/picture images with configurable scaling.
6. Emit `coordinates.json` for positional metadata (blocks, tables, images).
7. Log every step with rotating files for traceability.

If all you need is “Give Docling PDFs; get structured outputs,” this is it.

## 📂 Layout Overview

```
run_pipeline.py            # CLI entry point (Docling batch processor)
config/config.yaml         # Central configuration (Docling + system + logging)
core/                      # Config loader, logger, exceptions, simple models
processing/pdf_processor.py # Docling extraction orchestration
input_data_pdfs/           # Example source PDF directory
output_files*/             # Produced artifacts (one subfolder per PDF)
logs/                      # Rotating log files
```

### Output Folder Structure (Per PDF)
```
output_files/<DOCUMENT_NAME>/
  document.md              # Full markdown representation
  coordinates.json         # Positional metadata
  images/                  # Extracted images (page/picture depending on config)
  table_images/            # Rasterized table snapshots
  tables/                  # Individual table markdown (table_1.md, ...)
```

Note: Each output subfolder is named after the original PDF file (filename without extension, sanitized for filesystem safety).

## 🔧 Prerequisites

- Python 3.9+ (recommended 3.10+)
- Windows PowerShell (examples use PowerShell syntax)
- Optional: virtual environment

## Quick Start (Setup For Codebase)

```powershell
# From repository root
python -m venv .venv
./.venv/Scripts/Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt

# Run Docling batch processing
python run_pipeline.py --input-dir data/inputs --output-dir data/outputs
```

All `.pdf` files under `--input-dir` are processed; each gets its own output subfolder.

## 🏗️ Environment Setup (Detailed)
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
5. Validate environment (optional):
```powershell
python --version
pip --version
```
Deactivate later with:
```powershell
deactivate
```

## ⚙️ Configuration (`config/config.yaml`)

All runtime behavior is driven by YAML. Keys relevant to Docling PDF processing:

```yaml
document_processing:
  pdf_extraction:
    images_scale: 1.0            # Image DPI scaling (raise for higher-quality raster outputs)
    table_mode: ACCURATE         # Table detection mode (FAST|ACCURATE)
    use_progress_bar: true       # Enable tqdm during batch runs
    do_table_structure: true     # Emit structured table markdown files
    generate_page_images: true   # Render full page images
    generate_picture_images: true# Extract embedded/picture images

logging:
  level: INFO
  format: '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
  file_rotation:
    max_bytes: 10485760
    backup_count: 5

environment:
  HF_HUB_DISABLE_SYMLINKS: '1'
  CUDA_VISIBLE_DEVICES: ''        # Leave blank for CPU-only
  PYTORCH_ENABLE_MPS_FALLBACK: '1'

data_paths:
  output_dir: outputs             # Base directory for per-PDF folders
```

### How It Drives Docling
- `run_pipeline.py` loads `logging` + applies `environment` variables early.
- `pdf_processor.py` reads `pdf_extraction` to set Docling flags (tables/images, scaling, aspect filter).
- `--output-dir` defaults to `data_paths.output_dir` but can be overridden.

### Tuning Quick Reference
- Higher quality images: raise `images_scale` (e.g. 2.0). Trade-off: disk & time.
- Faster table detection: `table_mode: FAST` (less precise layout fidelity).
- Enable GPU: set `use_gpu: true`, remove `force_cpu`, ensure CUDA drivers + compatible wheels.
- Disable progress bar (e.g., CI logs): set `use_progress_bar: false`.

### Environment Variable Note
`HF_HUB_DISABLE_SYMLINKS: '1'` avoids Windows symlink issues when downloading models (a common Docling/Hugging Face friction point). Safe to keep even on Linux; remove if you prefer native symlinks.

### Missing Keys Safety
Absent values fall back to internal defaults (e.g., `table_mode -> ACCURATE`, `images_scale -> 1.0`). Missing sections are ignored without crashing core PDF flow.

## Running the Docling Pipeline

```powershell
python run_pipeline.py --input-dir <PATH_TO_PDF_DIRECTORY> --output-dir <OUTPUT_BASE_DIR>
```

Required:
- `--input-dir`: Directory containing PDFs.

Optional:
- `--output-dir`: Base output (defaults to `outputs` / YAML `data_paths.output_dir`).

Example:
```powershell
python run_pipeline.py --input-dir input_data_pdfs --output-dir output_files
```

Result:

```
Processed N PDF files into: output_files
```

## 📊 Processing Workflow

The following diagram illustrates the complete PDF processing pipeline (click to view full image):

![PDF Processing Flowchart](Flowchart_Docling_Extraction.png)

## 🗂️ Output Details

| Artifact | Description |
|----------|-------------|
| `document.md` | Full Docling markdown rendition of the PDF. |
| `tables/table_X.md` | Individual extracted tables in markdown. |
| `table_images/` | Image snapshots of tables for QA. |
| `images/` | Page or embedded picture exports (config-driven). |
| `coordinates.json` | BBoxes + page + element type metadata. |
| `logs/` | Rotating log files (INFO+). |
| Console Progress | `tqdm` progress bar showing per-file advancement when `use_progress_bar: true`. |

## 🌟 Repository Feature Highlights
- Multi-PDF batch processing: any number of PDFs in the input directory, each isolated into its own output folder named after the source file.
- Robust error handling: a failure in one PDF does not stop others; details captured in rotating log files.
- Unified `document.md`: aggregated, ordered extraction (text, tables, images) for direct downstream consumption (RAG, indexing, diffing).
- Embedded page markers: `page_number` tags (emitted at the bottom of each page region) enable precise citation, provenance, and page-scoped chunking.
- Dual image capture: the `images/` folder can include both full rendered page images (when `generate_page_images: true`) and individual embedded/picture images; no restriction is enforced on aspect ratio—images retain original layout proportions.
- Image linkage: `document.md` carries comment tags pointing to extracted raster assets in `images/` for multimodal tasks.
- Table redundancy for flexibility: tables appear (1) inline in `document.md`, (2) individually in `tables/table_X.md`, and (3) visually in `table_images/` for QA or OCR fallback.
- Spatial metadata: `coordinates.json` gives bounding boxes, page references, and element types for layout-aware enrichment or UI overlays.
- Structured raw representation: `document.json` (when present) contains the direct structured Docling model output (pages, blocks, tables, images, coordinates) prior to markdown rendering—useful for programmatic transformations, alternative serializers, or custom post-processing.
- Resilience & edge cases: for non-parsable / heavily corrupted PDFs Docling may yield garbled placeholder characters instead of real text—validate such outputs manually.
- Heading/page accuracy: headings and page number markers are accurate in almost all cases; rarely a heading/text may be appended to the previous page block if boundary hints are ambiguous or if the text in the pdf is in different font style.



## 🔖 Markdown Tag Conventions (Embedded HTML Comments)

Docling inserts lightweight HTML comment tags into `document.md` to preserve linkage between rendered markdown elements and their original extracted artifacts (tables, images, pagination). These tags never display in normal markdown rendering but are crucial for downstream enrichment (e.g., RAG indexing, delta comparison, re‑hydrating table/image contexts, page‑scoped processing).

Observed tag patterns (example values taken from `outputs/C'zec Republic PRO Details/document.md`):

| Tag Pattern | Meaning | Downstream Use Ideas |
|-------------|---------|----------------------|
| `<!-- page_number: page_5 -->` | Logical page boundary marker (1‑indexed as named by Docling). | Page segmentation; align with `coordinates.json` entries; chunking for embeddings; page-level QA. |
| `<!-- table : C:\\...\\tables\\table_7.md -->` | Indicates the following markdown table originated from an extracted table; path points to isolated per‑table markdown file. | Rapid table retrieval; join structured table file with surrounding narrative; provenance tracking. |
| `<!-- table_image : C:\\...\\table_images\\table_7.png -->` | Raster snapshot of the same table (visual fidelity / QA). | Human review UI; fallback OCR; vision‑language augmentation. |
| `<!-- image : C:\\...\\images\\picture_3.png -->` | Embedded/picture image extracted from the PDF (could be page element, logo, chart, etc.). | Image captioning; multimodal indexing; alt‑text generation; duplicate detection. |

### Parsing Tips
- Tags are always on their own line and start with `<!--` then a single space‑delimited key/value pattern.
- File paths are absolute (Windows) in current outputs; normalize to relative paths if storing externally.
- Associate a table markdown block with its preceding `table` / `table_image` comments until the next blank line or tag.
- Page tags (`page_number`) appear at the bottom of the page content and can be treated as hard boundaries; everything until the next page tag belongs to that page.
- Image tags may correspond to either a full-page render or an embedded/picture image; no enforced aspect ratio constraints.

### Suggested Extraction Regexes (Python Examples)
```python
PAGE_TAG_RE = re.compile(r"<!--\s*page_number:\s*(page_\d+)\s*-->")
TABLE_TAG_RE = re.compile(r"<!--\s*table\s*:\s*(.+?)\s*-->")
TABLE_IMG_TAG_RE = re.compile(r"<!--\s*table_image\s*:\s*(.+?)\s*-->")
IMAGE_TAG_RE = re.compile(r"<!--\s*image\s*:\s*(.+?)\s*-->")
```

## 🧩 Logging & Resilience
Each PDF is processed independently. Failures are logged (with stack traces) without halting other files wherever possible. Use log tailing to inspect anomalies:
```powershell
Get-Content -Path logs\*.log -Tail 50
```

## 🛠️ Troubleshooting Quick Table

| Issue | Cause | Fix |
|-------|-------|-----|
| PDF directory not found | Wrong path | Verify with `Get-ChildItem`. |
| Empty output | Unsupported PDF features / error | Inspect logs; validate file opens normally. |
| Missing tables | Detection mode too coarse | Use `ACCURATE` mode. |
| Slow run | Large PDFs / CPU only | Try GPU (`use_gpu: true`). |
| Permission denied | Restricted folder | Move to user path or run elevated. |

Diagnostics:
```powershell
Get-ChildItem -Path input_data_pdfs -Filter *.pdf
Get-ChildItem -Path logs
```

## ❓ FAQ
**Do I need any API keys?** No. Pure Docling PDF processing is local.

**Absolute paths okay for `--input-dir`?** Yes. Example: `python run_pipeline.py --input-dir C:\Data\PDFs`.

**How to clean outputs?** Remove the folder: `Remove-Item -Recurse -Force output_files` (or whichever base you used).

**Can I turn off the progress bar?** Yes—set `use_progress_bar: false` under `document_processing.pdf_extraction` in `config.yaml`.

**Why does the progress bar not show?** Either `tqdm` failed to import or `use_progress_bar` is disabled. Check that `tqdm` is in `requirements.txt` and reinstall dependencies.

---
Happy Docling processing!


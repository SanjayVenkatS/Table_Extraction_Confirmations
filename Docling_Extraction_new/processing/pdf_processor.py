"""
Generic PDF Processing Module
=============================

Provides a generalized, configuration-driven `PdfExtractor` built on docling for
structure-aware extraction of text, tables, images, and per-word coordinates.
Originally adapted from Sustainability-Mapper's implementation; now refactored
for reusable pipelines featuring:
    - Markdown export with injected page break markers.
    - Table and image reference annotation via HTML comments.
    - Separate persistence of page, inline, and table snapshot images.
    - Coordinate generation combining docling and PyMuPDF fallbacks.

This module is intended for generic document ingestion workflows rather than a
project-specific integration.
"""

import shutil
import re
import time
import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import json
from PIL import Image
from typing import Iterable
from pathlib import Path
import ssl
import urllib3

# Disable SSL warnings and verification BEFORE any other imports
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
ssl._create_default_https_context = ssl._create_unverified_context
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''
os.environ['SSL_CERT_FILE'] = ''

# Apply environment settings via config (no hard-coded env vars)
from core.config_loader import config as global_config
_env_cfg = getattr(global_config, '_config', {}).get('main', {}).get('environment', {})  # type: ignore
for _k, _v in _env_cfg.items():
    os.environ[str(_k)] = str(_v)

# Monkey-patch requests to disable SSL verification globally
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.ssl_ import create_urllib3_context

class SSLContextAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        context = create_urllib3_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        kwargs['ssl_context'] = context
        return super().init_poolmanager(*args, **kwargs)

# Patch the default session
_original_session = requests.Session
def _patched_session():
    session = _original_session()
    session.verify = False
    session.mount('https://', SSLContextAdapter())
    session.mount('http://', SSLContextAdapter())
    return session
requests.Session = _patched_session
requests.sessions.Session = _patched_session

from docling.datamodel.base_models import InputFormat
from docling_core.types.doc import ImageRefMode, TableItem
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions, TableFormerMode
)
from docling.document_converter import DocumentConverter, PdfFormatOption

from core.logger import StructuredLogger, Logger
from core.models import DocumentInfo

def _cfg(path: List[str], default=None):
    """Safely traverse config dict by path list returning default if any segment missing."""
    try:
        node = global_config._config['main']  # type: ignore
        for key in path:
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node
    except Exception:
        return default

@dataclass
class PDFExtractionResult:
    """Result of PDF extraction using Sustainability-Mapper approach."""
    pdf_path: Path
    output_dir: Path
    markdown_content: str
    extraction_method: str
    processing_time: float
    page_count: int
    success: bool
    document_info: DocumentInfo
    error_message: Optional[str] = None

class PdfExtractor:
    """
    Sustainability-Mapper's proven PdfExtractor class for RegScan-V2.
    
    This class handles the extraction of text, tables, and images from PDF
    documents and saves them to specified output directories.
    """

    def __init__(
        self,
        pdf_path: Path,
        output_dir: Path,
        images_scale: Optional[float] = None,
        table_mode: Optional[str] = None
    ):
        """
        Initialize the PDF Extractor using Sustainability-Mapper's approach.

        Args:
            pdf_path (Path): Path to the input PDF file.
            output_dir (Path): Directory where extracted content will be saved.
            images_scale (float, optional): Scale factor for extracted images.
                Defaults to 1.0 (72 DPI standard).
            table_mode (str, optional): Mode for table structure recognition.
                Defaults to "ACCURATE" (more accurate but slower).
        """
        # Use StructuredLogger for contextual logging if available; fallback to basic Logger
        try:
            self.logger = StructuredLogger("PdfExtractor")
        except Exception:
            self.logger = Logger.get_logger("PdfExtractor")
        self.logger.info(f"Initializing PDF Extractor for: {pdf_path}")
        
        # Input and output paths
        self.pdf_path = Path(pdf_path)
        self.output_dir = Path(output_dir)
        self.images_dir = self.output_dir / "images"
        self.tables_dir = self.output_dir / "tables"
        self.table_images_dir = self.output_dir / "table_images"
        self.markdown_file = self.output_dir / "document.md"
        
        # Configuration options resolved from config (pdf_extraction section)
        pdf_cfg = _cfg(['document_processing', 'pdf_extraction'], {}) or {}
        table_mode_map = {"ACCURATE": TableFormerMode.ACCURATE, "FAST": TableFormerMode.FAST}
        resolved_table_mode = table_mode if table_mode is not None else pdf_cfg.get('table_mode', 'ACCURATE')
        self.table_mode = table_mode_map.get(str(resolved_table_mode).upper(), TableFormerMode.ACCURATE)
        self.images_scale = images_scale if images_scale is not None else pdf_cfg.get('images_scale', 1.0)
        self.logger.debug(
            f"Resolved config -> table_mode={resolved_table_mode}, images_scale={self.images_scale}"
        )

        # Create necessary directories
        self._create_output_directories()

        # Configure pipeline options
        self.pipeline_options = self._configure_pipeline_options()

        # Initialize document converter
        self.converter = self._initialize_converter()
        self.logger.info("PDF Extractor initialized successfully")
        
    def _create_output_directories(self) -> None:
        """Create the necessary output directories if they don't exist."""
        self.logger.debug("Creating output directories")
        for folder in (self.output_dir, self.images_dir, self.tables_dir,
                      self.table_images_dir):
            folder.mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"Created directory: {folder}")
            
    def _configure_pipeline_options(self) -> PdfPipelineOptions:
        """
        Configure the PDF pipeline options.
        
        Returns:
            PdfPipelineOptions: Configured pipeline options.
        """
        self.logger.debug("Configuring PDF pipeline options")
        pdf_cfg = global_config._config['main'].get('document_processing', {}).get('pdf_extraction', {})  # type: ignore
        options = PdfPipelineOptions(
            do_table_structure=pdf_cfg.get('do_table_structure', True),
            generate_page_images=pdf_cfg.get('generate_page_images', True),
            generate_picture_images=pdf_cfg.get('generate_picture_images', True)
        )
        
        # Configure table recognition mode
        options.table_structure_options.mode = self.table_mode
        
        # Configure image scale (1.0 = 72 DPI standard)
        options.images_scale = self.images_scale
        
        return options
    
    def _initialize_converter(self) -> DocumentConverter:
        """
        Initialize the document converter with the configured options.
        
        Returns:
            DocumentConverter: Initialized document converter.
        """
        self.logger.debug("Initializing document converter")
        return DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=self.pipeline_options)
            }
        )
            
    def extract(self) -> Path:
        """
        Execute the PDF extraction process.
        
        This method runs the conversion pipeline and saves the extracted
        content including markdown text, page images, inline pictures,
        and tables.
        
        Returns:
            Path: Path to the output directory containing the extracted
                content.
        """
        self.logger.info(f"Starting extraction of PDF: {self.pdf_path}")
        
        # Run the conversion pipeline
        self.logger.info("Running conversion pipeline")
        result = self.converter.convert(self.pdf_path)
        self.logger.info("Conversion pipeline completed")
        
        # Save JSON
        json_path = self.output_dir / "document.json"
        self.logger.debug(f"Saving document JSON to: {json_path}")
        result.document.save_as_json(json_path,
                                   image_mode=ImageRefMode.PLACEHOLDER)
        
        # Export markdown with plain placeholders
        self.logger.debug("Exporting document to markdown")
        # markdown_text = result.document.export_to_markdown()
        # Export markdown with a page-break placeholder so we can inject page markers later
        markdown_text = result.document.export_to_markdown(page_break_placeholder="<PAGE_BREAK>")
        
        # Debug: Check markdown content
        if not markdown_text or len(markdown_text.strip()) == 0:
            self.logger.error(f"CRITICAL: Markdown export returned empty content for {self.pdf_path}")
            self.logger.error(f"Document pages: {len(result.document.pages) if hasattr(result.document, 'pages') else 'unknown'}")
        else:
            self.logger.info(f"Markdown exported successfully: {len(markdown_text)} characters")
        
        # Save page and inline images (filtered by aspect ratio)
        self.logger.info("Saving page images")
        self._save_page_images(result)
        
        self.logger.info("Saving inline pictures")
        picture_mapping = self._save_inline_pictures(result)
        
        # Save tables and get mapping
        self.logger.info("Saving tables")
        table_mapping = self._save_tables(result)

        # (Optional) still compute page mapping for potential diagnostics (not used directly now)
        self.logger.info("Finding tables in markdown (for diagnostics)")
        table_page_mapping = self._find_tables_in_markdown(markdown_text)
        if table_page_mapping:
            self.logger.debug(f"Table -> pages diagnostic mapping: {table_page_mapping}")

        # Save actual table snapshot images using Docling's TableItem.get_image
        self.logger.info("Saving actual table images (Docling snapshots)")
        table_image_mapping = self._save_table_images(result)
        
        # Update the markdown text with proper image and table references
        self.logger.info("Updating markdown references")
        self.logger.info(f"Original markdown length before update: {len(markdown_text)}")
        
        updated_markdown = self._update_markdown_references(
            markdown_text, 
            picture_mapping, 
            table_mapping,
            table_image_mapping
        )
        
        self.logger.info(f"Updated markdown length after references: {len(updated_markdown)}")
        
        # Inject page break markers using Docling's document structure
        try:
            # updated_markdown = self._add_page_markers_from_docling(updated_markdown, result.document)
            # Inject page break markers using Docling's document structure
            updated_markdown = self._add_page_markers_from_docling(updated_markdown, result.document)

            self.logger.info("Page markers injected successfully using Docling structure")
        except Exception as e:
            self.logger.warning(f"Failed to inject page markers from Docling: {e}")
            # Fallback: keep the markdown without page markers
            self.logger.info("Continuing without page markers")
        
        # Save the updated markdown
        self.logger.info(f"Saving enhanced markdown to: {self.markdown_file}")
        with open(self.markdown_file, "w", encoding="utf-8") as f:
            f.write(updated_markdown)
        
        self.logger.info(f"Enhanced markdown with references saved to: {self.markdown_file}")
        self.logger.info(f"Extraction completed successfully. Output saved to: {self.output_dir}")
        
        return self.output_dir

    def _add_page_markers_from_docling(self, markdown: str, document, placeholder="<PAGE_BREAK>") -> str:
        pages = sorted(getattr(document, "pages", {}).values(), key=lambda p: getattr(p, "page_no", 0))
        if not pages or placeholder not in markdown:
            return markdown
        parts = markdown.split(placeholder)
        out = []
        for i, part in enumerate(parts):
            out.append(part)
            if i < min(len(parts) - 1, len(pages)):
                out.append(f"\n<!-- page_number: page_{pages[i].page_no} -->\n")
        
        # Add trailing marker for the last page number
        out.append(f"\n<!-- page_number: page_{pages[-1].page_no} -->\n")

        return "".join(out)

        
    def _save_page_images(self, result) -> None:
        """Save each page as an image."""
        page_count = len(result.document.pages)
        self.logger.debug(f"Saving {page_count} page images")
        
        for page in result.document.pages.values():
            page_no = page.page_no
            image_path = self.images_dir / f"page_{page_no}.png"
            self.logger.debug(f"Saving page {page_no} image to: {image_path}")
            page.image.pil_image.save(image_path, format="PNG")
            self.logger.debug(f"Page image saved: {image_path}")
            
    def _save_inline_pictures(self, result) -> Dict[int, str]:
        """Save inline pictures as separate image files (no aspect ratio filtering)."""
        picture_mapping: Dict[int, str] = {}

        if hasattr(result.document, "pictures"):
            picture_count = len(result.document.pictures)
            self.logger.debug(f"Processing {picture_count} inline pictures (no filtering)")

            for idx, pic in enumerate(result.document.pictures, start=1):
                image = pic.get_image(result.document)
                width, height = image.size
                self.logger.debug(f"Picture {idx}: size={width}x{height}")
                pic_filename = f"picture_{idx}.png"
                pic_path = self.images_dir / pic_filename
                image.save(pic_path, format="PNG")
                picture_mapping[idx] = pic_filename
                self.logger.debug(f"Inline picture saved to: {pic_path}")
        else:
            self.logger.debug("No inline pictures found in document")

        return picture_mapping
                
    def _save_tables(self, result) -> Dict[int, str]:
        """Save tables as markdown files."""
        table_mapping = {}
        
        # Each table implements export_to_markdown()
        tables = getattr(result.document, "tables", [])
        if tables:
            self.logger.debug(f"Processing {len(tables)} tables")
            
            for idx, table in enumerate(tables, start=1):
                table_filename = f"table_{idx}.md"
                table_path = self.tables_dir / table_filename
                table_md = table.export_to_markdown()
                
                with open(table_path, "w", encoding="utf-8") as f:
                    f.write(table_md)
                    
                table_mapping[idx] = table_filename
                self.logger.debug(f"Table {idx} saved to: {table_path}")
        else:
            self.logger.debug("No tables found in document")
        
        return table_mapping

    def _find_tables_in_markdown(self, markdown_text: str) -> Dict[int, List[int]]:
        """Find the page numbers where each table appears in the markdown."""
        # Initialize the mapping
        table_page_mapping = {}
        
        # Split the markdown into lines for analysis
        lines = markdown_text.splitlines()
        
        # Find tables in the markdown
        table_pattern = (r'(\|[^\n]+\|\n\|[-\s|]+\|\n(?:\|[^\n]+\|\n)+)')
        tables = re.findall(table_pattern, markdown_text)
        
        self.logger.debug(f"Found {len(tables)} table patterns in markdown")
        
        # Find the position of each table in the markdown
        table_positions = []
        for table in tables:
            start_pos = markdown_text.find(table)
            end_pos = start_pos + len(table)
            table_positions.append((start_pos, end_pos))
        
        # Convert markdown positions to line numbers
        table_line_positions = []
        for start_pos, end_pos in table_positions:
            start_line = markdown_text[:start_pos].count('\n')
            end_line = start_line + table.count('\n')
            table_line_positions.append((start_line, end_line))
        
        # Map each table to its page number(s)
        for table_idx, (start_line, end_line) in enumerate(
                table_line_positions, start=1):
            # Determine which page(s) this table appears on by counting
            # image comments
            table_pages = set()
            current_page = 1
            
            # First, determine the current page at the start of the table
            for i in range(start_line):
                if i < len(lines) and "<!-- image" in lines[i]:
                    current_page += 1
            
            # Record the starting page
            table_pages.add(current_page)
            
            # Check if the table spans multiple pages
            for i in range(start_line, end_line):
                if i < len(lines) and "<!-- image" in lines[i]:
                    current_page += 1
                    table_pages.add(current_page)
            
            # Store the page numbers for this table
            if table_pages:
                table_page_mapping[table_idx] = sorted(list(table_pages))
                self.logger.debug(f"Table {table_idx} appears on page(s): "
                                f"{sorted(list(table_pages))}")
            else:
                # Fallback: if we couldn't determine the page, use page 1
                table_page_mapping[table_idx] = [1]
                self.logger.debug(f"Could not determine page(s) for table "
                                f"{table_idx}, using default page 1")
        
        return table_page_mapping

    def _save_table_images(self, result) -> Dict[int, List[str]]:
        """Extract and save actual table images using Docling's TableItem.get_image.

        Returns:
            Dict[int, List[str]]: Mapping of table index (1-based, in document order)
            to list of saved image filenames (currently one per table, but list kept
            for forward compatibility if multi-image tables appear).
        """
        table_image_mapping: Dict[int, List[str]] = {}
        # Strategy 1: Enumerate TableItem via iterate_items()
        table_items: List[Any] = []
        try:
            for element in result.document.iterate_items():  # type: ignore
                if isinstance(element, TableItem):
                    table_items.append(element)
        except Exception as e:
            self.logger.debug(f"iterate_items() failed or unavailable: {e}")

        self.logger.debug(f"Strategy 1 located {len(table_items)} TableItem objects")

        # Strategy 2: Fallback to result.document.tables list if present
        if not table_items:
            try:
                raw_tables = getattr(result.document, 'tables', [])
                if raw_tables:
                    self.logger.debug(f"Strategy 2 using document.tables list (count={len(raw_tables)})")
                    table_items = list(raw_tables)
            except Exception as e:
                self.logger.debug(f"Accessing document.tables failed: {e}")

        # Helper: try to obtain an image from a table-like object.
        def _table_to_image(tbl: Any) -> Optional[Image.Image]:  # type: ignore
            # 1. Direct get_image if available
            if hasattr(tbl, 'get_image'):
                try:
                    img = tbl.get_image(result.document)  # type: ignore
                    if img is not None:
                        return img
                except Exception as e:
                    self.logger.debug(f"get_image failed for table: {e}")
            # 2. Attempt crop from page image using bbox/box attributes
            try:
                page_no = getattr(tbl, 'page_no', None) or getattr(tbl, 'page', None)
                bbox = getattr(tbl, 'box', None) or getattr(tbl, 'bbox', None)
                if page_no and bbox and page_no in getattr(result.document, 'pages', {}):
                    page_obj = result.document.pages[page_no]
                    page_img = page_obj.image.pil_image
                    # Support both object-like and tuple-like bbox
                    try:
                        x0 = getattr(bbox, 'x0', None) if hasattr(bbox, 'x0') else bbox[0]
                        y0 = getattr(bbox, 'y0', None) if hasattr(bbox, 'y0') else bbox[1]
                        x1 = getattr(bbox, 'x1', None) if hasattr(bbox, 'x1') else bbox[2]
                        y1 = getattr(bbox, 'y1', None) if hasattr(bbox, 'y1') else bbox[3]
                    except Exception:
                        return None
                    # Heuristic: coordinates are often in PDF points; derive scaling
                    # If page object exposes width/height, use to scale to pixel dims.
                    px_w, px_h = page_img.size
                    page_w = getattr(page_obj, 'width', None) or getattr(page_obj, 'w', None)
                    page_h = getattr(page_obj, 'height', None) or getattr(page_obj, 'h', None)
                    if page_w and page_h:
                        sx = px_w / page_w
                        sy = px_h / page_h
                    else:
                        # Assume already pixel coordinates
                        sx = sy = 1.0
                    crop_box = (int(x0 * sx), int(y0 * sy), int(x1 * sx), int(y1 * sy))
                    # Sanitize crop box within bounds
                    crop_box = (
                        max(0, min(px_w, crop_box[0])),
                        max(0, min(px_h, crop_box[1])),
                        max(0, min(px_w, crop_box[2])),
                        max(0, min(px_h, crop_box[3])),
                    )
                    if crop_box[2] > crop_box[0] and crop_box[3] > crop_box[1]:
                        return page_img.crop(crop_box)
            except Exception as e:
                self.logger.debug(f"Crop fallback failed: {e}")
            return None

        # Extract images
        for idx, tbl in enumerate(table_items, start=1):
            try:
                pil_image = _table_to_image(tbl)
                if pil_image is None:
                    self.logger.warning(f"Unable to derive image for table {idx}; skipping")
                    continue
                filename = f"table_{idx}.png"
                out_path = self.table_images_dir / filename
                pil_image.save(out_path, "PNG")
                table_image_mapping[idx] = [filename]
                self.logger.debug(f"Saved table snapshot image: {out_path}")
            except Exception as e:
                self.logger.warning(f"Failed to save image for table {idx}: {e}")

        # Strategy 3: As absolute last resort, if no images produced but tables exist, store distinct page images with table index naming to signal fallback.
        if not table_image_mapping:
            try:
                raw_tables = getattr(result.document, 'tables', [])
                if raw_tables:
                    self.logger.info("Falling back to page-level images for tables (no direct snapshots)")
                    page_usage: Dict[int, int] = {}
                    for idx, tbl in enumerate(raw_tables, start=1):
                        page_no = getattr(tbl, 'page_no', None) or getattr(tbl, 'page', None)
                        if page_no and page_no in getattr(result.document, 'pages', {}):
                            page_usage[page_no] = page_usage.get(page_no, 0) + 1
                            page_img = result.document.pages[page_no].image.pil_image
                            filename = f"table_{idx}_page_{page_no}.png"
                            out_path = self.table_images_dir / filename
                            try:
                                page_img.save(out_path, "PNG")
                                table_image_mapping[idx] = [filename]
                                self.logger.debug(f"Fallback saved page image for table {idx} -> {out_path}")
                            except Exception as e:
                                self.logger.debug(f"Fallback save failed for table {idx}: {e}")
            except Exception:
                pass

        if not table_image_mapping:
            self.logger.info("No table images were saved (no tables found or all strategies failed)")
        else:
            self.logger.info(f"Saved {sum(len(v) for v in table_image_mapping.values())} table image(s) for {len(table_image_mapping)} table(s)")

        return table_image_mapping

    def _update_markdown_references(
        self, 
        markdown_text: str, 
        picture_mapping: Dict[int, str], 
        table_mapping: Dict[int, str],
        table_image_mapping: Dict[int, List[str]]
    ) -> str:
        """Updates the markdown text to include proper references to images and tables."""
        self.logger.debug("Updating markdown references")
        # Helper to normalize a path (absolute) as string for markdown comment usage.
        # Using resolve() ensures we capture the full path even if relative segments remain.
        # We intentionally retain Windows-style backslashes; consumers can normalize if needed.
        def _full(p: Path) -> str:
            try:
                return str(p.resolve())
            except Exception:
                return str(p)
        
        # First, let's identify and extract all tables in the markdown
        table_pattern = (r'(\|[^\n]+\|\n\|[-\s|]+\|\n(?:\|[^\n]+\|\n)+)')
        tables_in_md = re.findall(table_pattern, markdown_text)
        
        self.logger.debug(f"Found {len(tables_in_md)} tables in original markdown")
        
        # Track which table indices from table_mapping we've processed
        processed_table_indices = set()
        
        # For each table in markdown, add references but KEEP the table content
        for idx, table_content in enumerate(tables_in_md, start=1):
            refs = []
            
            # Add markdown reference if available
            if idx in table_mapping:
                processed_table_indices.add(idx)
                full_table_path = _full(self.tables_dir / table_mapping[idx])
                refs.append(f"<!-- table : {full_table_path} -->")
            
            # Add image references if available
            if idx in table_image_mapping:
                for image_filename in table_image_mapping[idx]:
                    full_table_image_path = _full(self.table_images_dir / image_filename)
                    refs.append(f"<!-- table_image : {full_table_image_path} -->")
            
            # Combine references WITH the table content
            if refs:
                combined_refs = "\n".join(refs)
                combined_content = combined_refs + "\n\n" + table_content
                markdown_text = markdown_text.replace(table_content, combined_content)
        
        # Now handle tables that were extracted but not detected in the markdown
        missing_table_indices = set(table_mapping.keys()) - processed_table_indices
        if missing_table_indices:
            self.logger.info(f"Found {len(missing_table_indices)} tables that weren't detected in the markdown")
            
            # Find the end of the document to append missing tables
            # Prefer to add before any potential footnotes or references
            # Commonly marked by headings like "References", "Footnotes", "Notes"
            ending_section_pattern = r'(?i)^#+\s*(References|Footnotes|Notes|Bibliography|Appendix)'
            ending_matches = re.search(ending_section_pattern, markdown_text, re.MULTILINE)
            
            if ending_matches:
                insert_position = ending_matches.start()
            else:
                insert_position = len(markdown_text)
            
            missing_tables_content = "\n\n## Additional Tables\n\n"
            for table_idx in sorted(missing_table_indices):
                table_file = self.tables_dir / table_mapping[table_idx]
                if table_file.exists():
                    try:
                        with open(table_file, 'r', encoding='utf-8') as f:
                            table_content = f.read().strip()
                            if table_content.startswith('|') and '|---' in table_content:
                                full_table_path = _full(self.tables_dir / table_mapping[table_idx])
                                refs = [f"<!-- table : {full_table_path} -->"]
                                
                                # Add image references if available
                                if table_idx in table_image_mapping:
                                    for image_filename in table_image_mapping[table_idx]:
                                        full_table_image_path = _full(self.table_images_dir / image_filename)
                                        refs.append(f"<!-- table_image : {full_table_image_path} -->")
                                
                                combined_refs = "\n".join(refs)
                                missing_tables_content += f"\n\n### Table {table_idx}\n\n{combined_refs}\n\n{table_content}\n\n"
                                self.logger.debug(f"Adding missing table {table_idx} to markdown")
                    except Exception as e:
                        self.logger.warning(f"Failed to read missing table file {table_file}: {e}")
            
            # Insert the missing tables at the chosen position
            if missing_tables_content != "\n\n## Additional Tables\n\n":
                markdown_text = (
                    markdown_text[:insert_position] + 
                    missing_tables_content + 
                    markdown_text[insert_position:]
                )
        
        # Replace generic image placeholders with specific ones
        # This is trickier now because we've filtered out some images
        # We'll use the picture_mapping which only contains valid images
        image_placeholders = []
        placeholder_positions = []
        
        # Find all image placeholders and their positions
        pos = 0
        while True:
            pos = markdown_text.find('<!-- image -->', pos)
            if pos == -1:
                break
            image_placeholders.append('<!-- image -->')
            placeholder_positions.append(pos)
            pos += len('<!-- image -->')
        
        self.logger.debug(f"Found {len(placeholder_positions)} image placeholders in markdown")
        
        # Replace valid image placeholders and remove invalid ones
        new_markdown = markdown_text
        offset = 0  # Track position offset as we modify the string
        
        for idx, pos in enumerate(placeholder_positions, start=1):
            if idx in picture_mapping:
                # Replace with valid image reference using full absolute path
                full_image_path = _full(self.images_dir / picture_mapping[idx])
                image_ref = f"<!-- image : {full_image_path} -->"
                adjusted_pos = pos + offset
                new_markdown = (new_markdown[:adjusted_pos] + image_ref +
                              new_markdown[adjusted_pos + 
                                         len('<!-- image -->'):])
                offset += len(image_ref) - len('<!-- image -->')
                self.logger.debug(f"Updated reference for image {idx} -> {full_image_path}")
            else:
                # Remove invalid image placeholder
                adjusted_pos = pos + offset
                new_markdown = (new_markdown[:adjusted_pos] +
                              new_markdown[adjusted_pos +
                                         len('<!-- image -->'):])
                offset -= len('<!-- image -->')
                self.logger.debug(f"Removed invalid placeholder for image {idx}")
        
        return new_markdown

    def process(self):
        """Process the PDF file and save outputs."""
        self.logger.info(f"Processing file: {self.pdf_path.name}")

        # Extract text, tables, images, and coordinates
        text, tables, images, coordinates = self.extract_text_and_assets()

        # Save outputs
        base_name = self.pdf_path.stem
        self.save_markdown(self.markdown_file, self.pdf_path.name, text, tables, images)
        self.save_tables(self.tables_dir, base_name, tables)
        self.save_images(self.images_dir, base_name, images)
        self.save_coordinates(self.output_dir / f"{base_name}_coordinates.json", coordinates)

    def extract_text_and_assets(self):
        """Extract text, tables, images, and coordinates from a PDF file."""
        try:
            import PyPDF2
            text = []
            coordinates = []
            with open(self.pdf_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page_num, page in enumerate(reader.pages):
                    try:
                        page_text = page.extract_text() or ""
                        text.append(page_text)
                        # Placeholder for extracting coordinates (e.g., bounding boxes)
                        coordinates.append({"page": page_num + 1, "coordinates": []})
                    except Exception:
                        text.append("")
                        coordinates.append({"page": page_num + 1, "coordinates": []})
            full_text = "\n\n".join(text)
        except Exception:
            self.logger.debug("PyPDF2 not available or failed; using fallback byte info")
            full_text = f"[Unable to extract text from {self.pdf_path.name} - PyPDF2 not installed]"
            coordinates = []

        return full_text, [], [], coordinates

    def save_markdown(self, md_path: Path, title: str, text: str, tables, images):
        """Save extracted text to a markdown file with annotated placeholders."""
        content = f"# {title}\n\n{text}\n\n"
        for i, _ in enumerate(tables):
            content += f"[Table {i + 1} Placeholder]\n\n"
        for i, _ in enumerate(images):
            content += f"![Image {i + 1} Placeholder](images/{self.pdf_path.stem}_img_{i + 1}.png)\n\n"
        md_path.write_text(content, encoding='utf-8')

    def save_tables(self, tables_folder: Path, base_name: str, tables):
        """Save extracted tables as markdown files."""
        for i, table in enumerate(tables):
            out = tables_folder / f"{base_name}_table_{i+1}.md"
            out.write_text(str(table), encoding='utf-8')

    def save_images(self, images_folder: Path, base_name: str, images):
        """Save extracted images as PNG files."""
        for i, img in enumerate(images):
            out = images_folder / f"{base_name}_img_{i+1}.png"
            if isinstance(img, Image.Image):
                img.save(out)

    def save_coordinates(self, json_path: Path, coordinates):
        """Save extracted coordinates to a JSON file."""
        with json_path.open('w', encoding='utf-8') as f:
            json.dump(coordinates, f, indent=4)

def process_pdf_directory(pdf_dir: Path, output_base: Path, logger) -> int:
    """Iterate through PDFs and process each one creating an isolated output folder per PDF.

    For each PDF we produce:
      - document.md (full text with inline placeholders referencing tables/images)
      - tables/ (markdown files for each extracted table preserving structure)
      - images/ (PNG images: page_#.png, picture_#.png, table image snapshots if available)
      - coordinates.json (bounding boxes for each word/span of text)
      - document.json (raw docling JSON representation)

    Returns the number of successfully processed files.
    """
    # Gather list of PDFs first so we can show total in progress bar
    pdf_files: List[Path] = [p for p in pdf_dir.iterdir() if p.is_file() and p.suffix.lower() == '.pdf']
    processed = 0
    use_pbar = _cfg(['document_processing', 'pdf_extraction', 'use_progress_bar'], True)

    iterator = pdf_files
    pbar = None
    if use_pbar:
        try:
            from tqdm import tqdm  # type: ignore
            pbar = tqdm(iterator, total=len(pdf_files), desc='Processing PDFs', unit='file')
            iterator = pbar  # type: ignore
        except Exception:
            logger.warning('tqdm import failed; continuing without progress bar')

    for child in iterator:  # type: ignore
        pdf_output_dir = output_base / child.stem
        pdf_output_dir.mkdir(parents=True, exist_ok=True)
        try:
            extractor = PdfExtractor(
                pdf_path=child,
                output_dir=pdf_output_dir,
                images_scale=None,
                table_mode=None
            )
            extractor.extract()
            extractor.generate_coordinates_json()
            processed += 1
            logger.info(f"Processed PDF: {child.name}", output_dir=str(pdf_output_dir))
        except Exception as e:
            logger.exception(f"Failed to process PDF: {child} - {e}")
        finally:
            if pbar is not None:
                try:
                    pbar.set_postfix({'last': child.name, 'processed': processed})
                except Exception:
                    pass
    if pbar is not None:
        pbar.close()
    return processed

    
###############################
# Coordinate Extraction Logic #
###############################

def _extract_docling_coordinates(docling_result, logger) -> List[Dict[str, Any]]:
    """Attempt to extract coordinates from docling result structure.

    The docling document model can evolve; we defensively traverse common
    attributes (pages -> blocks -> lines -> spans) collecting text & bbox.
    """
    coordinates: List[Dict[str, Any]] = []
    try:
        pages = getattr(docling_result.document, 'pages', {})
        for page in pages.values():
            page_words: List[Dict[str, Any]] = []
            # Common nesting attributes seen in docling
            blocks = getattr(page, 'blocks', []) or getattr(page, 'text_blocks', [])
            for block in blocks:
                lines = getattr(block, 'lines', []) or getattr(block, 'text_lines', [])
                for line in lines:
                    spans = getattr(line, 'spans', []) or getattr(line, 'text_spans', [])
                    for span in spans:
                        text = getattr(span, 'text', '')
                        box = getattr(span, 'box', None) or getattr(span, 'bbox', None)
                        if box is None:
                            continue
                        # Support both dataclass-like and tuple-like boxes
                        try:
                            x0 = getattr(box, 'x0', None) if hasattr(box, 'x0') else box[0]
                            y0 = getattr(box, 'y0', None) if hasattr(box, 'y0') else box[1]
                            x1 = getattr(box, 'x1', None) if hasattr(box, 'x1') else box[2]
                            y1 = getattr(box, 'y1', None) if hasattr(box, 'y1') else box[3]
                        except Exception:
                            continue
                        page_words.append({
                            'text': text,
                            'bbox': {'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1}
                        })
            coordinates.append({'page': getattr(page, 'page_no', len(coordinates)+1), 'words': page_words})
        if not coordinates:
            logger.warning("Docling coordinate extraction produced no data")
    except Exception as e:
        logger.warning(f"Docling coordinate extraction failed: {e}")
    return coordinates

def _extract_pymupdf_coordinates(pdf_path: Path, logger) -> List[Dict[str, Any]]:
    """Fallback coordinate extraction using PyMuPDF (fitz)."""
    coordinates: List[Dict[str, Any]] = []
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(pdf_path)
        for page_index in range(len(doc)):
            page = doc[page_index]
            words = page.get_text("words")  # list of (x0,y0,x1,y1, word, block_no, line_no, word_no)
            page_words = []
            for w in words:
                if len(w) >= 5:
                    x0, y0, x1, y1, word = w[:5]
                    if word.strip():
                        page_words.append({'text': word, 'bbox': {'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1}})
            coordinates.append({'page': page_index + 1, 'words': page_words})
        return coordinates
    except Exception as e:
        logger.warning(f"PyMuPDF coordinate extraction failed: {e}")
        return coordinates

def _merge_coordinates(primary: List[Dict[str, Any]], fallback: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merge two coordinate lists preferring primary; if primary page empty, use fallback page."""
    if not primary:
        return fallback
    if not fallback:
        return primary
    merged: List[Dict[str, Any]] = []
    for p_page in primary:
        f_page = next((fp for fp in fallback if fp['page'] == p_page['page']), None)
        if p_page.get('words'):
            merged.append(p_page)
        elif f_page and f_page.get('words'):
            merged.append(f_page)
        else:
            merged.append(p_page)
    # Include any fallback pages not present in primary
    primary_pages = {p['page'] for p in primary}
    for f_page in fallback:
        if f_page['page'] not in primary_pages:
            merged.append(f_page)
    return merged

def _write_coordinates_json(coordinates: List[Dict[str, Any]], output_path: Path, logger) -> None:
    try:
        with output_path.open('w', encoding='utf-8') as f:
            json.dump({'pages': coordinates}, f, indent=2)
        logger.info(f"Saved coordinates JSON: {output_path}")
    except Exception as e:
        logger.error(f"Failed to write coordinates JSON {output_path}: {e}")

# Extend PdfExtractor with coordinate generation capability
def _pdf_extractor_generate_coordinates_json(self: 'PdfExtractor') -> None:  # type: ignore
    """Generate coordinates.json combining docling & PyMuPDF extraction."""
    coords_docling: List[Dict[str, Any]] = []
    if hasattr(self, 'converter'):
        try:
            # Re-run lightweight conversion (fast reuse) to access structured doc again
            result = self.converter.convert(self.pdf_path)
            coords_docling = _extract_docling_coordinates(result, self.logger)
        except Exception as e:
            self.logger.warning(f"Docling conversion for coordinates failed: {e}")
    coords_pymupdf = _extract_pymupdf_coordinates(self.pdf_path, self.logger)
    merged = _merge_coordinates(coords_docling, coords_pymupdf)
    _write_coordinates_json(merged, self.output_dir / 'coordinates.json', self.logger)

# Bind method dynamically
PdfExtractor.generate_coordinates_json = _pdf_extractor_generate_coordinates_json  # type: ignore
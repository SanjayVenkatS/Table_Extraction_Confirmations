"""
ADI PDF Extraction Module
========================

Simple PDF processing using Azure Document Intelligence API.
"""

from pathlib import Path
from typing import List, Optional, Dict
import json
import re
import sys
import io
from dataclasses import dataclass
from langchain_core.documents import Document as LangChainDocument
from langchain_community.document_loaders import AzureAIDocumentIntelligenceLoader
import time
try:
    import fitz  # PyMuPDF for PDF page image extraction
except ImportError:
    fitz = None
try:
    from PIL import Image
except ImportError:
    Image = None

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from core import adi_config
from core.logger import Logger, StructuredLogger
from core.exception_handler import exception_handler, ContextualErrorLogger, PDFProcessingExceptionHandler

# Simple exception classes
class ExtractionError(Exception):
    """Custom exception for extraction-related errors."""
    pass

class ProcessingError(Exception):
    """Custom exception for processing-related errors."""
    pass

@dataclass
class ADIExtractionResult:
    """Result of PDF extraction using Azure Document Intelligence."""
    pdf_path: Path
    output_dir: Path
    markdown_content: str
    extraction_method: str
    processing_time: float
    page_count: int
    success: bool
    table_count: int
    error_message: Optional[str] = None

class ADIExtractor:
    """
    Azure Document Intelligence PDF Extractor.
    
    This class handles the extraction of text and tables from PDF
    documents using Azure Document Intelligence API and saves them
    to specified output directories.
    """

    def __init__(
        self,
        pdf_path: Path,
        output_dir: Path,
        azure_endpoint: Optional[str] = None,
        azure_key: Optional[str] = None
    ):
        """
        Initialize the ADI PDF Extractor.

        Args:
            pdf_path (Path): Path to the input PDF file.
            output_dir (Path): Directory where extracted content will be saved.
            azure_endpoint (str, optional): Azure endpoint override.
            azure_key (str, optional): Azure key override.
        """
        try:
            self.logger = StructuredLogger("ADIExtractor")
        except Exception:
            self.logger = Logger.get_logger("ADIExtractor")
        
        self.logger.info(f"Initializing ADI Extractor for: {pdf_path}")
        
        # Input and output paths
        self.pdf_path = Path(pdf_path)
        self.output_dir = Path(output_dir)
        self.tables_dir = self.output_dir / adi_config.processing.tables_folder_name
        self.images_dir = self.output_dir / getattr(adi_config.processing, 'images_folder_name', 'images')
        self.table_images_dir = self.output_dir / getattr(adi_config.processing, 'table_images_folder_name', 'table_images')
        self.markdown_file = self.output_dir / adi_config.processing.combined_content_filename
        self.metadata_file = self.output_dir / adi_config.processing.metadata_filename
        
        # Azure configuration
        self.azure_endpoint = azure_endpoint or adi_config.azure.endpoint
        self.azure_key = azure_key or adi_config.azure.api_key
        
        # Initialize PDF processing exception handler
        self.exception_handler = PDFProcessingExceptionHandler(self.pdf_path.name)
        
        # Create necessary directories
        self._create_output_directories()
        
        # Initialize Azure loader
        self.loader = self._initialize_azure_loader()
        
        self.logger.info("ADI Extractor initialized successfully")
        
    def _create_output_directories(self) -> None:
        """Create the necessary output directories if they don't exist."""
        self.logger.debug("Creating output directories")
        directories = [self.output_dir, self.images_dir]
        if adi_config.processing.save_individual_tables:
            directories.append(self.tables_dir)
        if getattr(adi_config.processing, 'extract_table_images', False):
            directories.append(self.table_images_dir)
            
        for folder in directories:
            folder.mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"Created directory: {folder}")
            
    def _initialize_azure_loader(self) -> AzureAIDocumentIntelligenceLoader:
        """
        Initialize the Azure Document Intelligence loader.
        
        Returns:
            AzureAIDocumentIntelligenceLoader: Configured Azure loader.
        """
        self.logger.debug("Initializing Azure Document Intelligence loader")
        return AzureAIDocumentIntelligenceLoader(
            api_endpoint=self.azure_endpoint,
            api_key=self.azure_key,
            file_path=str(self.pdf_path),
            api_model=adi_config.azure.api_model,
            mode=adi_config.azure.mode
        )
    
    @exception_handler
    def extract(self) -> ADIExtractionResult:
        """
        Execute the PDF extraction process using Azure Document Intelligence.
        
        Returns:
            ADIExtractionResult: Results of the extraction process.
        """
        import time
        start_time = time.time()
        
        try:
            if not self.pdf_path.exists():
                error_msg = f"PDF file not found: {self.pdf_path}"
                self.logger.error(error_msg)
                return ADIExtractionResult(
                    pdf_path=self.pdf_path,
                    output_dir=self.output_dir,
                    markdown_content="",
                    extraction_method="azure_di",
                    processing_time=0,
                    page_count=0,
                    success=False,
                    table_count=0,
                    error_message=error_msg
                )
            
            self.logger.info(f"Processing {self.pdf_path.name}")
            
            # Load documents using Azure Document Intelligence
            documents = self._load_pdf_documents()
            
            if not documents:
                error_msg = f"No content extracted from {self.pdf_path.name}"
                self.logger.warning(error_msg)
                return ADIExtractionResult(
                    pdf_path=self.pdf_path,
                    output_dir=self.output_dir,
                    markdown_content="",
                    extraction_method="azure_di",
                    processing_time=time.time() - start_time,
                    page_count=0,
                    success=False,
                    table_count=0,
                    error_message=error_msg
                )
            
            self.logger.info("Azure DI processing completed")
            
            # Save extraction results including tables and metadata
            table_count = self._save_extraction_results(documents)
            
            # Extract and save page images (one image per page) - check config setting
            if getattr(adi_config.processing, 'extract_page_images', True):
                self._save_page_images()
            
            # Extract and save table images using Azure DI bounding regions
            if getattr(adi_config.processing, 'extract_table_images', False):
                self.logger.info("Starting table image extraction")
                self._save_table_images(documents)
            
            # Create markdown content from documents
            markdown_content = self._create_markdown_content(documents)
            
            processing_time = time.time() - start_time
            self.logger.info(f"Markdown content created successfully: {len(markdown_content)} characters")
            self.logger.info(f"Extraction completed successfully. Output saved to: {self.output_dir}")
            self.logger.info(f"Successfully processed {self.pdf_path.name}")
            
            return ADIExtractionResult(
                pdf_path=self.pdf_path,
                output_dir=self.output_dir,
                markdown_content=markdown_content,
                extraction_method="azure_di",
                processing_time=processing_time,
                page_count=len(documents),
                success=True,
                table_count=table_count
            )
            
        except Exception as e:
            error_msg = f"Error processing {self.pdf_path.name}: {e}"
            self.logger.error(error_msg)
            
            # Handle Azure API errors
            if hasattr(e, 'status_code'):
                self.exception_handler.handle_azure_api_error(e)
            else:
                self.exception_handler.handle_file_processing_error(e, "Azure_DI_Loading")
            
            return ADIExtractionResult(
                pdf_path=self.pdf_path,
                output_dir=self.output_dir,
                markdown_content="",
                extraction_method="azure_di",
                processing_time=time.time() - start_time,
                page_count=0,
                success=False,
                table_count=0,
                error_message=error_msg
            )
    
    def _load_pdf_documents(self) -> List[LangChainDocument]:
        """
        Load PDF documents using Azure Document Intelligence loader.
        
        Returns:
            List[LangChainDocument]: List of processed documents.
        """
        try:
            self.logger.info("Loading documents using Azure DI loader")
            documents = self.loader.load()
            
            if not documents:
                # Create error document with metadata
                error_doc = LangChainDocument(
                    page_content="Page Content not available, image might be present.",
                    metadata={
                        "filename": self.pdf_path.name,
                        "page_number": 1,
                        "source_path": str(self.pdf_path),
                        "error": "No documents returned from Azure DI"
                    }
                )
                documents = [error_doc]
                
            self.logger.info(f"Loaded {len(documents)} documents from PDF")
            return documents
            
        except Exception as e:
            self.logger.error(f"Error loading PDF documents: {e}")
            # Create error document with metadata
            error_doc = LangChainDocument(
                page_content="Page Content not available, image might be present.",
                metadata={
                    "filename": self.pdf_path.name,
                    "page_number": 1,
                    "source_path": str(self.pdf_path),
                    "error": str(e)
                }
            )
            return [error_doc]
    
    def _convert_html_tables_to_markdown(self, content: str) -> tuple[str, int]:
        """Convert HTML tables to Markdown format."""
        def html_table_to_markdown(table_html):
            try:
                row_pattern = r'<tr[^>]*>(.*?)</tr>'
                rows = re.findall(row_pattern, table_html, re.DOTALL | re.IGNORECASE)
                markdown_lines = []
                
                for row_idx, row in enumerate(rows):
                    cell_pattern = r'<(?:th|td)[^>]*>(.*?)</(?:th|td)>'
                    cells = re.findall(cell_pattern, row, re.DOTALL | re.IGNORECASE)
                    clean_cells = []
                    
                    for cell in cells:
                        clean_cell = re.sub(r'<[^>]+>', '', cell).strip()
                        clean_cell = re.sub(r'\s+', ' ', clean_cell)
                        clean_cell = clean_cell.replace('|', '\\|')
                        clean_cells.append(clean_cell)
                    
                    if clean_cells:
                        markdown_row = "| " + " | ".join(clean_cells) + " |"
                        markdown_lines.append(markdown_row)
                        
                        if row_idx == 0:
                            separator = "| " + " | ".join(["---"] * len(clean_cells)) + " |"
                            markdown_lines.append(separator)
                
                return "\n".join(markdown_lines)
            except Exception as e:
                self.logger.error(f"Table conversion error: {e}")
                return f"[Table conversion error: {e}]"
        
        table_pattern = r'<table[^>]*>(.*?)</table>'
        tables = re.findall(table_pattern, content, re.DOTALL | re.IGNORECASE)
        
        def replace_table(match):
            table_html = match.group(0)
            return html_table_to_markdown(table_html)
        
        markdown_content = re.sub(table_pattern, replace_table, content, flags=re.DOTALL | re.IGNORECASE)
        return markdown_content, len(tables)
    
    def _save_individual_tables(self, content: str) -> int:
        """Save individual table files and return table count."""
        if not adi_config.processing.save_individual_tables:
            return 0
            
        table_pattern = r'<table[^>]*>(.*?)</table>'
        tables = re.findall(table_pattern, content, re.DOTALL | re.IGNORECASE)
        
        if not tables:
            return 0
            
        try:
            for i, table_html in enumerate(tables):
                try:
                    markdown_table, _ = self._convert_html_tables_to_markdown(f"<table>{table_html}</table>")
                    if markdown_table and not markdown_table.startswith("[Table conversion error"):
                        md_file = self.tables_dir / f"{adi_config.processing.table_filename_prefix}{i+1}.md"
                        with open(md_file, 'w', encoding=adi_config.encoding) as f:
                            f.write(f"# Table {i+1}\n\n{markdown_table}\n")
                        
                        if adi_config.logging.show_table_save_confirmations:
                            self.logger.debug(f"Table {i+1} saved as: {md_file.name}")
                except Exception as e:
                    self.logger.error(f"Error processing table {i+1}: {e}")
        except Exception as e:
            self.logger.error(f"Error creating tables folder: {e}")
            raise ProcessingError(f"Failed to create tables folder: {e}")
        
        return len(tables)
    
    def _remove_pdf_page_numbers(self, content: str) -> str:
        """
        Remove only PDF page-related comments while preserving other important HTML content.
        Uses exact string matching for known PDF page patterns.
        """
        import re
        
        # Find all HTML comments
        comment_pattern = r'<!--[^>]*?-->'
        comments = re.findall(comment_pattern, content, re.DOTALL)
        
        cleaned_content = content
        
        for comment in comments:
            # Extract the inner content of the comment
            inner_content = comment[4:-3].strip()  # Remove <!-- and -->
            
            # Check if this is a PDF page-related comment
            should_remove = False
            
            # Specific PDF page patterns to remove:
            if any(pattern in inner_content for pattern in [
                'PageNumber=', 'PageFooter=', 'PageHeader=',
                'Page #', 'page #', '/Page ', ' Page ',
                'FOR INTERNAL USE', 'INTERNAL USE ONLY',
                'CONFIDENTIAL', 'DRAFT COPY'
            ]):
                should_remove = True
            
            # Check for number/number patterns typical of page numbers
            elif re.search(r'\d+/\d+', inner_content) or re.search(r'\d+\s+of\s+\d+', inner_content):
                should_remove = True
            
            # Check for patterns with parentheses and slashes (document IDs)
            elif re.search(r'\(\d+\)[/\\]\d+', inner_content):
                should_remove = True
            
            # Check for standalone page references with # 
            elif re.search(r'#\d+', inner_content) and len(inner_content) < 100:
                should_remove = True
            
            if should_remove:
                # Remove this specific comment
                escaped_comment = re.escape(comment)
                cleaned_content = re.sub(escaped_comment + r'\s*', '', cleaned_content)
        
        # Clean up extra whitespace
        cleaned_content = re.sub(r'\n{3,}', '\n\n', cleaned_content)
        
        return cleaned_content

    def _save_extraction_results(self, documents: List[LangChainDocument]) -> int:
        """Save extracted content and metadata to separate files."""
        try:
            # Create simple metadata structure (not the full Azure DI response)
            simple_metadata = {
                "document_info": {
                    "filename": self.pdf_path.name,
                    "processing_date": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "total_pages": len(documents),
                    "extraction_method": "azure_document_intelligence",
                    "output_directory": str(self.output_dir)
                },
                "processing_summary": {
                    "pages_processed": len(documents),
                    "content_length": sum(len(doc.page_content) for doc in documents)
                }
            }
            
            with open(self.metadata_file, 'w', encoding=adi_config.encoding) as f:
                json.dump(simple_metadata, f, indent=2, ensure_ascii=False)
            
            # Save combined content with Markdown tables
            original_combined_content = ""
            for page_idx, doc in enumerate(documents, 1):
                original_combined_content += f"\n<!-- page_number: page_{page_idx} -->\n"
                original_combined_content += doc.page_content
                original_combined_content += "\n"
            
            # Save individual table files and get count
            table_count = self._save_individual_tables(original_combined_content)
            if table_count > 0:
                self.logger.info(f"Extracted {table_count} tables")
            else:
                self.logger.info("No tables found in document")
                
            self.logger.info(f"Saving enhanced markdown to: {self.markdown_file}")
            
            # Save the combined content with Markdown tables
            with open(self.markdown_file, 'w', encoding='utf-8') as f:
                for page_idx, doc in enumerate(documents, 1):
                    page_content = doc.page_content
                    # Convert HTML tables to Markdown
                    page_content_with_md_tables, _ = self._convert_html_tables_to_markdown(page_content)
                    
                    # Remove PDF page numbers using dedicated function
                    page_content_with_md_tables = self._remove_pdf_page_numbers(page_content_with_md_tables)
                    
                    # Split content by Azure's page breaks and add custom page numbers
                    if "<!-- PageBreak -->" in page_content_with_md_tables:
                        page_sections = page_content_with_md_tables.split("<!-- PageBreak -->")
                        for i, section in enumerate(page_sections):
                            if section.strip():
                                f.write(section.strip())
                                f.write(f"\n\n{adi_config.processing.page_number_format.format(i + 1)}\n\n")
                    else:
                        f.write(page_content_with_md_tables)
                        f.write(f"\n\n{adi_config.processing.page_number_format.format(page_idx)}\n\n")
                    f.write("\n")
                    
            self.logger.info(f"Enhanced markdown with references saved to: {self.markdown_file}")
            return table_count

        except Exception as e:
            self.logger.error(f"Failed to save extraction results: {e}")
            raise ProcessingError(f"Failed to save extraction results: {e}")
    
    def _save_page_images(self) -> None:
        """Save each page as an image using PyMuPDF, similar to Docling's approach."""
        if fitz is None or Image is None:
            self.logger.warning("PyMuPDF (fitz) or PIL not available. Skipping page image extraction. Install with: pip install PyMuPDF Pillow")
            return
            
        try:
            self.logger.info("Saving page images")
            
            # Get configuration settings
            scale_factor = getattr(adi_config.processing, 'image_scale_factor', 2.0)
            image_format = getattr(adi_config.processing, 'image_format', 'PNG')
            
            # Open PDF document with PyMuPDF
            pdf_doc = fitz.open(str(self.pdf_path))
            page_count = len(pdf_doc)
            
            self.logger.debug(f"Saving {page_count} page images with scale factor {scale_factor}")
            
            for page_no in range(page_count):
                page = pdf_doc[page_no]
                
                # Convert page to image 
                # Using configurable scale factor for quality control
                matrix = fitz.Matrix(scale_factor, scale_factor)
                pix = page.get_pixmap(matrix=matrix)
                
                # Convert to PIL Image
                img_data = pix.tobytes("png")
                pil_image = Image.open(io.BytesIO(img_data))
                
                # Save image with same naming convention as Docling (1-indexed)
                image_path = self.images_dir / f"page_{page_no + 1}.{image_format.lower()}"
                self.logger.debug(f"Saving page {page_no + 1} image to: {image_path}")
                pil_image.save(image_path, format=image_format.upper())
                self.logger.debug(f"Page image saved: {image_path}")
                
            pdf_doc.close()
            self.logger.info(f"Successfully saved {page_count} page images")
            
        except Exception as e:
            self.logger.error(f"Failed to extract page images: {e}")
            # Don't raise exception - image extraction is optional
    
    def _save_table_images(self, documents: List[LangChainDocument]) -> None:
        """Extract and save table images using Azure DI bounding regions, similar to Docling's approach."""
        if fitz is None or Image is None:
            self.logger.warning("PyMuPDF (fitz) or PIL not available. Skipping table image extraction. Install with: pip install PyMuPDF Pillow")
            return
        
        try:
            self.logger.info("Saving table images using Azure DI bounding regions")
            
            # Get tables from Azure DI metadata
            tables_metadata = []
            for doc in documents:
                if 'tables' in doc.metadata:
                    tables_metadata.extend(doc.metadata['tables'])
            
            if not tables_metadata:
                self.logger.info("No tables found in Azure DI response")
                return
                
            # Open PDF document
            pdf_doc = fitz.open(str(self.pdf_path))
            
            # Get image scale factor from config
            scale_factor = getattr(adi_config.processing, 'image_scale_factor', 2.0)
            image_format = getattr(adi_config.processing, 'image_format', 'PNG')
            
            self.logger.debug(f"Processing {len(tables_metadata)} tables for image extraction")
            
            for idx, table_info in enumerate(tables_metadata, start=1):
                try:
                    # Get table bounding regions
                    bounding_regions = table_info.get('boundingRegions', [])
                    if not bounding_regions:
                        self.logger.warning(f"No bounding regions found for table {idx}")
                        continue
                    
                    # Use first bounding region (tables can span multiple regions)
                    region = bounding_regions[0]
                    page_number = region['pageNumber']
                    polygon = region['polygon']
                    
                    # Get page from PDF (1-indexed to 0-indexed)
                    if page_number <= len(pdf_doc):
                        page = pdf_doc[page_number - 1]
                        
                        # Convert page to image with scaling
                        matrix = fitz.Matrix(scale_factor, scale_factor)
                        pix = page.get_pixmap(matrix=matrix)
                        
                        # Convert to PIL Image
                        img_data = pix.tobytes("png")
                        page_image = Image.open(io.BytesIO(img_data))
                        
                        # Convert Azure DI coordinates to pixel coordinates
                        # Azure DI provides coordinates in inches, convert to points then pixels
                        page_width, page_height = page_image.size
                        
                        # Extract bounding box from polygon (assuming rectangular)
                        # Polygon format: [x1, y1, x2, y2, x3, y3, x4, y4] for 4 corners
                        if len(polygon) >= 8:
                            x_coords = [polygon[i] for i in range(0, len(polygon), 2)]
                            y_coords = [polygon[i] for i in range(1, len(polygon), 2)]
                            
                            # Get bounding box coordinates (in inches)
                            min_x = min(x_coords)
                            max_x = max(x_coords)
                            min_y = min(y_coords)
                            max_y = max(y_coords)
                            
                            # Convert from inches to points (1 inch = 72 points)
                            POINTS_PER_INCH = 72
                            min_x_pts = min_x * POINTS_PER_INCH
                            max_x_pts = max_x * POINTS_PER_INCH
                            min_y_pts = min_y * POINTS_PER_INCH
                            max_y_pts = max_y * POINTS_PER_INCH
                            
                            # Convert points to pixels using the scale factor
                            left = int(min_x_pts * scale_factor)
                            top = int(min_y_pts * scale_factor)
                            right = int(max_x_pts * scale_factor)
                            bottom = int(max_y_pts * scale_factor)
                            
                            # Ensure coordinates are within image bounds
                            left = max(0, min(page_width, left))
                            top = max(0, min(page_height, top))
                            right = max(0, min(page_width, right))
                            bottom = max(0, min(page_height, bottom))
                            
                            # Crop table from page image
                            if right > left and bottom > top:
                                table_image = page_image.crop((left, top, right, bottom))
                                
                                # Save table image with same naming convention as Docling
                                image_path = self.table_images_dir / f"table_{idx}.{image_format.lower()}"
                                table_image.save(image_path, format=image_format.upper())
                                
                                self.logger.debug(f"Table {idx} image saved to: {image_path}")
                            else:
                                self.logger.warning(f"Invalid crop coordinates for table {idx}")
                        else:
                            self.logger.warning(f"Invalid polygon format for table {idx}")
                    else:
                        self.logger.warning(f"Page {page_number} not found in PDF for table {idx}")
                        
                except Exception as e:
                    self.logger.error(f"Failed to extract image for table {idx}: {e}")
            
            pdf_doc.close()
            self.logger.info(f"Successfully saved {len(tables_metadata)} table images")
            
        except Exception as e:
            self.logger.error(f"Failed to extract table images: {e}")
            # Don't raise exception - table image extraction is optional
    
    def _create_markdown_content(self, documents: List[LangChainDocument]) -> str:
        """Create combined markdown content from documents with table image references."""
        markdown_content = ""
        
        # Get table metadata for creating image references
        tables_metadata = []
        for doc in documents:
            if 'tables' in doc.metadata:
                tables_metadata.extend(doc.metadata['tables'])
        
        for doc in documents:
            page_content_with_md_tables, _ = self._convert_html_tables_to_markdown(doc.page_content)
            
            # Add table image references similar to Docling's approach
            if tables_metadata and getattr(adi_config.processing, 'extract_table_images', False):
                page_content_with_md_tables = self._add_table_image_references(page_content_with_md_tables, tables_metadata)
            
            markdown_content += page_content_with_md_tables + "\n\n"
            
        return markdown_content
    
    def _add_table_image_references(self, markdown_content: str, tables_metadata: List[Dict]) -> str:
        """Add table image references to markdown content similar to Docling's approach."""
        try:
            # Find markdown tables and add image references
            table_pattern = r'(\|[^\n]+\|\n\|[-\s|]+\|\n(?:\|[^\n]+\|\n)+)'
            tables_found = list(re.finditer(table_pattern, markdown_content))
            
            if not tables_found:
                return markdown_content
                
            # Process tables from end to beginning to preserve positions
            for idx, match in enumerate(reversed(tables_found), 1):
                table_number = len(tables_found) - idx + 1  # Get correct table number
                
                if table_number <= len(tables_metadata):
                    # Create table image reference similar to Docling
                    table_image_path = self.table_images_dir / f"table_{table_number}.png"
                    table_file_path = self.tables_dir / f"table_{table_number}.md"
                    
                    # Add references before the table
                    references = []
                    if adi_config.processing.save_individual_tables and table_file_path.exists():
                        references.append(f"<!-- table : {table_file_path} -->")
                    
                    if getattr(adi_config.processing, 'extract_table_images', False) and table_image_path.exists():
                        references.append(f"<!-- table_image : {table_image_path} -->")
                    
                    if references:
                        reference_text = "\n".join(references) + "\n"
                        markdown_content = markdown_content[:match.start()] + reference_text + markdown_content[match.start():]
            
            return markdown_content
            
        except Exception as e:
            self.logger.error(f"Failed to add table image references: {e}")
            return markdown_content


# Get logger instance for backward compatibility
logger = Logger.get_logger("PDFExtraction")

# Legacy wrapper functions for backward compatibility
def load_pdf_with_azure_di(pdf_file: Path, azure_endpoint: Optional[str] = None, azure_key: Optional[str] = None) -> List[LangChainDocument]:
    """Legacy function wrapper for backward compatibility."""
    extractor = ADIExtractor(pdf_file, pdf_file.parent / f"{pdf_file.stem}_output", azure_endpoint, azure_key)
    return extractor._load_pdf_documents()

def save_extraction_results(documents: List[LangChainDocument], output_folder: str = "extraction_output"):
    """Legacy function wrapper for backward compatibility."""
    # Create a temporary extractor to use the save method
    output_path = Path(output_folder)
    pdf_path = Path("temp.pdf")  # Temporary path
    extractor = ADIExtractor(pdf_path, output_path)
    return extractor._save_extraction_results(documents)

@exception_handler
def process_pdf_folder(input_folder: str, output_folder: str = "output"):
    """Process all PDF files in input folder and save results to output folder."""
    try:
        input_path = Path(input_folder)
        output_path = Path(output_folder)
        
        if not input_path.exists():
            error_msg = f"Input folder not found: {input_path}"
            logger.error(error_msg)
            print(error_msg)
            return
        
        # Scan PDF Directory
        pdf_files = list(input_path.glob("*.pdf"))
        
        # Check if PDFs found
        if not pdf_files:
            error_msg = f"No PDF files found in: {input_path}"
            logger.warning(error_msg)
            print(error_msg)
            return
        
        logger.info(f"Found {len(pdf_files)} PDF files to process")
        output_path.mkdir(exist_ok=True)
        
        processing_stats = {
            'successful': 0,
            'failed': 0,
            'total_pages': 0
        }
        
        # Process Each PDF
        for pdf_file in pdf_files:
            try:
                logger.info(f"Processing {pdf_file.name}")
                
                folder_name = pdf_file.stem
                file_output_folder = output_path / folder_name
                
                # Initialize ADI extractor and process
                extractor = ADIExtractor(pdf_file, file_output_folder)
                result = extractor.extract()
                
                if result.success:
                    processing_stats['successful'] += 1
                    processing_stats['total_pages'] += result.page_count
                    logger.info(f"Processed PDF: {pdf_file.name} | output_dir={file_output_folder}")
                else:
                    logger.warning(f"Failed to process {pdf_file.name}: {result.error_message}")
                    processing_stats['failed'] += 1
            
            except Exception as e:
                error_msg = f"Failed to process {pdf_file.name}: {e}"
                logger.error(error_msg)
                processing_stats['failed'] += 1
        
        # Complete Processing
        logger.info(f"PDF processing finished | total_processed={processing_stats['successful']}")
        logger.info(f"Processing complete. Successful: {processing_stats['successful']}, Failed: {processing_stats['failed']}")

    except Exception as e:
        error_msg = f"Error in process_pdf_folder: {e}"
        logger.error(error_msg)
        raise ProcessingError(error_msg)

if __name__ == "__main__":
    try:
        logger.info("Starting PDF extraction process")
        
        input_folder = adi_config.paths.input_folder
        output_folder = adi_config.paths.output_folder
        
        logger.info(f"Input folder: {input_folder}")
        logger.info(f"Output folder: {output_folder}")
        
        process_pdf_folder(input_folder, output_folder)
        
        logger.info("PDF extraction process completed successfully")
        
    except Exception as e:
        logger.error(f"PDF extraction process failed: {e}")
        print(f"Error: {e}")
        sys.exit(1)

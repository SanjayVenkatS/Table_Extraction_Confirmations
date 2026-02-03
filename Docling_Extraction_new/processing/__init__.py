"""Processing Module
===================

Current minimalist PDF-only exports. Chunking and document manager
symbols have been removed from public exports for the slimmed workflow.
"""

from .pdf_processor import PdfExtractor, process_pdf_directory

__all__ = [
    'PdfExtractor',
    'process_pdf_directory'
]
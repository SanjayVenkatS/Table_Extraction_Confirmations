"""Processing Module
===================

PDF extraction module for ADI Extraction system.
"""

from .pdfextraction import load_pdf_with_azure_di, process_pdf_folder

__all__ = [
    'load_pdf_with_azure_di',
    'process_pdf_folder'
]
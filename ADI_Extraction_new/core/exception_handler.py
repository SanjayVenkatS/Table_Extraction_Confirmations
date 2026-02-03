"""
Exception Handler for ADI Extraction
===================================

Provides comprehensive exception handling and logging throughout the application.
"""

import sys
import traceback
import functools
from typing import Callable, Any
from core.logger import StructuredLogger, Logger

class GlobalExceptionHandler:
    """Global exception handler for capturing and logging all errors."""

    def __init__(self, service_name: str = "ADI_Extraction"):
        self.service_name = service_name
        self.logger = StructuredLogger(f"{service_name}_ExceptionHandler")
        self._original_excepthook = sys.excepthook
        self.setup_exception_handling()

    def setup_exception_handling(self):
        """Set up global exception handling."""
        sys.excepthook = self.handle_exception
        self.logger.info(f"{self.service_name} global exception handler initialized")

    def handle_exception(self, exc_type, exc_value, exc_traceback):
        """Handle uncaught exceptions."""
        if issubclass(exc_type, KeyboardInterrupt):
            self._original_excepthook(exc_type, exc_value, exc_traceback)
            return

        error_details = {
            'exception_type': exc_type.__name__,
            'exception_message': str(exc_value),
            'file': exc_traceback.tb_frame.f_code.co_filename,
            'line': exc_traceback.tb_lineno
        }

        tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        full_traceback = ''.join(tb_lines)
        self.logger.error("Unhandled exception", **{**error_details, 'traceback': full_traceback})


def exception_handler(func: Callable) -> Callable:
    """Decorator to wrap function execution with try/except and log exceptions."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = Logger.get_logger(func.__name__)
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.exception(f"Unhandled exception in {func.__name__}: {e}")
            raise
    return wrapper


class ContextualErrorLogger:
    """Context manager for adding contextual info to error logs."""
    def __init__(self, context_name: str, **context):
        self.context_name = context_name
        self.context = context
        self.logger = StructuredLogger(f"Context.{context_name}")
    
    def __enter__(self):
        self.logger.info("Entering context", **self.context)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.logger.error(f"Error in context", error=str(exc_val), **self.context)
        else:
            self.logger.info("Exiting context successfully", **self.context)
        # Do not suppress exceptions
        return False


# ADI-Specific Exception Handlers
class PDFProcessingExceptionHandler:
    """Specialized exception handler for PDF processing operations."""
    
    def __init__(self, pdf_filename: str):
        self.pdf_filename = pdf_filename
        self.logger = StructuredLogger("PDF_Processing")
        self.logger.set_context(pdf_file=pdf_filename)
    
    def handle_azure_api_error(self, error: Exception) -> None:
        """Handle Azure Document Intelligence API specific errors."""
        error_details = {
            'error_type': 'Azure_API_Error',
            'pdf_file': self.pdf_filename,
            'error_message': str(error)
        }
        
        if hasattr(error, 'status_code'):
            error_details['status_code'] = error.status_code
        if hasattr(error, 'error_code'):
            error_details['azure_error_code'] = error.error_code
            
        self.logger.error("Azure Document Intelligence API error", **error_details)
    
    def handle_file_processing_error(self, error: Exception, operation: str) -> None:
        """Handle file processing errors."""
        self.logger.error(f"File processing error during {operation}", 
                         error=str(error), 
                         operation=operation,
                         pdf_file=self.pdf_filename)
    
    def handle_table_extraction_error(self, error: Exception, table_index: int) -> None:
        """Handle table extraction specific errors."""
        self.logger.error("Table extraction error", 
                         error=str(error),
                         table_index=table_index,
                         pdf_file=self.pdf_filename)


# Convenience aliases for backward compatibility
ADIContextualErrorLogger = ContextualErrorLogger  # For existing ADI code
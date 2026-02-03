"""
Global Exception Handler for RegScan-V2
=======================================

Provides comprehensive exception handling and logging throughout the application.
"""

import sys
import traceback
import functools
from typing import Callable, Any
from core.logger import StructuredLogger, Logger

class GlobalExceptionHandler:
    """Global exception handler for capturing and logging all errors."""

    def __init__(self):
        self.logger = StructuredLogger("ExceptionHandler")
        self._original_excepthook = sys.excepthook
        self.setup_exception_handling()

    def setup_exception_handling(self):
        """Set up global exception handling."""
        sys.excepthook = self.handle_exception
        self.logger.info("Global exception handler initialized")

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
        # StructuredLogger formats kwargs into the message; avoid passing 'extra' which standard logger expects differently
        self.logger.error("Unhandled exception", **{**error_details, 'traceback': full_traceback})


def exception_handler(func: Callable) -> Callable:
    """Decorator to wrap function execution with try/except and log exceptions."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = Logger.get_logger(func.__name__)
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.exception(f"Unhandled exception: {e}")
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
            self.logger.error("Error in context", error=str(exc_val), **self.context)
        else:
            self.logger.info("Exiting context successfully", **self.context)
        # Do not suppress exceptions
        return False
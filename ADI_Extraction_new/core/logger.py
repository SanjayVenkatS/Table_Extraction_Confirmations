"""
Enhanced Logger for ADI Extraction
=================================

Provides comprehensive logging capabilities with rotation and structured logging 
for Azure Document Intelligence PDF extraction pipeline.
"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

class Logger:
    """Enhanced logger with rotation and structured logging for ADI extraction."""
    
    _loggers: Dict[str, logging.Logger] = {}
    _configured = False
    _error_file_handler = None
    
    @classmethod
    def configure_logging(cls, config: Optional[Dict[str, Any]] = None):
        """Configure the logging system for ADI Extraction."""
        if cls._configured:
            return
        
        if config is None:
            # Default configuration for ADI Extraction
            config = {
                'level': 'INFO',
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                'file_rotation': {
                    'max_bytes': 10485760,  # 10MB
                    'backup_count': 5
                }
            }
        
        # Create logs directory
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        
        # Set up root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, config['level'].upper()))
        
        # Clear any existing handlers
        root_logger.handlers.clear()
        
        # Create formatter
        formatter = logging.Formatter(config['format'])
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.INFO)
        root_logger.addHandler(console_handler)
        
        # ADI Extraction main log file with rotation
        log_file = logs_dir / f"adi_extraction_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=config['file_rotation']['max_bytes'],
            backupCount=config['file_rotation']['backup_count'],
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(getattr(logging, config['level'].upper()))
        root_logger.addHandler(file_handler)
        
        # ADI Extraction error-only log file with detailed formatting
        error_log_file = logs_dir / f"adi_extraction_errors_{datetime.now().strftime('%Y%m%d')}.log"
        error_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s\n'
            'Location: %(pathname)s:%(lineno)d in %(funcName)s()\n'
            'Message: %(message)s\n'
            'Thread: %(threadName)s | Process: %(processName)s\n'
            '{"="*80}\n'
        )
        
        cls._error_file_handler = logging.handlers.RotatingFileHandler(
            error_log_file,
            maxBytes=config['file_rotation']['max_bytes'],
            backupCount=10,  # Keep more error logs
            encoding='utf-8'
        )
        cls._error_file_handler.setFormatter(error_formatter)
        cls._error_file_handler.setLevel(logging.ERROR)
        root_logger.addHandler(cls._error_file_handler)
        
        cls._configured = True
    
    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """Get or create a logger instance."""
        if not cls._configured:
            cls.configure_logging()
        
        if name not in cls._loggers:
            logger = logging.getLogger(name)
            cls._loggers[name] = logger
        
        return cls._loggers[name]
    
    @classmethod
    def log_system_info(cls):
        """Log ADI Extraction system information at startup."""
        logger = cls.get_logger("System")
        logger.info("=" * 80)
        logger.info("ADI Extraction - Azure Document Intelligence PDF Processing")
        logger.info("=" * 80)
        logger.info(f"System started at: {datetime.now().isoformat()}")
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Working directory: {os.getcwd()}")
        logger.info("=" * 80)

class StructuredLogger:
    """Structured logger following Docling pattern for ADI extraction processing."""
    
    def __init__(self, name: str):
        self.logger = Logger.get_logger(name)
        self.context: Dict[str, Any] = {}
    
    def set_context(self, **kwargs):
        """Set context for structured logging."""
        self.context.update(kwargs)
    
    def clear_context(self):
        """Clear logging context."""
        self.context.clear()
    
    def _format_message(self, message: str, **kwargs) -> str:
        """Format message with context."""
        context = {**self.context, **kwargs}
        if context:
            context_str = " | ".join([f"{k}={v}" for k, v in context.items()])
            return f"{message} | {context_str}"
        return message
    
    def debug(self, message: str, **kwargs):
        """Log debug message with context."""
        self.logger.debug(self._format_message(message, **kwargs))
    
    def info(self, message: str, **kwargs):
        """Log info message with context."""
        self.logger.info(self._format_message(message, **kwargs))
    
    def warning(self, message: str, **kwargs):
        """Log warning message with context."""
        self.logger.warning(self._format_message(message, **kwargs))
    
    def error(self, message: str, **kwargs):
        """Log error message with context."""
        self.logger.error(self._format_message(message, **kwargs))
    
    def exception(self, message: str, **kwargs):
        """Log exception message with context and full traceback."""
        self.logger.exception(self._format_message(message, **kwargs))
    
    def critical(self, message: str, **kwargs):
        """Log critical message with context."""
        self.logger.critical(self._format_message(message, **kwargs))

class PDFProcessingLogger:
    """Specialized logger for tracking PDF processing pipeline steps."""
    
    def __init__(self, pdf_filename: str):
        self.logger = StructuredLogger("PDF_Processing")
        self.logger.set_context(pdf_file=pdf_filename)
        self.pdf_filename = pdf_filename
        self.step_number = 0
        self.total_steps = 0
    
    def set_total_steps(self, total: int):
        """Set total number of processing steps."""
        self.total_steps = total
        self.logger.info(f"Starting PDF processing pipeline for {self.pdf_filename}", total_steps=total)
    
    def start_step(self, step_name: str, **kwargs):
        """Start a processing step."""
        self.step_number += 1
        progress = f"{self.step_number}/{self.total_steps}" if self.total_steps > 0 else str(self.step_number)
        self.logger.info(f"Starting step: {step_name}", step=progress, **kwargs)
    
    def complete_step(self, step_name: str, duration_seconds: Optional[float] = None, **kwargs):
        """Complete a processing step."""
        progress = f"{self.step_number}/{self.total_steps}" if self.total_steps > 0 else str(self.step_number)
        log_kwargs = {"step": progress, **kwargs}
        if duration_seconds is not None:
            log_kwargs["duration_sec"] = round(duration_seconds, 2)
        self.logger.info(f"Completed step: {step_name}", **log_kwargs)
    
    def error_step(self, step_name: str, error: str, **kwargs):
        """Log step error."""
        progress = f"{self.step_number}/{self.total_steps}" if self.total_steps > 0 else str(self.step_number)
        self.logger.error(f"Error in step: {step_name} - {error}", step=progress, **kwargs)

class TableExtractionLogger:
    """Specialized logger for table extraction tracking."""
    
    def __init__(self, pdf_filename: str):
        self.logger = StructuredLogger("Table_Extraction")
        self.logger.set_context(pdf_file=pdf_filename)
        self.pdf_filename = pdf_filename
    
    def start_table_extraction(self, total_tables: int):
        """Log start of table extraction process."""
        self.logger.info(f"Starting table extraction from {self.pdf_filename}", 
                        total_tables=total_tables)
    
    def table_extracted(self, table_index: int, table_filename: str, 
                       rows: int = 0, columns: int = 0):
        """Log successful table extraction."""
        self.logger.info(f"Table extracted: {table_filename}", 
                        table_index=table_index, rows=rows, columns=columns)
    
    def table_error(self, table_index: int, error: str):
        """Log table extraction error."""
        self.logger.error(f"Table extraction failed for table {table_index}: {error}", 
                         table_index=table_index)
    
    def extraction_summary(self, total_tables: int, successful_tables: int, 
                          failed_tables: int, processing_time: float):
        """Log extraction summary."""
        self.logger.info(f"Table extraction completed for {self.pdf_filename}",
                        total_tables=total_tables,
                        successful_tables=successful_tables,
                        failed_tables=failed_tables,
                        processing_time_sec=round(processing_time, 2))

class AzureAPILogger:
    """Specialized logger for Azure Document Intelligence API interactions."""
    
    def __init__(self):
        self.logger = StructuredLogger("Azure_API")
    
    def log_api_request(self, pdf_filename: str, model: str, mode: str):
        """Log Azure API request."""
        self.logger.info("Azure Document Intelligence API request",
                        pdf_file=pdf_filename, model=model, mode=mode)
    
    def log_api_response(self, pdf_filename: str, pages_processed: int, 
                        tables_found: int, processing_time: float):
        """Log Azure API response."""
        self.logger.info("Azure Document Intelligence API response received",
                        pdf_file=pdf_filename,
                        pages_processed=pages_processed,
                        tables_found=tables_found,
                        api_processing_time_sec=round(processing_time, 2))
    
    def log_api_error(self, pdf_filename: str, error_code: str, error_message: str):
        """Log Azure API error."""
        self.logger.error("Azure Document Intelligence API error",
                         pdf_file=pdf_filename,
                         error_code=error_code,
                         error_message=error_message)
    
    def log_quota_usage(self, requests_made: int, quota_limit: int):
        """Log API quota usage."""
        self.logger.info("Azure API quota usage",
                        requests_made=requests_made,
                        quota_limit=quota_limit,
                        usage_percentage=round((requests_made/quota_limit)*100, 2))
"""
Enhanced Logger for RegScan-V2
=============================

Provides comprehensive logging capabilities with rotation and structured logging.
"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

class Logger:
    """Enhanced logger with rotation and structured logging."""
    
    _loggers: Dict[str, logging.Logger] = {}
    _configured = False
    _error_file_handler = None
    
    @classmethod
    def configure_logging(cls, config: Optional[Dict[str, Any]] = None):
        """Configure the logging system."""
        if cls._configured:
            return
        
        if config is None:
            # Default configuration
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
        
        # Main log file handler with rotation
        log_file = logs_dir / f"regscan_v2_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=config['file_rotation']['max_bytes'],
            backupCount=config['file_rotation']['backup_count'],
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(getattr(logging, config['level'].upper()))
        root_logger.addHandler(file_handler)
        
        # Error-only log file with detailed formatting
        error_log_file = logs_dir / f"regscan_v2_errors_{datetime.now().strftime('%Y%m%d')}.log"
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
        """Log system information at startup."""
        logger = cls.get_logger("System")
        logger.info("=" * 80)
        logger.info("RegScan-V2 Multi-Document RAG Extraction System")
        logger.info("=" * 80)
        logger.info(f"System started at: {datetime.now().isoformat()}")
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Working directory: {os.getcwd()}")
        logger.info("=" * 80)

class StructuredLogger:
    """Structured logger for tracking processing steps and metrics."""
    
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

class ProcessingLogger:
    """Specialized logger for tracking processing pipeline steps."""
    
    def __init__(self, jurisdiction: str, process_type: str):
        self.logger = StructuredLogger(f"Processing.{process_type}")
        self.logger.set_context(jurisdiction=jurisdiction, process=process_type)
        self.step_number = 0
        self.total_steps = 0
    
    def set_total_steps(self, total: int):
        """Set total number of processing steps."""
        self.total_steps = total
        self.logger.info(f"Starting processing pipeline", total_steps=total)
    
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

class FieldLogger:
    """Specialized logger for field extraction tracking."""
    
    def __init__(self, jurisdiction: str):
        self.logger = StructuredLogger("FieldExtraction")
        self.logger.set_context(jurisdiction=jurisdiction)
    
    def start_field_extraction(self, field_id: int, field_name: str, source: str):
        """Log start of field extraction."""
        self.logger.info(f"Extracting field: {field_name}", 
                        field_id=field_id, source=source)
    
    def field_extracted(self, field_id: int, field_name: str, 
                       confidence: float, has_custom_instruction: bool = False):
        """Log successful field extraction."""
        self.logger.info(f"Field extracted: {field_name}", 
                        field_id=field_id, confidence=confidence,
                        custom_instruction=has_custom_instruction)
    
    def field_error(self, field_id: int, field_name: str, error: str):
        """Log field extraction error."""
        self.logger.error(f"Field extraction failed: {field_name} - {error}", 
                         field_id=field_id)
    
    def field_not_found(self, field_id: int, field_name: str, source: str):
        """Log when field information is not found."""
        self.logger.warning(f"Field information not found: {field_name}", 
                           field_id=field_id, source=source)
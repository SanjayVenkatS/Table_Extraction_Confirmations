"""PDF Processing Entry Point
===========================

Minimal CLI entry point focused solely on PDF directory processing.
Removes all jurisdiction-based logic and delegates actual PDF work to
`processing/pdf_processor.py`.
"""

import ssl
import urllib3
import os

# Disable SSL verification FIRST before any other imports
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
ssl._create_default_https_context = ssl._create_unverified_context
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''

import argparse
import sys
from pathlib import Path
from core.logger import Logger, StructuredLogger
from core.exception_handler import exception_handler, ContextualErrorLogger
from processing.pdf_processor import process_pdf_directory
from core.config_loader import config as global_config

def _apply_environment(env_cfg: dict) -> None:
    """Apply environment variables from config."""
    for k, v in env_cfg.items():
        os.environ[str(k)] = str(v)

def configure_logging():
    """Configure logging using values from config.yaml."""
    log_cfg = global_config.logging_config if hasattr(global_config, 'logging_config') else {
        'level': 'INFO',
        'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        'file_rotation': {
            'max_bytes': 10485760,
            'backup_count': 5
        }
    }
    Logger.configure_logging(log_cfg)
    Logger.log_system_info()
    # Apply environment variables AFTER logging so we can trace them
    try:
        env_cfg = global_config._config['main'].get('environment', {})  # type: ignore
        _apply_environment(env_cfg)
        Logger.get_logger("CLI").info("Environment variables applied", **env_cfg)
    except Exception:
        Logger.get_logger("CLI").warning("Environment config missing; using process defaults")

@exception_handler
def run_pdf_mode(args):
    """Process a directory of PDFs and save outputs as markdown, tables, images, and coordinate JSON.

    Uses StructuredLogger to allow keyword/value context formatting without causing TypeErrors
    from the standard logging API (which only accepts specific kwargs like extra, exc_info).
    """
    # Use StructuredLogger so calls like logger.info("msg", total_processed=3) are properly formatted
    logger = StructuredLogger("PDF")
    with ContextualErrorLogger("PDFDirectoryProcessing", mode="pdf", pdf_dir=args.input_dir):
        try:
            if not args.input_dir:
                print("Error: --input-dir is required")
                return 1
            pdf_path = Path(args.input_dir)
            if not pdf_path.exists() or not pdf_path.is_dir():
                logger.error(f"PDF directory not found: {pdf_path}")
                print(f"Error: PDF directory not found: {pdf_path}")
                return 1
            output_base = Path(args.output_dir)
            output_base.mkdir(parents=True, exist_ok=True)
            processed = process_pdf_directory(pdf_path, output_base, logger)
            # Structured logging with contextual key-value pairs
            logger.info("PDF processing finished", total_processed=processed)
            print(f"Processed {processed} PDF files into: {output_base}")
            return 0
        except Exception as e:
            logger.exception(f"PDF processing failed: {e}")
            print(f"PDF processing failed: {e}")
            return 1

@exception_handler
def main():
    """Simplified main entry point for PDF processing only."""
    configure_logging()
    logger = Logger.get_logger("CLI")
    data_paths = global_config.data_paths if hasattr(global_config, 'data_paths') else {'output_dir': 'outputs'}
    parser = argparse.ArgumentParser(description="PDF Processing CLI")
    parser.add_argument('--input-dir', required=True, help="Directory containing PDF files to process")
    parser.add_argument('--output-dir', default=data_paths.get('output_dir', 'outputs'), help="Base output directory (default from config)")
    args = parser.parse_args()
    logger.info("Starting PDF processing run")
    return run_pdf_mode(args)


    # run_pdf_mode updated above

if __name__ == "__main__":
    sys.exit(main())
"""ADI Extraction Pipeline Entry Point
====================================

Minimal CLI entry point focused solely on PDF directory processing.
Delegates actual PDF work to `processing/pdfextraction.py`.
"""

import argparse
import sys
from pathlib import Path
from core.logger import Logger, StructuredLogger
from core.exception_handler import exception_handler, ContextualErrorLogger
from processing.pdfextraction import process_pdf_folder
from core.config_loader import adi_config
import os

def _apply_environment(env_cfg: dict) -> None:
    """Apply environment variables from config."""
    for k, v in env_cfg.items():
        os.environ[str(k)] = str(v)

def configure_logging():
    """Configure logging using values from config with Docling-style structure."""
    # Suppress Azure SDK HTTP logging for cleaner output
    import logging
    logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
    logging.getLogger("azure.core.pipeline.policies").setLevel(logging.WARNING)
    logging.getLogger("azure.identity").setLevel(logging.WARNING)
    
    log_cfg = {
        'level': 'INFO',
        'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        'file_rotation': {
            'max_bytes': 10485760,
            'backup_count': 5
        }
    }
    Logger.configure_logging(log_cfg)
    
    # Log system initialization banner like Docling
    system_logger = Logger.get_logger("System")
    system_logger.info("=" * 80)
    system_logger.info("ADI Extraction - Azure Document Intelligence PDF Processing")
    system_logger.info("=" * 80)
    Logger.log_system_info()
    system_logger.info("=" * 80)
    
    # Apply environment variables if available
    try:
        env_cfg = adi_config.get_environment_variables() if hasattr(adi_config, 'get_environment_variables') else {}
        if env_cfg:
            _apply_environment(env_cfg)
            Logger.get_logger("CLI").info("Environment variables applied", **env_cfg)
    except Exception:
        Logger.get_logger("CLI").warning("Environment config missing; using process defaults")

@exception_handler
def run_adi_mode(args):
    """Process a directory of PDFs using Azure Document Intelligence API."""
    logger = StructuredLogger("ADI")
    with ContextualErrorLogger("PDFDirectoryProcessing", mode="azure_di", pdf_dir=args.input_dir):
        try:
            if not args.input_dir:
                print("Error: --input-dir is required")
                sys.exit(1)
            
            # Validate paths
            input_path = Path(args.input_dir)
            if not input_path.exists():
                print(f"Error: Input directory does not exist: {input_path}")
                sys.exit(1)
            
            if not input_path.is_dir():
                logger.error("PDF directory not found: {}".format(input_path))
                print("Error: PDF directory not found: {}".format(input_path))
                return 1
            
            output_base = Path(args.output_dir)
            output_base.mkdir(parents=True, exist_ok=True)
            
            # Process PDFs using ADI
            process_pdf_folder(str(input_path), str(output_base))
            
            return 0
        except Exception as e:
            logger.exception("ADI processing failed: {}".format(e))
            print("ADI processing failed: {}".format(e))
            return 1

@exception_handler
def main():
    """Simplified main entry point for ADI extraction."""
    configure_logging()
    logger = Logger.get_logger("CLI")
    try:
        default_output = str(adi_config.paths.output_folder)
    except Exception:
        default_output = 'outputs'
    
    parser = argparse.ArgumentParser(description="ADI Extraction CLI")
    parser.add_argument('--input-dir', required=True, help="Directory containing PDF files to process")
    parser.add_argument('--output-dir', default=default_output, help="Base output directory (default from config)")
    args = parser.parse_args()
    logger.info("Starting ADI extraction run")
    
    return run_adi_mode(args)

if __name__ == "__main__":
    sys.exit(main())
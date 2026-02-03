"""
Configuration Loader for ADI Extraction
======================================

Handles loading and managing configuration for Azure Document Intelligence PDF extraction.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any
from dataclasses import dataclass
from dotenv import load_dotenv

@dataclass
class AzureConfig:
    """Azure Document Intelligence configuration."""
    endpoint: str
    api_key: str
    api_model: str
    mode: str

@dataclass
class PathsConfig:
    """File paths configuration."""
    input_folder: str
    output_folder: str

@dataclass
class ProcessingConfig:
    """Processing settings configuration."""
    combined_content_filename: str
    metadata_filename: str
    tables_folder_name: str
    images_folder_name: str
    save_individual_tables: bool
    table_filename_prefix: str
    table_images_folder_name: str
    extract_table_images: bool
    extract_page_images: bool
    image_scale_factor: float
    image_format: str
    page_number_format: str

@dataclass
class LoggingConfig:
    """Logging configuration."""
    show_processing_messages: bool
    show_table_save_confirmations: bool
    show_error_details: bool

class ADIConfigLoader:
    """Singleton configuration loader for ADI Extraction."""
    
    _instance = None
    _config = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ADIConfigLoader, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._config is None:
            self._load_env_variables()
            self._load_config()
    
    def _load_env_variables(self):
        """Load environment variables from .env file."""
        # Try to load .env file from the project root
        current_dir = Path(__file__).parent
        env_file = current_dir.parent / ".env"
        
        if env_file.exists():
            load_dotenv(env_file)
        else:
            # Try loading from current directory
            load_dotenv()
    
    def _get_config_dir(self) -> Path:
        """Get the configuration directory path."""
        current_dir = Path(__file__).parent
        config_dir = current_dir.parent / "config"
        
        if not config_dir.exists():
            raise FileNotFoundError(f"Configuration directory not found: {config_dir}")
        
        return config_dir
    
    def _load_yaml_file(self, filename: str) -> Dict[str, Any]:
        """Load a YAML configuration file."""
        config_dir = self._get_config_dir()
        file_path = config_dir / filename
        
        if not file_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return yaml.safe_load(file)
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML file {filename}: {e}")
    
    def _load_config(self):
        """Load configuration file."""
        try:
            self._config = self._load_yaml_file("config.yaml")
        except Exception as e:
            raise RuntimeError(f"Failed to load configuration: {e}")
    
    @property
    def azure(self) -> AzureConfig:
        """Get Azure Document Intelligence configuration."""
        config = self._config['azure']
        
        # Get sensitive values from environment variables
        endpoint = os.getenv('AZURE_ENDPOINT')
        api_key = os.getenv('AZURE_API_KEY')
        
        if not endpoint:
            raise ValueError("AZURE_ENDPOINT environment variable is required")
        if not api_key:
            raise ValueError("AZURE_API_KEY environment variable is required")
            
        return AzureConfig(
            endpoint=endpoint,
            api_key=api_key,
            api_model=config['api_model'],
            mode=config['mode']
        )
    
    @property
    def paths(self) -> PathsConfig:
        """Get paths configuration."""
        config = self._config['paths']
        return PathsConfig(
            input_folder=config['input_folder'],
            output_folder=config['output_folder']
        )
    
    @property
    def processing(self) -> ProcessingConfig:
        """Get processing configuration."""
        config = self._config['processing']
        return ProcessingConfig(
            combined_content_filename=config['combined_content_filename'],
            metadata_filename=config['metadata_filename'],
            tables_folder_name=config['tables_folder_name'],
            images_folder_name=config['images_folder_name'],
            save_individual_tables=config['save_individual_tables'],
            table_filename_prefix=config['table_filename_prefix'],
            table_images_folder_name=config['table_images_folder_name'],
            extract_table_images=config['extract_table_images'],
            extract_page_images=config['extract_page_images'],
            image_scale_factor=config['image_scale_factor'],
            image_format=config['image_format'],
            page_number_format=config['page_number_format']
        )
    
    @property
    def logging(self) -> LoggingConfig:
        """Get logging configuration."""
        config = self._config['logging']
        return LoggingConfig(
            show_processing_messages=config['show_processing_messages'],
            show_table_save_confirmations=config['show_table_save_confirmations'],
            show_error_details=config['show_error_details']
        )
    
    @property
    def encoding(self) -> str:
        """Get file encoding."""
        return self._config['encoding']
    
    def get_raw_config(self) -> Dict[str, Any]:
        """Get raw configuration dictionary."""
        return self._config
    
    def reload_config(self):
        """Reload configuration file."""
        self._config = None
        self._load_config()

# Singleton instance
adi_config = ADIConfigLoader()
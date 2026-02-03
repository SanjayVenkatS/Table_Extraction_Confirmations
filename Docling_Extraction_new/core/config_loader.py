"""
Configuration Loader for RegScan-V2
===================================

Handles loading and managing all configuration files including:
- Main system configuration (config.yaml)
- Field mappings (loaded from JSON field definitions)
"""

import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

@dataclass
class AzureOpenAIConfig:
    """Azure OpenAI configuration."""
    endpoint: str
    api_key: str
    api_version: str
    chat_deployment: str
    chat_model: str
    embedding_deployment: str
    embedding_model: str
    temperature: float = 0.1
    output_max_tokens: int = 32768
    input_token_size: int = 512000
    embedding_dimensions: int = 1536
    default_timeout_seconds: float = 86400.0

@dataclass
class VectorStoreConfig:
    """Vector store configuration."""
    provider: str
    index_type: str
    distance_metric: str
    save_dir: str
    versioning_enabled: bool = True

@dataclass
class RetrievalConfig:
    """Retrieval configuration."""
    default_strategy: str
    top_k: int
    similarity_threshold: float
    strategies: Dict[str, Dict[str, Any]]
    max_context_length: int = 3000
    default_context_length: int = 4000

class ConfigLoader:
    """Singleton configuration loader for RegScan-V2."""
    
    _instance = None
    _config = None
    _discovery_enabled = True
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigLoader, cls).__new__(cls)
        return cls._instance
    
    def __init__(self, enable_discovery: bool = True):
        self._discovery_enabled = enable_discovery
        if self._config is None:
            self._load_all_configs()
    
    def _get_config_dir(self) -> Path:
        """Get the configuration directory path."""
        # Assume config directory is relative to this file
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
    
    def _load_all_configs(self):
        """Load all configuration files (PDF-only simplified)."""
        try:
            main_config = self._load_yaml_file("config.yaml")
            field_mappings = {'field_mappings': {}, 'processing_sequence': []}
            field_instructions = {'field_instructions': {}}
            self._config = {
                'main': main_config,
                'field_mappings': field_mappings,
                'field_instructions': field_instructions
            }
        except Exception as e:
            raise RuntimeError(f"Failed to load configuration: {e}")
    
    @property
    def azure_openai(self) -> AzureOpenAIConfig:
        """Get Azure OpenAI configuration."""
        config = self._config['main']['azure_openai']
        return AzureOpenAIConfig(
            endpoint=config['endpoint'],
            api_key=config['api_key'],
            api_version=config['api_version'],
            chat_deployment=config['chat_model']['deployment_name'],
            chat_model=config['chat_model']['model_name'],
            embedding_deployment=config['embedding_model']['deployment_name'],
            embedding_model=config['embedding_model']['model_name'],
            temperature=config['chat_model']['temperature'],
            output_max_tokens=config['chat_model']['output_max_tokens'],
            input_token_size=config['chat_model']['input_token_size'],
            embedding_dimensions=config['embedding_model']['dimensions'],
            default_timeout_seconds=config['timeouts']['default_timeout_seconds'],
            query_expansion_timeout_seconds=config['timeouts']['query_expansion_timeout_seconds'],
            query_expansion_temperature=config['query_expansion']['temperature']
        )
    
    @property
    def vector_store(self) -> VectorStoreConfig:
        """Get vector store configuration."""
        config = self._config['main']['vector_store']
        return VectorStoreConfig(
            provider=config['provider'],
            index_type=config['index_type'],
            distance_metric=config['distance_metric'],
            save_dir=config['save_dir'],
            versioning_enabled=config['versioning']['enabled']
        )
    
    @property
    def retrieval(self) -> RetrievalConfig:
        """Get retrieval configuration."""
        config = self._config['main']['retrieval']
        return RetrievalConfig(
            default_strategy=config['default_strategy'],
            top_k=config['top_k'],
            similarity_threshold=config['similarity_threshold'],
            strategies=config['strategies'],
            max_context_length=config['context_limits']['max_context_length'],
            default_context_length=config['context_limits']['default_context_length']
        )
    
    @property
    def document_processing(self) -> Dict[str, Any]:
        """Get document processing configuration."""
        return self._config['main']['document_processing']
    
    @property
    def field_processing(self) -> Dict[str, Any]:
        """Get field processing configuration."""
        return self._config['main']['field_processing']
    
    @property
    def data_paths(self) -> Dict[str, Any]:
        """Get data paths configuration."""
        return self._config['main']['data_paths']
    
    @property
    def logging_config(self) -> Dict[str, Any]:
        """Get logging configuration."""
        return self._config['main']['logging']
    
    @property
    def system_config(self) -> Dict[str, Any]:
        """Get system configuration."""
        return self._config['main']['system']
    
    def get_field_mappings(self) -> Dict[str, Any]:
        """Get complete field mappings configuration."""
        return self._config['field_mappings']
    
    def get_field_instructions(self) -> Dict[str, Any]:
        """Get field instructions configuration."""
        return self._config['field_instructions']
    
    def get_fields_by_source(self, source: str) -> List[Dict[str, Any]]:
        """Get fields by source type (user_input, regulation, pro, combined, on_hold)."""
        mappings = self.get_field_mappings()
        
        if source in mappings['field_mappings']:
            return mappings['field_mappings'][source]
        else:
            return []
    
    def get_processing_sequence(self) -> List[int]:
        """Get the field processing sequence."""
        return self.get_field_mappings()['processing_sequence']
    
    def get_field_instruction(self, field_name: str) -> Optional[Dict[str, Any]]:
        """Get instruction for a specific field."""
        instructions = self.get_field_instructions()
        return instructions['field_instructions'].get(field_name)
    
    def get_default_instruction(self) -> Dict[str, Any]:
        """Get default instruction template."""
        instructions = self.get_field_instructions()
        return instructions['default_instruction']
    
    def get_output_format(self, format_name: str) -> Optional[Dict[str, Any]]:
        """Get output format specification."""
        instructions = self.get_field_instructions()
        return instructions['output_formats'].get(format_name)
    
    # Jurisdiction-related methods removed for PDF-only mode
    
    def reload_config(self, force_discovery: bool = False):
        """Reload all configuration files."""
        self._config = None
        if force_discovery:
            self._discovery_enabled = True
        self._load_all_configs()
    
    # Jurisdiction discovery and validation methods removed

# Singleton instance
config = ConfigLoader()
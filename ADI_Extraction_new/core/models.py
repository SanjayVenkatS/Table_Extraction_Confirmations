"""
Data Models for ADI Extraction
==============================

Pydantic models for type safety, validation, and data structure definition
throughout the Azure Document Intelligence PDF extraction pipeline.
"""

from pydantic import BaseModel, Field, validator
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from enum import Enum
from pathlib import Path

class ExtractionMode(str, Enum):
    """Azure Document Intelligence extraction modes."""
    MARKDOWN = "markdown"
    TEXT = "text"
    FIGURES = "figures"

class ProcessingStatus(str, Enum):
    """Processing status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

class TableFormat(str, Enum):
    """Table output format types."""
    MARKDOWN = "markdown"
    HTML = "html"
    CSV = "csv"
    JSON = "json"

class AzureConfig(BaseModel):
    """Azure Document Intelligence configuration."""
    endpoint: str = Field(..., description="Azure Document Intelligence endpoint URL")
    api_key: str = Field(..., description="Azure API key")
    api_model: str = Field(default="prebuilt-layout", description="Azure model to use")
    mode: ExtractionMode = Field(default=ExtractionMode.MARKDOWN, description="Extraction mode")
    
    @validator('endpoint')
    def validate_endpoint(cls, v):
        """Validate Azure endpoint URL."""
        if not v or not v.strip():
            raise ValueError("Azure endpoint cannot be empty")
        if not v.startswith('https://'):
            raise ValueError("Azure endpoint must be HTTPS URL")
        return v.strip()
    
    @validator('api_key')
    def validate_api_key(cls, v):
        """Validate API key."""
        if not v or not v.strip():
            raise ValueError("Azure API key cannot be empty")
        return v.strip()

class PathsConfig(BaseModel):
    """File paths configuration."""
    input_folder: Path = Field(..., description="Input folder for PDF files")
    output_folder: Path = Field(..., description="Output folder for extracted content")
    
    @validator('input_folder', 'output_folder')
    def validate_paths(cls, v):
        """Validate path exists."""
        path = Path(v)
        if not path.exists():
            raise ValueError(f"Path does not exist: {path}")
        return path

class ProcessingConfig(BaseModel):
    """Processing configuration settings."""
    file_naming: Dict[str, str] = Field(default_factory=dict, description="File naming conventions")
    table_settings: Dict[str, Any] = Field(default_factory=dict, description="Table processing settings")
    max_concurrent_requests: int = Field(default=1, ge=1, le=10, description="Max concurrent API requests")
    retry_attempts: int = Field(default=3, ge=1, le=10, description="Number of retry attempts")
    timeout_seconds: int = Field(default=300, ge=30, le=3600, description="Request timeout in seconds")

class LoggingConfig(BaseModel):
    """Logging configuration settings."""
    show_processing_steps: bool = Field(default=True, description="Show processing step messages")
    show_table_extraction: bool = Field(default=True, description="Show table extraction messages")
    show_file_operations: bool = Field(default=True, description="Show file operation messages")
    log_level: str = Field(default="INFO", description="Logging level")
    
    @validator('log_level')
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {valid_levels}")
        return v.upper()

class PDFDocument(BaseModel):
    """Information about a PDF document."""
    filename: str = Field(..., description="PDF filename")
    file_path: Path = Field(..., description="Full path to PDF file")
    file_size_bytes: int = Field(..., description="File size in bytes")
    processing_status: ProcessingStatus = Field(default=ProcessingStatus.PENDING)
    error_message: Optional[str] = Field(None, description="Error message if processing failed")
    
    @validator('filename')
    def validate_filename(cls, v):
        """Validate PDF filename."""
        if not v.endswith('.pdf'):
            raise ValueError("File must be a PDF")
        return v

class TableInfo(BaseModel):
    """Information about extracted table."""
    table_index: int = Field(..., description="Table index in document")
    filename: str = Field(..., description="Generated table filename")
    format: TableFormat = Field(..., description="Table output format")
    rows: int = Field(default=0, description="Number of rows")
    columns: int = Field(default=0, description="Number of columns")
    file_size_bytes: int = Field(default=0, description="Table file size")
    extraction_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence score")

class ExtractionResult(BaseModel):
    """Result of PDF extraction process."""
    pdf_document: PDFDocument
    processing_start_time: datetime = Field(default_factory=datetime.now)
    processing_end_time: Optional[datetime] = Field(None)
    processing_duration_seconds: float = Field(default=0.0)
    pages_processed: int = Field(default=0)
    tables_extracted: List[TableInfo] = Field(default_factory=list)
    output_folder: Path = Field(..., description="Output folder for this document")
    metadata_file: Optional[Path] = Field(None, description="Path to metadata JSON file")
    combined_content_file: Optional[Path] = Field(None, description="Path to combined content file")
    success: bool = Field(default=False)
    
    @property
    def total_tables(self) -> int:
        """Get total number of tables extracted."""
        return len(self.tables_extracted)
    
    @property
    def extraction_summary(self) -> Dict[str, Any]:
        """Get extraction summary."""
        return {
            "pdf_filename": self.pdf_document.filename,
            "processing_duration": round(self.processing_duration_seconds, 2),
            "pages_processed": self.pages_processed,
            "total_tables": self.total_tables,
            "success": self.success
        }

class BatchProcessingRequest(BaseModel):
    """Request for batch processing multiple PDF files."""
    input_folder: Path = Field(..., description="Folder containing PDF files")
    output_folder: Path = Field(..., description="Output folder for results")
    azure_config: AzureConfig = Field(..., description="Azure configuration")
    processing_config: ProcessingConfig = Field(..., description="Processing configuration")
    logging_config: LoggingConfig = Field(..., description="Logging configuration")
    pdf_files: List[str] = Field(default_factory=list, description="Specific PDF files to process")

class BatchProcessingResult(BaseModel):
    """Result of batch processing multiple PDF files."""
    total_files: int = Field(..., description="Total number of PDF files processed")
    successful_files: List[str] = Field(default_factory=list)
    failed_files: List[str] = Field(default_factory=list)
    extraction_results: List[ExtractionResult] = Field(default_factory=list)
    batch_start_time: datetime = Field(default_factory=datetime.now)
    batch_end_time: Optional[datetime] = Field(None)
    total_processing_duration_seconds: float = Field(default=0.0)
    total_tables_extracted: int = Field(default=0)
    total_pages_processed: int = Field(default=0)
    errors: List[str] = Field(default_factory=list)
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_files == 0:
            return 0.0
        return round((len(self.successful_files) / self.total_files) * 100, 2)
    
    @property
    def processing_summary(self) -> Dict[str, Any]:
        """Get processing summary."""
        return {
            "total_files": self.total_files,
            "successful_files": len(self.successful_files),
            "failed_files": len(self.failed_files),
            "success_rate": self.success_rate,
            "total_processing_duration": round(self.total_processing_duration_seconds, 2),
            "total_tables_extracted": self.total_tables_extracted,
            "total_pages_processed": self.total_pages_processed
        }

class AzureAPIMetrics(BaseModel):
    """Metrics for Azure Document Intelligence API usage."""
    total_requests: int = Field(default=0, description="Total API requests made")
    successful_requests: int = Field(default=0, description="Successful API requests")
    failed_requests: int = Field(default=0, description="Failed API requests")
    total_pages_analyzed: int = Field(default=0, description="Total pages analyzed by API")
    total_api_time_seconds: float = Field(default=0.0, description="Total time spent in API calls")
    average_request_time_seconds: float = Field(default=0.0, description="Average request time")
    quota_usage_percentage: float = Field(default=0.0, ge=0.0, le=100.0, description="API quota usage")
    
    @property
    def success_rate(self) -> float:
        """Calculate API success rate."""
        if self.total_requests == 0:
            return 0.0
        return round((self.successful_requests / self.total_requests) * 100, 2)

class ExtractionMetadata(BaseModel):
    """Metadata for extraction process."""
    extraction_timestamp: datetime = Field(default_factory=datetime.now)
    azure_config: AzureConfig = Field(..., description="Azure configuration used")
    processing_config: ProcessingConfig = Field(..., description="Processing configuration used")
    system_info: Dict[str, str] = Field(default_factory=dict, description="System information")
    api_metrics: AzureAPIMetrics = Field(default_factory=AzureAPIMetrics)
    version: str = Field(default="1.0.0", description="ADI Extraction version")

class QualityReport(BaseModel):
    """Comprehensive quality report for batch processing."""
    batch_processing_result: BatchProcessingResult
    extraction_metadata: ExtractionMetadata
    detailed_results: List[ExtractionResult]
    quality_metrics: Dict[str, Any] = Field(default_factory=dict)
    recommendations: List[str] = Field(default_factory=list)
    report_generated_at: datetime = Field(default_factory=datetime.now)
    
    @property
    def overall_quality_score(self) -> float:
        """Calculate overall quality score based on success rates and processing metrics."""
        if not self.batch_processing_result.total_files:
            return 0.0
        
        # Base score from success rate
        success_score = self.batch_processing_result.success_rate
        
        # Bonus for table extraction
        if self.batch_processing_result.total_tables_extracted > 0:
            success_score = min(success_score + 5, 100)
        
        # Penalty for errors
        if self.batch_processing_result.errors:
            success_score = max(success_score - len(self.batch_processing_result.errors), 0)
        
        return round(success_score, 2)
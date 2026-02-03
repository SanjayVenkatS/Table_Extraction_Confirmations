"""
Data Models for RegScan-V2
==========================

Pydantic models for type safety, validation, and data structure definition
throughout the RegScan-V2 multi-document extraction pipeline.
"""

from pydantic import BaseModel, Field, validator
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from enum import Enum
from pathlib import Path

class SourceType(str, Enum):
    """Enumeration of data sources."""
    USER_INPUT = "user_input"
    REGULATION = "regulation"
    PRO = "pro"
    COMBINED = "combined"
    ON_HOLD = "on_hold"

class ProcessingStatus(str, Enum):
    """Processing status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

class SplitterType(str, Enum):
    """Document splitter types."""
    SEMANTIC = "semantic"
    PARAGRAPH = "paragraph"
    SECTION = "section"

class RetrieverType(str, Enum):
    """Retriever strategy types."""
    SIMPLE = "simple"
    HYBRID = "hybrid"
    RERANKER = "reranker"
    QUERY_EXPANSION = "query_expansion"

class UserInput(BaseModel):
    """User-provided static input fields."""
    jurisdiction: str = Field(..., description="Jurisdiction name")
    geographical_scope: str = Field(..., description="Geographical scope")
    adoption_status: str = Field(..., description="Adoption status")
    date_of_adoption: str = Field(..., description="Date of adoption")
    date_entry_into_force: str = Field(..., description="Date entry into force")
    review_date: Optional[str] = Field(None, description="Review date if available")
    
    @validator('jurisdiction')
    def validate_jurisdiction(cls, v):
        """Validate jurisdiction name."""
        if not v or not v.strip():
            raise ValueError("Jurisdiction cannot be empty")
        return v.strip()

class FieldMapping(BaseModel):
    """Field mapping configuration."""
    field_id: int = Field(..., description="Sequential field ID")
    column_name: str = Field(..., description="Column name in output CSV")
    source: SourceType = Field(..., description="Data source type")
    required: bool = Field(default=True, description="Whether field is required")
    default_value: Optional[str] = Field(None, description="Default value for on-hold fields")

class FieldInstruction(BaseModel):
    """Custom instruction for field extraction."""
    instruction: str = Field(..., description="Detailed extraction instruction")
    expected_format: str = Field(..., description="Expected output format")
    search_terms: List[str] = Field(default_factory=list, description="Keywords for searching")

class ExtractionContext(BaseModel):
    """Context for field extraction."""
    field_mapping: FieldMapping
    custom_instruction: Optional[FieldInstruction] = None
    vector_stores: List[str] = Field(default_factory=list, description="Vector stores to search")
    retrieval_strategy: RetrieverType = Field(default=RetrieverType.HYBRID)

class ExtractionResult(BaseModel):
    """Result of field extraction."""
    field_id: int
    field_name: str
    extracted_value: str
    confidence_score: float = Field(ge=0.0, le=1.0, description="Confidence score 0-1")
    source_documents: List[str] = Field(default_factory=list, description="Source document references")
    processing_time_seconds: float = Field(default=0.0, description="Processing time")
    used_custom_instruction: bool = Field(default=False, description="Whether custom instruction was used")
    retrieval_method: str = Field(default="unknown", description="Retrieval method used")
    error_message: Optional[str] = Field(None, description="Error message if extraction failed")

class DocumentInfo(BaseModel):
    """Information about processed documents."""
    file_path: Path
    document_type: str  # 'regulation' or 'pro'
    file_size_bytes: int
    page_count: Optional[int] = None
    processing_time_seconds: float = 0.0
    chunk_count: int = 0
    embeddings_generated: bool = False
    extraction_method: str = Field(default="unknown", description="PDF extraction method used")

class ProcessingConfig(BaseModel):
    """Configuration for processing pipeline."""
    jurisdiction: str
    user_input: UserInput
    splitter_type: SplitterType = Field(default=SplitterType.SEMANTIC)
    retrieval_strategy: RetrieverType = Field(default=RetrieverType.HYBRID)
    top_k: int = Field(default=5, ge=1, le=20)
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    chunk_size: int = Field(default=1000, ge=100, le=4000)
    chunk_overlap: int = Field(default=200, ge=0, le=500)
    enable_custom_instructions: bool = Field(default=True)
    enable_search_terms: bool = Field(default=False)
    enable_dependency_context: bool = Field(default=False)
    parallel_processing: bool = Field(default=False)

class VectorStoreInfo(BaseModel):
    """Information about vector stores."""
    store_name: str
    document_type: str  # 'regulation' or 'pro'
    index_path: Path
    document_count: int = 0
    embedding_dimensions: int = 1536
    created_at: datetime = Field(default_factory=datetime.now)
    last_updated: datetime = Field(default_factory=datetime.now)
    version: str = Field(default="v1")

class QualityMetrics(BaseModel):
    """Quality metrics for extraction."""
    total_fields: int
    extracted_fields: int
    failed_fields: int
    on_hold_fields: int
    average_confidence: float = Field(ge=0.0, le=1.0)
    fields_with_custom_instructions: int = 0
    total_processing_time_seconds: float = 0.0

class QualityReport(BaseModel):
    """Comprehensive quality report."""
    jurisdiction: str
    processing_timestamp: datetime = Field(default_factory=datetime.now)
    user_input: UserInput
    processing_config: ProcessingConfig
    document_info: List[DocumentInfo]
    vector_store_info: List[VectorStoreInfo]
    extraction_results: List[ExtractionResult]
    quality_metrics: QualityMetrics
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

class CSVOutputRow(BaseModel):
    """Complete CSV output row with all 56 fields."""
    # User Input Fields (6)
    jurisdiction: str
    geographical_scope: str
    name_of_legislation: str
    implementing_authority: str
    adoption_status: str
    date_of_adoption: str
    date_entry_into_force: str
    review_date: Optional[str] = "Not specified"
    
    # Regulation Document Fields (39)
    summary_description: str = "Not found"
    implementation_timeline: str = "Not found"
    scope: str = "Not found"
    scope_covered_materials: str = "Not found"
    in_scope_transactions: str = "Not found"
    producer_definition: str = "Not found"
    exemptions: str = "Not found"
    extended_producer_responsibility: str = "Not found"
    epr_summary_description: str = "Not found"
    thresholds_epr_obligations: str = "Not found"
    reporting_filing_requirements: str = "Not found"
    first_reporting_cycle: str = "Not found"
    reporting_timing: str = "Not found"
    other_financial_instruments: str = "Not found"
    financial_summary_description: str = "Not found"
    financial_timeline: str = "Not found"
    non_compliance_penalties: str = "Not found"
    penalties_summary_description: str = "Not found"
    bans_restrictions_phase_outs: str = "Not found"
    products_materials_impacted: str = "Not found"
    bans_summary_description: str = "Not found"
    bans_timeline: str = "Not found"
    recycled_content_mandates: str = "Not found"
    recycled_summary_description: str = "Not found"
    recycled_timeline: str = "Not found"
    other_design_requirements: str = "Not found"
    design_summary_description: str = "Not found"
    labelling_certification_requirements: str = "Not found"
    labelling_summary_description: str = "Not found"
    consumer_information: str = "Not found"
    consumer_summary_description: str = "Not found"
    waste_management_recycling: str = "Not found"
    waste_summary_description: str = "Not found"
    additional_sources: str = "Not found"
    
    # PRO Document Fields (3)
    designated_pro: str = "Not found"
    pro_contact_information: str = "Not found"
    registration: str = "Not found"
    
    # Combined Document Fields (7)
    fees_and_rates: str = "Not found"
    date_first_year_payment: str = "Not found"
    payment_timing: str = "Not found"
    entity_responsible_collecting: str = "Not found"
    taxes: str = "Not found"
    taxes_summary_description: str = "Not found"
    thresholds_tax_obligations: str = "Not found"
    
    # On Hold Fields (3)
    registration_reporting_requirements: str = "On-HOLD"
    fees_rates_on_hold: str = "On-HOLD"
    timeline_on_hold: str = "On-HOLD"

class BatchProcessingRequest(BaseModel):
    """Request for batch processing multiple jurisdictions."""
    jurisdictions: List[str]
    user_inputs: Dict[str, UserInput]  # jurisdiction -> user_input
    processing_config: ProcessingConfig
    output_directory: Path
    parallel_processing: bool = Field(default=False)

class BatchProcessingResult(BaseModel):
    """Result of batch processing."""
    total_jurisdictions: int
    successful_jurisdictions: List[str]
    failed_jurisdictions: List[str]
    quality_reports: Dict[str, QualityReport]  # jurisdiction -> quality_report
    combined_csv_path: Optional[Path] = None
    individual_csv_paths: Dict[str, Path] = Field(default_factory=dict)
    total_processing_time_seconds: float = 0.0
    errors: List[str] = Field(default_factory=list)
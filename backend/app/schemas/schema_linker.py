"""Pydantic v2 Validation Schemas for Schema Linking & Join Graph API Endpoints.

QueryMind AI 2.0 - Phase 4: Schema Linking & Join Graph Construction.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ColumnMetadataSchema(BaseModel):
    """Pydantic schema representing column catalog metadata."""
    name: str = Field(..., description="Column name in SQLite table")
    table_name: str = Field(..., description="Parent table name")
    data_type: str = Field(..., description="SQL data type (INTEGER, VARCHAR, FLOAT, DATE)")
    nullable: bool = Field(..., description="Whether column accepts NULL values")
    is_primary_key: bool = Field(..., description="True if column is part of Primary Key")
    is_foreign_key: bool = Field(..., description="True if column has Foreign Key constraint")
    foreign_key_target: Optional[str] = Field(None, description="Target table.column if foreign key")
    description: str = Field(..., description="Academic attribute domain description")
    synonyms: List[str] = Field(default_factory=list, description="Common academic synonyms and aliases")


class TableMetadataSchema(BaseModel):
    """Pydantic schema representing table catalog metadata."""
    name: str = Field(..., description="Canonical table name in SQLite schema")
    entity_name: str = Field(..., description="Domain entity class name (e.g., Department, Student)")
    description: str = Field(..., description="Academic entity role and description")
    primary_keys: List[str] = Field(..., description="List of primary key column names")
    foreign_keys: List[Dict[str, Any]] = Field(..., description="Foreign key constraint specifications")
    unique_constraints: List[Dict[str, Any]] = Field(..., description="Unique constraint definitions")
    columns: Dict[str, ColumnMetadataSchema] = Field(..., description="Dictionary of column metadata")
    synonyms: List[str] = Field(default_factory=list, description="Domain aliases for table entity")


class SchemaCatalogResponse(BaseModel):
    """Response payload for full schema catalog inspection."""
    status: str = Field("success", description="Response status indicator")
    total_tables: int = Field(..., description="Total number of academic tables introspected (9)")
    total_columns: int = Field(..., description="Total number of introspected columns across tables")
    tables: Dict[str, TableMetadataSchema] = Field(..., description="Map of table name to table metadata")


class JoinPathStepSchema(BaseModel):
    """Represents a single directional join edge in a multi-table path."""
    from_table: str = Field(..., description="Source table being joined")
    to_table: str = Field(..., description="Target table being joined")
    join_type: str = Field("INNER JOIN", description="SQL Join type (INNER JOIN or LEFT JOIN)")
    condition: str = Field(..., description="ON clause join equality condition")
    direction: str = Field(..., description="Relationship direction (MANY_TO_ONE or ONE_TO_MANY)")


class JoinPathRequest(BaseModel):
    """Request payload for join path resolution between tables."""
    tables: List[str] = Field(..., min_length=1, description="List of table names required in join path")
    preferred_anchor: Optional[str] = Field(None, description="Optional preferred starting root table")


class JoinPathResponse(BaseModel):
    """Response payload containing resolved join path information."""
    status: str = Field("success", description="Resolution status")
    is_connected: bool = Field(..., description="True if a valid foreign key path connects all tables")
    anchor_table: Optional[str] = Field(None, description="Starting anchor table for join sequence")
    joined_tables: List[str] = Field(default_factory=list, description="Ordered sequence of joined tables")
    total_hops: int = Field(..., description="Total number of foreign key hops in the path")
    join_steps: List[JoinPathStepSchema] = Field(default_factory=list, description="Ordered join statements")
    alternative_paths_count: int = Field(0, description="Count of alternative shortest paths if ambiguous")
    alternative_paths: List[List[JoinPathStepSchema]] = Field(default_factory=list, description="Candidate alternative join paths of equal minimum length")
    error: Optional[str] = Field(None, description="Error message if tables are disconnected or unknown")


class LinkedColumnMatch(BaseModel):
    """Single column match for an entity."""
    column_name: str = Field(..., description="Resolved column name")
    matched_token: str = Field(..., description="Token or phrase from query triggering match")
    confidence: float = Field(..., description="Confidence score of attribute match (0.0 to 1.0)")
    match_type: str = Field(..., description="Match category (EXACT, SYNONYM_MATCH, CONTEXT_RESOLVED)")


class LinkedValueMatch(BaseModel):
    """Literal academic domain value resolved from query."""
    matched_token: str = Field(..., description="Query token matching value")
    table_name: str = Field(..., description="Target table containing value")
    column_name: str = Field(..., description="Target column containing value")
    value: Any = Field(..., description="Normalized target value for SQL filter")
    confidence: float = Field(..., description="Confidence score")


class CandidateColumnRef(BaseModel):
    """Potential column candidate for an ambiguous query term."""
    table: str = Field(..., description="Candidate table name")
    column: str = Field(..., description="Candidate column name")
    description: Optional[str] = Field(None, description="Candidate attribute description")


class AmbiguousCandidateSchema(BaseModel):
    """Structure explaining ambiguous schema matches requiring disambiguation."""
    token: str = Field(..., description="Ambiguous query token")
    candidates: List[CandidateColumnRef] = Field(..., description="Alternative plausible candidates")
    message: str = Field(..., description="Explanation of ambiguity")


class SchemaLinkRequest(BaseModel):
    """Request payload for linking natural language queries to schema."""
    query: str = Field(..., min_length=1, max_length=500, description="Natural language academic query")


class SchemaLinkResponse(BaseModel):
    """Structured response payload for schema linking and join path resolution."""
    status: str = Field("success", description="Execution status indicator")
    query: str = Field(..., description="Original input query processed")
    linked_tables: List[str] = Field(..., description="List of canonical tables referenced")
    linked_columns: Dict[str, List[LinkedColumnMatch]] = Field(..., description="Columns linked by table")
    linked_values: List[LinkedValueMatch] = Field(..., description="Extracted domain filter values")
    unsupported_entities: List[str] = Field(default_factory=list, description="Out-of-catalog entities detected")
    is_ambiguous: bool = Field(..., description="True if schema references are ambiguous or unsupported")
    ambiguity_reason: Optional[str] = Field(None, description="Reason code: MULTIPLE_COLUMN_CANDIDATES, UNSUPPORTED_ENTITIES, etc.")
    ambiguous_candidates: List[AmbiguousCandidateSchema] = Field(default_factory=list, description="Details of ambiguous terms")
    join_path: JoinPathResponse = Field(..., description="Calculated join path across linked tables")
    execution_time_ms: float = Field(..., description="Processing latency in milliseconds")


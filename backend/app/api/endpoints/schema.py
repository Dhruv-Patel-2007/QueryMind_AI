"""FastAPI Route Endpoints for Schema Catalog, Schema Linking, and Join Graph.

QueryMind AI 2.0 - Phase 4: Schema Linking & Join Graph Construction.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.schema_linker import (
    ColumnMetadataSchema,
    JoinPathRequest,
    JoinPathResponse,
    JoinPathStepSchema,
    SchemaCatalogResponse,
    SchemaLinkRequest,
    SchemaLinkResponse,
    TableMetadataSchema,
)
from app.services.schema_linker import get_join_graph, get_schema_catalog, get_schema_linker

router = APIRouter()


@router.get(
    "/catalog",
    response_model=SchemaCatalogResponse,
    summary="Inspect Dynamic Academic Schema Catalog",
    description="Returns introspected metadata for all 9 academic tables, including primary keys, foreign keys, unique constraints, and domain synonyms.",
)
def get_catalog_endpoint() -> SchemaCatalogResponse:
    """Returns the complete introspected schema catalog with domain aliases and column specifications."""
    catalog = get_schema_catalog()

    tables_payload = {}
    total_columns = 0

    for t_name, table in catalog.tables.items():
        columns_payload = {}
        for c_name, col in table.columns.items():
            total_columns += 1
            columns_payload[c_name] = ColumnMetadataSchema(
                name=col.name,
                table_name=col.table_name,
                data_type=col.data_type,
                nullable=col.nullable,
                is_primary_key=col.is_primary_key,
                is_foreign_key=col.is_foreign_key,
                foreign_key_target=col.foreign_key_target,
                description=col.description,
                synonyms=col.synonyms,
            )

        tables_payload[t_name] = TableMetadataSchema(
            name=table.name,
            entity_name=table.entity_name,
            description=table.description,
            primary_keys=table.primary_keys,
            foreign_keys=table.foreign_keys,
            unique_constraints=table.unique_constraints,
            columns=columns_payload,
            synonyms=table.synonyms,
        )

    return SchemaCatalogResponse(
        status="success",
        total_tables=len(tables_payload),
        total_columns=total_columns,
        tables=tables_payload,
    )


@router.post(
    "/link",
    response_model=SchemaLinkResponse,
    summary="Link Query to Schema Entities, Columns & Values",
    description="Resolves natural language entities and attributes to SQLite tables and columns, evaluates ambiguity, detects unsupported terms, and resolves the join path.",
)
def link_query_endpoint(request: SchemaLinkRequest) -> SchemaLinkResponse:
    """Performs semantic schema linking, ambiguity evaluation, and join path resolution for a user query."""
    clean_query = request.query.strip()
    if not clean_query:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Query string cannot be empty or whitespace only.",
        )

    linker = get_schema_linker()
    res = linker.link_query(clean_query)

    return SchemaLinkResponse(
        status="success",
        query=res["query"],
        linked_tables=res["linked_tables"],
        linked_columns=res["linked_columns"],
        linked_values=res["linked_values"],
        unsupported_entities=res["unsupported_entities"],
        is_ambiguous=res["is_ambiguous"],
        ambiguity_reason=res["ambiguity_reason"],
        ambiguous_candidates=res["ambiguous_candidates"],
        join_path=JoinPathResponse(
            status="success" if res["join_path"]["is_connected"] else "error",
            is_connected=res["join_path"]["is_connected"],
            anchor_table=res["join_path"]["anchor_table"],
            joined_tables=res["join_path"]["joined_tables"],
            total_hops=res["join_path"]["total_hops"],
            join_steps=[
                JoinPathStepSchema(
                    from_table=s["from_table"],
                    to_table=s["to_table"],
                    join_type=s["join_type"],
                    condition=s["condition"],
                    direction=s["direction"],
                )
                for s in res["join_path"]["join_steps"]
            ],
            alternative_paths_count=res["join_path"]["alternative_paths_count"],
            alternative_paths=[
                [
                    JoinPathStepSchema(
                        from_table=s["from_table"],
                        to_table=s["to_table"],
                        join_type=s["join_type"],
                        condition=s["condition"],
                        direction=s["direction"],
                    )
                    for s in alt_p
                ]
                for alt_p in res["join_path"].get("alternative_paths", [])
            ],
            error=res["join_path"]["error"],
        ),
        execution_time_ms=res["execution_time_ms"],
    )


@router.post(
    "/join-path",
    response_model=JoinPathResponse,
    summary="Resolve Multi-Table Join Path",
    description="Determines the minimal connecting foreign-key join path across a given set of tables using shortest-path Steiner graph traversal.",
)
def resolve_join_path_post(request: JoinPathRequest) -> JoinPathResponse:
    """Calculates the minimal join sequence across requested tables."""
    graph = get_join_graph()
    target_tables = set(t.lower().strip() for t in request.tables if t.strip())

    if not target_tables:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one valid table name must be supplied.",
        )

    res = graph.resolve_multi_table_join(target_tables, preferred_anchor=request.preferred_anchor)

    return JoinPathResponse(
        status="success" if res.is_connected else "error",
        is_connected=res.is_connected,
        anchor_table=res.anchor_table,
        joined_tables=res.joined_tables,
        total_hops=res.total_hops,
        join_steps=[
            JoinPathStepSchema(
                from_table=step.from_table,
                to_table=step.to_table,
                join_type=step.join_type,
                condition=step.condition,
                direction=step.direction,
            )
            for step in res.join_steps
        ],
        alternative_paths_count=len(res.alternative_paths),
        alternative_paths=[
            [
                JoinPathStepSchema(
                    from_table=step.from_table,
                    to_table=step.to_table,
                    join_type=step.join_type,
                    condition=step.condition,
                    direction=step.direction,
                )
                for step in alt_edges
            ]
            for alt_edges in res.alternative_paths
        ],
        error=res.error,
    )


@router.get(
    "/join-path",
    response_model=JoinPathResponse,
    summary="Resolve Join Path via Query Parameter",
    description="Convenience GET endpoint resolving join paths for comma-separated table names (e.g. ?tables=departments,students).",
)
def resolve_join_path_get(
    tables: str = Query(..., description="Comma-separated table names, e.g. departments,students"),
    anchor: Optional[str] = Query(None, description="Optional preferred anchor table"),
) -> JoinPathResponse:
    """GET endpoint parsing comma-separated table names and computing the join path."""
    table_list = [t.strip() for t in tables.split(",") if t.strip()]
    if not table_list:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Parameter 'tables' must contain at least one non-empty table name.",
        )

    req = JoinPathRequest(tables=table_list, preferred_anchor=anchor)
    return resolve_join_path_post(req)


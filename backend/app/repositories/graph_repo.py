"""Repository for the workspace knowledge graph (V2 plan §4.2).

Graph traversal stays in SQL — BFS over ``graph_edges`` with bounded depth.
Entity identity within a workspace is (kind, lower(name)); duplicate edge
observations either dedupe (same source) or bump ``weight`` (new source).
"""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.graph import GraphEntityORM, GraphEdgeORM


class GraphRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _ws_clause(workspace_id: Optional[str]):
        if workspace_id is None:
            return GraphEntityORM.workspace_id.is_(None)
        return GraphEntityORM.workspace_id == workspace_id

    async def upsert_entity(
        self,
        workspace_id: Optional[str],
        kind: str,
        name: str,
        summary: Optional[str] = None,
        source_type: Optional[str] = None,
        source_id: Optional[str] = None,
    ) -> GraphEntityORM:
        """Create-or-update an entity keyed on (workspace, kind, name).

        Name matching is case-insensitive so "Alice" and "alice" stay one
        node. Existing rows get their ``updated_at`` bumped and ``summary``/
        source pointers refreshed to the latest observation.
        """
        name = name.strip()[:255]
        result = await self.db.execute(
            select(GraphEntityORM).where(
                self._ws_clause(workspace_id),
                GraphEntityORM.kind == kind,
                func.lower(GraphEntityORM.name) == name.lower(),
            )
        )
        entity = result.scalars().first()
        if entity:
            if summary:
                entity.summary = summary
            if source_type:
                entity.source_type = source_type
            if source_id:
                entity.source_id = source_id
            entity.updated_at = func.now()
            await self.db.commit()
            await self.db.refresh(entity)
            return entity

        entity = GraphEntityORM(
            workspace_id=workspace_id,
            kind=kind,
            name=name,
            summary=summary,
            source_type=source_type,
            source_id=source_id,
        )
        self.db.add(entity)
        await self.db.commit()
        await self.db.refresh(entity)
        return entity

    async def add_edge(
        self,
        workspace_id: Optional[str],
        src_id: str,
        dst_id: str,
        relation: str,
        source_id: Optional[str] = None,
    ) -> GraphEdgeORM:
        """Add or reinforce an edge.

        One row per (src, dst, relation). An identical observation — same
        ``source_id`` too — is deduped (no-op); the same relation observed
        from a *new* source increments ``weight``.
        """
        result = await self.db.execute(
            select(GraphEdgeORM).where(
                GraphEdgeORM.src_id == src_id,
                GraphEdgeORM.dst_id == dst_id,
                GraphEdgeORM.relation == relation,
            )
        )
        edge = result.scalars().first()
        if edge:
            if edge.source_id == source_id:
                return edge  # identical (src, dst, relation, source_id) — dedupe
            edge.weight += 1
            if source_id:
                edge.source_id = source_id
            await self.db.commit()
            await self.db.refresh(edge)
            return edge

        edge = GraphEdgeORM(
            workspace_id=workspace_id,
            src_id=src_id,
            dst_id=dst_id,
            relation=relation,
            weight=1,
            source_id=source_id,
        )
        self.db.add(edge)
        await self.db.commit()
        await self.db.refresh(edge)
        return edge

    async def neighbors(self, entity_id: str, depth: int = 1) -> dict:
        """BFS out to ``depth`` hops. Returns {"entities": [...], "edges": [...]}
        (the seed entity itself is excluded from "entities")."""
        seen = {entity_id}
        frontier = {entity_id}
        edges_acc: dict[str, GraphEdgeORM] = {}
        for _ in range(max(1, depth)):
            if not frontier:
                break
            result = await self.db.execute(
                select(GraphEdgeORM).where(
                    or_(
                        GraphEdgeORM.src_id.in_(frontier),
                        GraphEdgeORM.dst_id.in_(frontier),
                    )
                )
            )
            next_frontier: set[str] = set()
            for edge in result.scalars().all():
                edges_acc[edge.id] = edge
                for node_id in (edge.src_id, edge.dst_id):
                    if node_id not in seen:
                        seen.add(node_id)
                        next_frontier.add(node_id)
            frontier = next_frontier

        entities: List[GraphEntityORM] = []
        other_ids = seen - {entity_id}
        if other_ids:
            result = await self.db.execute(
                select(GraphEntityORM).where(GraphEntityORM.id.in_(other_ids))
            )
            entities = list(result.scalars().all())
        return {"entities": entities, "edges": list(edges_acc.values())}

    async def search_entities(
        self,
        workspace_id: Optional[str],
        query: str,
        kinds: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[GraphEntityORM]:
        stmt = select(GraphEntityORM).where(self._ws_clause(workspace_id))
        if query:
            stmt = stmt.where(GraphEntityORM.name.ilike(f"%{query}%"))
        if kinds:
            stmt = stmt.where(GraphEntityORM.kind.in_(kinds))
        stmt = stmt.order_by(GraphEntityORM.updated_at.desc()).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def entities_for_source(
        self, source_type: str, source_id: str
    ) -> List[GraphEntityORM]:
        result = await self.db.execute(
            select(GraphEntityORM).where(
                GraphEntityORM.source_type == source_type,
                GraphEntityORM.source_id == source_id,
            )
        )
        return list(result.scalars().all())

    async def recent_activity(
        self,
        workspace_id: Optional[str],
        since: Optional[datetime] = None,
        limit: int = 50,
    ) -> dict:
        """Recently updated entities + the edges touching them.

        Powers "catch me up": the graph-delta since the caller's last visit.
        """
        stmt = select(GraphEntityORM).where(self._ws_clause(workspace_id))
        if since is not None:
            stmt = stmt.where(GraphEntityORM.updated_at >= since)
        stmt = stmt.order_by(GraphEntityORM.updated_at.desc()).limit(limit)
        result = await self.db.execute(stmt)
        entities = list(result.scalars().all())

        edges: List[GraphEdgeORM] = []
        ids = [e.id for e in entities]
        if ids:
            result = await self.db.execute(
                select(GraphEdgeORM).where(
                    or_(GraphEdgeORM.src_id.in_(ids), GraphEdgeORM.dst_id.in_(ids))
                )
            )
            edges = list(result.scalars().all())
        return {"entities": entities, "edges": edges}

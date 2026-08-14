from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.content import RelationshipType


class ConceptSummary(BaseModel):
    slug: str
    name: str


class TopicSummary(BaseModel):
    slug: str
    name: str
    concepts: list[ConceptSummary]


class DomainSummary(BaseModel):
    slug: str
    name: str
    topics: list[TopicSummary]


class LessonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    concepto: str | None = None
    como_funciona: str | None = None
    por_que_importa: str | None = None
    visualizacion: str | None = None
    ejemplo: str | None = None
    comandos: str | None = None
    errores_frecuentes: str | None = None
    regla_mental: str | None = None
    perspectiva_ofensiva: str | None = None
    perspectiva_defensiva: str | None = None


class ConceptRelationships(BaseModel):
    prerequisites: list[ConceptSummary]
    related: list[ConceptSummary]
    continues_with: list[ConceptSummary]


class ConceptDetail(BaseModel):
    slug: str
    name: str
    lesson: LessonOut | None
    relationships: ConceptRelationships


class GraphNode(BaseModel):
    slug: str
    name: str
    domain_slug: str
    topic_slug: str
    mastery_score: float
    studied: bool
    next_due_at: datetime | None


class GraphEdge(BaseModel):
    source_slug: str
    target_slug: str
    type: RelationshipType


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]

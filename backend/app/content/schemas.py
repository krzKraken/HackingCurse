from pydantic import BaseModel, ConfigDict


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

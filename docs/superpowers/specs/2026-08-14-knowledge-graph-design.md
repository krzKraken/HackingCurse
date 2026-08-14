# Fase 2: Knowledge Graph Navegable — Diseño

> Master prompt: knowledge graph navegable, vista visual interactiva de las
> relaciones entre conceptos (hoy solo existe como lista jerárquica de texto
> dentro de cada lección, vía `ConceptRelationship`).

## Objetivo

Dar una vista visual e interactiva de todos los concepts y sus relaciones
(`prerequisite`, `related`, `continues_with`), que sirva a la vez para:

1. **Navegación/contexto** — entender cómo se conectan los temas y saltar a
   una lección directo desde el grafo.
2. **Diagnóstico de progreso** — ver de un vistazo, por color de nodo, dónde
   hay huecos de `mastery_score`.

## Decisiones de diseño (confirmadas con el usuario)

1. **Ambos objetivos con el mismo peso** en una sola vista (no dos vistas
   separadas para navegación vs. progreso).
2. **Ubicación: página propia `/graph` + preview en el Dashboard.** El
   Dashboard reemplaza el placeholder "Knowledge Connectivity" por una
   versión reducida del mismo componente (sin filtros/búsqueda), con link
   "Ver grafo completo" hacia `/graph`.
3. **Layout: force-directed (auto-layout), no jerárquico.** Los nodos se
   acomodan solos según sus conexiones (arrastrable, zoom/pan libre). Se
   prefiere sobre un layout tipo dagre porque `related` no es una relación
   jerárquica y mezclarla con `prerequisite`/`continues_with` en niveles fijos
   sería confuso.
4. **Nodos: solo `Concept`.** `Domain`/`Topic` no son nodos propios — se usan
   como color/agrupación visual y como filtro lateral (checkboxes por
   dominio). Evita un grafo con tres tipos de nodo y dos tipos de conexión
   (pertenencia vs. relación) mezclados.
5. **Interacciones v1:** zoom/pan (nativo de la librería), click en nodo →
   navega a `/lessons/:slug`, filtro por dominio (checkboxes), buscador que
   centra/resalta un nodo por nombre, tooltip on-hover con
   nombre/mastery/próximo repaso.

## Backend

### Schemas (`backend/app/content/schemas.py`)

```python
class GraphNode(BaseModel):
    slug: str
    name: str
    domain_slug: str
    topic_slug: str
    mastery_score: float  # 0.0 si no estudiado
    studied: bool
    next_due_at: datetime | None

class GraphEdge(BaseModel):
    source_slug: str
    target_slug: str
    type: RelationshipType

class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
```

### Servicio (`backend/app/content/service.py`)

`get_knowledge_graph(db, user_id) -> GraphResponse`:

- Query de `Concept` con `join(Topic).join(Domain)` +
  `outerjoin(ConceptMastery, y ConceptMastery.user_id == user_id)` +
  `outerjoin(ReviewSchedule)` — un solo query, sin N+1. `studied` es
  `ConceptMastery` no nulo; `mastery_score` es `0.0` si no hay fila.
- Query separada de todas las `ConceptRelationship` (no depende de usuario),
  mapeada a `GraphEdge` por slug de `source`/`target`.

Sigue el mismo patrón que `dashboard/service.py::get_domains_summary` (join
manual, sin abstraer un helper compartido — son consultas distintas).

### Endpoint (`backend/app/content/router.py`)

`GET /content/graph`, protegido con `get_current_user` (mismo patrón que
`/content/domains` y `/content/concepts/{slug}`).

## Frontend

### Librería

`react-force-graph-2d` (canvas 2D, force-directed nativo, soporta
`onNodeHover`/`onNodeClick`/`centerAt` — no se agrega 3D innecesariamente).

### `src/features/graph/KnowledgeGraph.tsx` (componente compartido)

Props: `{ data: GraphResponse, height: number, highlightSlug?: string,
onNodeClick: (slug: string) => void, interactive: boolean }`.

- Traduce `GraphResponse` al formato `{ nodes, links }` de la librería.
- Color de nodo: gris si `!studied`; si `studied`, escala de color por
  `mastery_score` (rojo bajo → verde alto), reusando el criterio de color de
  `weak_concepts` en el Dashboard.
- Estilo de arista por `type`: `prerequisite` → flecha dirigida sólida;
  `continues_with` → flecha dirigida punteada; `related` → línea sin flecha.
- `interactive=false` (modo preview del Dashboard) desactiva drag y oculta
  buscador/filtros — solo zoom/pan pasivo y click.

### `src/features/graph/GraphPage.tsx` (`/graph`, ruta protegida)

- `KnowledgeGraph` a pantalla completa (`interactive=true`).
- Panel lateral: checkboxes por dominio (filtra `nodes`/`edges` client-side,
  ya viene todo en una sola respuesta) + input de búsqueda (matchea por
  nombre, llama `graphRef.centerAt(node.x, node.y)` + resalta el nodo).
- Tooltip on-hover: nombre, `mastery_score` (o "no estudiado"), próximo
  repaso si existe.
- Click en nodo → `navigate(`/lessons/${slug}`)`.

### Dashboard (`DashboardPage.tsx`)

Reemplaza la entrada "Knowledge Connectivity" de `COMING_SOON` por una
sección real: `<KnowledgeGraph data={graph} height={300} interactive={false}
onNodeClick={...} />` + link "Ver grafo completo" → `/graph`. Usa el mismo
`GraphResponse` (una llamada extra a `/content/graph` en el `useEffect` de la
página, igual que ya hace con `getDashboardSummary`).

### `App.tsx`

Nueva ruta `/graph` dentro de `ProtectedLayout`.

## Manejo de errores / casos vacíos

- Sin concepts o sin relaciones → grafo vacío, mensaje "Todavía no hay
  contenido para mostrar" (mismo patrón que `independence_score === null`).
- Filtro por dominio que deja 0 nodos → panel vacío, sin error.
- Concept sin `ConceptMastery` → se muestra igual (nodo gris, `studied:
  false`), nunca se omite del grafo.

## Testing

Mismo patrón del proyecto: DB real, sin mocks.

- Backend: test de `get_knowledge_graph` — concepts sin mastery aparecen con
  `studied=False, mastery_score=0.0`; relaciones se mapean con el `type`
  correcto; nodos/edges cubren los 3 tipos de `RelationshipType`; endpoint
  requiere auth (401 sin sesión). Caso límite: dominio con un solo concept y
  sin relaciones (no debe romper el join).
- Frontend: test del mapeo `GraphResponse → { nodes, links }` (colores por
  mastery, tipos de arista correctos), test de que el filtro por dominio
  reduce nodes/edges correctamente, test de que el click invoca
  `onNodeClick` con el slug correcto.
- Verificación manual en navegador real: zoom/pan/drag, hover con tooltip,
  búsqueda que centra el nodo, click que navega a la lección, filtro por
  dominio, y el preview del Dashboard (no interactivo) enlazando a `/graph`.

## Fuera de alcance (explícitamente)

- Nodos de `Domain`/`Topic` en el grafo — quedan como filtro/color, no como
  nodos.
- Layout jerárquico/dagre — se decide auto-layout por fuerza.
- Edición de relaciones desde el grafo (crear/borrar `ConceptRelationship`
  visualmente) — el grafo es de solo lectura en v1.
- Persistencia de posiciones de nodos entre sesiones — el layout se
  recalcula cada vez que se carga la página.

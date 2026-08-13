# CyberLearn — Sub-plan: Notas (Fase 1)

> **Depende de:** `docs/superpowers/specs/2026-08-13-cyberlearn-fase0-design.md` (§8, sistema de notas y knowledge graph) y `docs/superpowers/specs/2026-08-13-content-lessons-design.md` (Concept como nodo central).
> **Estado:** aprobado por el usuario el 2026-08-13.

## 1. Modelo de datos

```
Note
  id: uuid
  title: str
  body_markdown: text
  is_global: bool
  linked_concept_id: uuid | null, FK -> concepts.id, UNIQUE (nullable-unique: una nota por concepto)
  created_at, updated_at

NoteLink
  source_note_id: uuid, FK -> notes.id
  target_note_id: uuid | null, FK -> notes.id
  target_concept_id: uuid | null, FK -> concepts.id
  link_text: str
```

Regla: `linked_concept_id` es único entre las filas no nulas (constraint parcial) — garantiza una única nota "de lección" por concepto, tal como se decidió. Las notas globales (`is_global=true`, `linked_concept_id=null`) no tienen ese límite; puede haber cualquier cantidad.

`NoteLink` se recalcula por completo (delete + reinsert) en cada autosave, parseando `[[...]]` del `body_markdown`:
- Si el texto entre `[[ ]]` coincide (case-insensitive) con `Concept.slug` o `Concept.name` → `target_concept_id` se rellena.
- Si no coincide con ningún concepto pero sí con el `title` de otra `Note` → `target_note_id` se rellena.
- Si no coincide con nada → se guarda igual con ambos campos `null` (link "roto", no bloquea el guardado; podría resolverse más adelante si se crea el concepto/nota).

## 2. API

```
GET  /api/v1/notes                          → todas las notas del usuario (para /notes)
POST /api/v1/notes                            → crea una nota global suelta
GET  /api/v1/notes/{id}                        → una nota por id
PUT  /api/v1/notes/{id}                          → actualiza título/cuerpo (recalcula NoteLink)
DELETE /api/v1/notes/{id}

GET  /api/v1/notes/by-concept/{slug}               → la nota ligada a ese concepto, o 404 si no existe
PUT  /api/v1/notes/by-concept/{slug}                 → upsert: crea si no existe, actualiza si existe
```

Todas requieren sesión autenticada (mismo patrón que `content`).

## 3. Frontend

**Panel en `LessonPage`**: columna derecha en desktop (`display: grid`, dos columnas cuando el viewport lo permite), debajo del contenido en móvil (media query). `<textarea>` simple con preview Markdown al lado o debajo (reutiliza `marked`, ya presente). Autosave: `useEffect` con `setTimeout`/debounce ~1.5s tras cada cambio, llama `PUT /notes/by-concept/{slug}`; sin botón "Guardar" visible — un indicador textual discreto ("Guardado" / "Guardando…") es suficiente.

**Ruta `/notes`**: lista todas las notas (`GET /notes`), cada fila muestra título, primeras líneas del cuerpo, y si `linked_concept_id` no es null, un link a esa lección. Botón "Nueva nota" crea una nota global vacía y navega a un editor de nota standalone (reutiliza el mismo componente de textarea+preview+autosave del panel, parametrizado por `note.id` en vez de `slug`).

## 4. Fuera de alcance de este sub-plan

- Export/Import a Obsidian (Fase 2, según el roadmap del spec de Fase 0 §11).
- Búsqueda global / Command Palette (no listado en Fase 1 del roadmap).
- Visualización de grafo interactivo de `NoteLink` (Fase 2, junto con el knowledge graph visual).

## 5. Criterio de aceptación

- Escribir `[[net-01-fundamentals]]` en el cuerpo de una nota y guardar crea un `NoteLink` con `target_concept_id` apuntando a esa lección.
- Al recargar la página de una lección, la nota ligada a ese concepto aparece con el contenido previamente guardado (persistencia real, no solo estado de React).
- Editar dos veces la misma nota de concepto no crea una segunda fila `Note` — el `UNIQUE` parcial en `linked_concept_id` lo garantiza junto con la lógica de upsert.
- `/notes` lista tanto notas de lección como notas globales, distinguibles visualmente.

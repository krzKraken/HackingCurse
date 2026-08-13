# CyberLearn — Sub-plan: Banco de preguntas (mínimo) + Motor de retención + Repaso (Fase 1)

> **Depende de:** `docs/superpowers/specs/2026-08-13-cyberlearn-fase0-design.md` (§5 motor de aprendizaje, §6 flujo de repaso, §7 modelo de preguntas) y `docs/superpowers/specs/2026-08-13-content-lessons-design.md` (Concept como nodo central).
> **Estado:** aprobado por el usuario el 2026-08-13.

## 0. Simplificaciones deliberadas respecto al spec de Fase 0

El spec de Fase 0 diseña un sistema más grande del que tiene sentido construir de una vez, porque varias piezas dependen de módulos que todavía no existen (Labs, ErrorPattern, fragmentation). Este sub-plan implementa una versión real y funcional, con estas simplificaciones explícitas (registradas también en `PROJECT_MASTER_CHECKLIST.md`):

1. **Sin tablas separadas `Answer`/`Evaluation`** — `ReviewItem` concentra respuesta + resultado + confianza en una sola fila. El concepto de "examen" formal (Modo Examen, sección 73 del master prompt) es un sub-plan futuro que sí necesitará separarlas.
2. **`QuestionVariant` sin plantillas ni randomización de contexto** (el `context_generator` de la sección 7.2 del spec de Fase 0) — cada variante es texto literal escrito por el agente de contenido. La generación procedural de variantes es un concern de Fase 3 (generación por IA).
3. **`ConceptMastery.mastery_score` es un único score unificado**, no separado en `theoretical_score`/`practical_score` — esa separación solo tiene sentido cuando exista evaluación práctica real vía Labs.
4. **`confidence_declared` se captura pero no se actúa sobre él** — se guarda en cada `ReviewItem` para tener el dato histórico, pero la lógica de "alta confianza + incorrecto → prioridad de repaso" (sección 29 del master prompt) se implementa en Fase 3, cuando haya suficiente volumen de datos para que la señal sea útil.
5. **El modo de repaso "antes de laboratorio" recibe una lista explícita de `concept slugs`** como prerequisitos, en vez de resolver un `lab_id` — no existe `Laboratory` todavía.

## 1. Modelo de datos

**Banco de preguntas**
```
Question
  id, concept_id (FK), type: multiple_choice | true_false | free_explanation
  difficulty: int 0-7
  evaluation_criteria: text | null   (para free_explanation)
  expected_answer: text | null        (para free_explanation)
  status: draft | published

QuestionVariant
  id, question_id (FK), prompt_markdown: text
  options: json | null                 (lista de strings, solo multiple_choice)
  correct_option_index: int | null      (índice en options, solo multiple_choice)
  correct_bool: bool | null              (solo true_false)
```
`source` (`curated`/`ai_generated`) y la extensión de generación por IA quedan documentadas como pendientes en el checklist — el campo no se modela aún porque no hay generador que lo use todavía (YAGNI).

**Progreso pedagógico**
```
ConceptMastery
  id, user_id (FK), concept_id (FK), UNIQUE(user_id, concept_id)
  mastery_score: float (0-100)
  last_seen: datetime | null
  last_tested: datetime | null

ReviewSchedule
  id, concept_mastery_id (FK, UNIQUE — 1:1)
  stability_days: float
  next_due_at: datetime
```

**Sesiones de repaso**
```
ReviewSession
  id, user_id (FK), mode: str, started_at, ended_at: datetime | null

ReviewItem
  id, review_session_id (FK), concept_id (FK), question_variant_id (FK)
  user_response: text                     (índice elegido, "true"/"false", o texto libre)
  confidence_declared: str | null          (nada_seguro|poco_seguro|seguro|muy_seguro)
  outcome: str | null                       (correct|partial|incorrect — null hasta calificar)
  shown_at: datetime
  answered_at: datetime | null
```

## 2. Motor de retención (fórmulas)

Implementación directa de la sección 5.1-5.2 del spec de Fase 0:

```python
THRESHOLD = 0.85
INITIAL_STABILITY_DAYS = 1 / -ln(THRESHOLD)   # calibrado para que el primer repaso caiga ~día 1

def retention(stability_days, days_since_tested) -> float:
    return exp(-days_since_tested / stability_days)

def update_stability(old_stability, outcome: "correct"|"partial"|"incorrect") -> float:
    factor = {"correct": 1.6, "partial": 1.1, "incorrect": 0.5}[outcome]
    return max(old_stability * factor, MIN_STABILITY_DAYS)

def next_due_at(stability_days, now) -> datetime:
    days_until_threshold = -stability_days * ln(THRESHOLD)
    return now + timedelta(days=days_until_threshold)
```

`mastery_score` se recalcula con una media móvil simple sobre los últimos N=5 `ReviewItem` de ese concepto (`correct`→100, `partial`→50, `incorrect`→0), y también alimenta el **difficulty engine**: `accuracy_rolling ≥ 0.8` → sube dificultad sugerida (usada para filtrar qué `QuestionVariant` mostrar, acotado a ±1 nivel por evento, igual que en la sección 5.2 del spec de Fase 0).

## 3. `ReviewSelector` — 7 modos

```
general          — ReviewSchedule WHERE next_due_at <= now()
debilidades       — ORDER BY mastery_score ASC (ignora next_due_at)
olvidado           — ORDER BY forgetting_risk DESC (1 - retention(...), calculado al vuelo)
por_tema             — filtra por domain_slug/topic_slug
mixto                 — muestreo ponderado cruzando dominios/topics
sorpresa               — muestreo aleatorio entre todos los conceptos con mastery (no solo los vencidos)
pre_lab                  — filtra por lista explícita de concept_slugs (parámetro de la request)
```

Todos pasan por: interleaving (round-robin entre conceptos distintos, nunca agrupar por concepto) → selección de `QuestionVariant` excluyendo las últimas K=3 mostradas por concepto (si se agotan, se permite repetir) → recorte a `budget` (N preguntas o minutos, ~90s/pregunta como heurística de conversión).

## 4. Flujo de una pregunta

```
Mostrar QuestionVariant.prompt_markdown (+ options si es multiple_choice)
   ↓
(opcional) usuario declara confianza — siempre se muestra el selector, no es obligatorio usarlo
   ↓
Intento del usuario
   ↓
multiple_choice / true_false → auto-calificación inmediata (compara con correct_option_index/correct_bool)
free_explanation → se muestran evaluation_criteria + expected_answer, usuario se autocalifica
   (correcto/parcial/incorrecto)
   ↓
Se registra ReviewItem completo (outcome final)
   ↓
Motor recalcula: stability → next_due_at; mastery_score; nivel de dificultad sugerido
```

## 5. API

```
POST /api/v1/reviews/sessions
  body: { mode, domain_slug?, topic_slug?, concept_slugs?, budget_count?, budget_minutes? }
  → { session_id, items: [{ item_id, concept_slug, type, prompt_markdown, options? }] }
  (nunca incluye correct_option_index/correct_bool/expected_answer en esta respuesta)

POST /api/v1/reviews/items/{item_id}/answer
  body: { user_response, confidence_declared? }
  → multiple_choice/true_false: { outcome, correct_option_index | correct_bool }
  → free_explanation: { evaluation_criteria, expected_answer }  (outcome aún null, pendiente self-rate)

POST /api/v1/reviews/items/{item_id}/self-rate
  body: { outcome: correct|partial|incorrect }
  → { outcome }  (solo válido para items de tipo free_explanation con outcome aún null)
```

## 6. Frontend

Ruta `/review`:
- Selector de modo (7 botones) + presupuesto (5/10/15/20 preguntas o 5/10/20 minutos, sección 13 del master prompt).
- `[Empezar]` → crea sesión → muestra ítems uno a uno con el flujo de la sección 4.
- Al terminar: resumen (aciertos/parciales/fallos, conceptos repasados).

## 7. Contenido: preguntas para NET-01 a NET-10

El agente `cybersecurity-instructor` escribe 3-5 `Question` + su `QuestionVariant` por cada una de las 10 lecciones ya cargadas, mezclando los 3 tipos (multiple_choice, true_false, free_explanation), como archivos YAML hermanos de los de lección (`content/networking/net-XX-*.questions.yaml`), cargados por un script de seed nuevo (`seed_questions.py`, mismo patrón de idempotencia que `seed_content.py`).

## 8. Criterio de aceptación

- Responder una pregunta de un concepto nuevo crea `ConceptMastery` + `ReviewSchedule` si no existían.
- Responder correctamente sube `stability_days` y empuja `next_due_at` hacia el futuro; responder mal lo acerca.
- El modo "olvidado" prioriza conceptos con `forgetting_risk` alto sobre los recién repasados.
- Repetir `POST /reviews/sessions` en modo "general" para el mismo concepto no repite la misma `QuestionVariant` que la sesión anterior (si hay más de una disponible).
- `POST /reviews/items/{id}/answer` nunca devuelve la respuesta correcta para preguntas `free_explanation` en el mismo paso — solo tras `self-rate`.
- Las 10 lecciones tienen preguntas reales cargadas y respondibles de punta a punta vía `/review`.

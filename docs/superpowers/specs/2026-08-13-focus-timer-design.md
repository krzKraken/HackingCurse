# CyberLearn — Sub-plan: Focus/Timer + "No sé qué estudiar" (Fase 1)

> **Depende de:** `docs/superpowers/specs/2026-08-13-cyberlearn-fase0-design.md` (§10) y de `ConceptMastery`/`ReviewSchedule` del sub-plan de retención.
> **Estado:** aprobado por el usuario el 2026-08-13.

## 0. Simplificaciones deliberadas

1. **`LearningSession` y `FocusSession` se fusionan en un solo modelo.** El spec de Fase 0 los separaba, pero en la práctica toda sesión activa tiene configuración de timer desde el inicio (con defaults) — no hay caso real donde exista una sin la otra. Una sola tabla `LearningSession` con los campos de timer embebidos.
2. **El algoritmo "No sé qué estudiar" usa 3 señales** (forgetting_risk, debilidad/`1 - mastery_score`, "siguiente en el roadmap": concepto nunca estudiado cuyos prerequisitos ya están completos) en vez de las 5 del spec de Fase 0 — fragmentación y errores personales no existen todavía como módulos.
3. **Selección por prioridad en niveles, no por suma ponderada de pesos.** Más explicable y depurable que ajustar constantes arbitrarias: (1) si algo está vencido, recomendar lo más vencido; si no, (2) si hay un concepto "siguiente" nunca estudiado con prerequisitos satisfechos, recomendarlo; si no, (3) recomendar el concepto con `mastery_score` más bajo para repaso ligero; si no hay contenido en absoluto, no hay recomendación.
4. **No se implementa "context recap"** (master prompt §52: 3 preguntas rápidas si han pasado varios días desde la última sesión). Este sub-plan solo cubre resume de posición (`last_position`). Context recap queda pendiente, registrado en el checklist — se puede construir reutilizando `ReviewSelector` con `budget_count=3` filtrado a los conceptos de la última sesión, una vez que valga la pena esa capa adicional de fricción de reentrada.

## 1. Modelo de datos

```
LearningSession
  id, user_id (FK)
  started_at: datetime
  ended_at: datetime | null
  active_time_sec: int, default 0        (actualizado por ping periódico del frontend)
  last_position: str | null                (ruta del frontend, ej. "/lessons/net-04-routing")
  timer_mode: count_up | pomodoro | countdown | no_timer, default count_up
  pomodoro_preset: str | null               (ej. "25/5")
  break_reminder_threshold_min: int, default 50
  hyperfocus_reminder_min: int, default 90
```

Regla: un usuario tiene como máximo una `LearningSession` activa (`ended_at IS NULL`) a la vez. Al iniciar una nueva, si existe una activa se cierra automáticamente (`ended_at = now()`) — cubre el caso de cerrar el navegador sin terminar la sesión explícitamente.

## 2. API

```
POST /api/v1/focus/sessions
  → crea una nueva LearningSession (cierra la anterior activa si existía)
  → { id, started_at, timer_mode, ... }

GET /api/v1/focus/sessions/current
  → la sesión activa del usuario (ended_at IS NULL), o 404 si no hay ninguna
  (usado al cargar la app para ofrecer "Continuar donde estabas")

PATCH /api/v1/focus/sessions/{id}
  body: { active_time_sec?, last_position?, timer_mode?, pomodoro_preset? }
  → actualiza la sesión (ping periódico desde el frontend)

POST /api/v1/focus/sessions/{id}/end
  → marca ended_at = now()

GET /api/v1/focus/recommendation?minutes=15
  → { activity_type: "review"|"learn", concept_slug, concept_name, reason }
  → 204 sin contenido si no hay nada que recomendar (sin conceptos con preguntas aún)
```
Todas autenticadas, mismo patrón que los módulos anteriores.

## 3. Frontend

- **Al cargar la app** (tras login): `GET /focus/sessions/current`. Si existe, mostrar un banner "Continuar donde estabas" con link a `last_position`.
- **Timer**: widget flotante/fijo simple con conteo ascendente (obligatorio, sección 47 del master prompt — el modo `no_timer` solo oculta el número, el conteo sigue corriendo internamente). Selector de modo (Count Up / Pomodoro con presets 15-5, 25-5, 40-10, 50-10 / Countdown / No Timer).
- **Recordatorio de pausa**: al cruzar `break_reminder_threshold_min` de tiempo activo, mostrar prompt no bloqueante con `[Pausa]` `[Seguir]` `[No preguntar hoy]` (dismissal por día en `localStorage`, no en backend — es preferencia efímera de UI).
- **Hyperfocus reminder**: al cruzar `hyperfocus_reminder_min`, mensaje informativo una vez; nunca detiene la sesión.
- **Focus Mode**: toggle simple (persistido en `localStorage`) que oculta elementos secundarios de la UI actual.
- **Botón "No sé qué estudiar"**: visible de forma persistente (ej. en cada página principal); al pulsar, pide minutos disponibles (o usa un valor por defecto de 15) y llama `GET /focus/recommendation`, mostrando una única actividad con `[Empezar]` que navega a `/review` (modo `pre_lab` con ese concepto) o `/lessons/:slug` según `activity_type`.
- **Ping de sesión**: cada ~30s (y en cada cambio de ruta relevante), `PATCH` la sesión activa con `active_time_sec` acumulado y `last_position` actual. Si no existe sesión activa al empezar a interactuar, se crea una (`POST /focus/sessions`) de forma transparente.

## 4. Criterio de aceptación

- Cerrar la pestaña sin salir y volver a abrir la app muestra "Continuar donde estabas" apuntando a la última página visitada.
- El timer nunca se detiene automáticamente ni bloquea la interacción, incluso pasado el umbral de hyperfocus.
- "No sé qué estudiar" en una cuenta sin ningún concepto repasado devuelve un concepto "siguiente" (sin prerequisitos pendientes), no un error ni un repaso vacío.
- "No sé qué estudiar" en una cuenta con repasos vencidos prioriza el más vencido sobre sugerir contenido nuevo.
- Iniciar una segunda sesión sin haber cerrado la primera cierra automáticamente la anterior (nunca hay dos `LearningSession` activas para el mismo usuario).

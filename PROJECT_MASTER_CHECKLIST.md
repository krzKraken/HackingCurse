# PROJECT_MASTER_CHECKLIST.md

> Checklist vivo del proyecto CyberLearn, según master prompt §146-147.
> Se actualiza después de cada implementación. `- [ ]` pendiente, `- [x]` completado
> (solo se marca `[x]` cuando: implementación + tests + verificación end-to-end están hechos).

## Fase 0 — Diseño

- [x] Spec de arquitectura general (`docs/superpowers/specs/2026-08-13-cyberlearn-fase0-design.md`)

## Fase 1 — Core

### Scaffolding + Auth
- [x] Docker Compose (Postgres/Redis), FastAPI boot, engine SQLAlchemy/Alembic
- [x] Modelo User, hashing Argon2, TOTP, sesiones Redis, rate limiting
- [x] Endpoints login/mfa/me/logout
- [x] Script CLI `create_owner.py`
- [x] Frontend React+Vite: login/MFA/rutas protegidas
- [x] Verificación end-to-end en navegador

### Contenido + Lecciones
- [x] Modelos Domain/Topic/Concept/Lesson/ConceptRelationship + migración
- [x] Servicio + endpoints `/content/domains`, `/content/concepts/{slug}`
- [x] Cargador YAML idempotente (`seed_content.py`)
- [x] Visor de lecciones en frontend (`/lessons/:slug`)
- [x] 10 lecciones reales de Networking (NET-01 a NET-10) escritas y cargadas

### Notas
- [x] Modelos Note/NoteLink + migración (1 nota por concepto)
- [x] Servicio con resolución de wikilinks `[[...]]`
- [x] Endpoints CRUD + `by-concept`
- [x] `NoteEditor` con autosave, panel embebido en lección
- [x] Página `/notes` + editor standalone `/notes/:id`

### Banco de preguntas (mínimo) + Motor de retención + Repaso
- [x] Modelos Question/QuestionVariant (multiple_choice, true_false, free_explanation — sin tablas separadas Answer/Evaluation, ver spec §0)
- [x] Preguntas reales para NET-01 a NET-10 (agente cybersecurity-instructor, 50 preguntas)
- [x] ConceptMastery + ReviewSchedule (curva de olvido, stability S)
- [x] Difficulty engine (rolling accuracy window)
- [x] ReviewSelector: modo general
- [x] ReviewSelector: modo debilidades
- [x] ReviewSelector: modo olvidado
- [x] ReviewSelector: modo por tema
- [x] ReviewSelector: modo mixto
- [x] ReviewSelector: modo sorpresa
- [x] ReviewSelector: modo antes-de-laboratorio (sin labs reales aún, solo prerequisitos por concept_slugs)
- [x] Flujo de pregunta: mostrar → confidence check → intento → evaluar → explicación → registrar
- [x] Auto-evaluación guiada para `free_explanation` (mostrar criterios/respuesta modelo tras el intento)
- [x] Frontend: página `/review` con selector de modo/cantidad
- [x] Verificación end-to-end (API + navegador)

**Pendiente para más adelante (fuera de este sub-plan, dejar registrado):**
- [ ] Modo de repaso "errores personales" (depende de `ErrorPattern`, módulo `errors/`)
- [ ] Modo de repaso "integración" (depende de fragmentation score, módulo `fragmentation/`)
- [ ] Calificación asistida por IA para respuestas de `free_explanation` (extensión futura, flag `AI_GRADING_ENABLED`)

### Dashboard
- [x] Agregación de métricas ya calculadas (nivel por dominio, retención, repasos pendientes)
- [x] Página `/dashboard` con tarjetas "Próximamente" para widgets aún no construidos

### Focus/Timer + "No sé qué estudiar"
- [x] LearningSession, timer (4 modos), Focus Mode
- [x] Session resume (última posición)
- [ ] Context recap (3 preguntas rápidas tras un hueco de varios días — no implementado en este sub-plan)
- [x] Algoritmo de recomendación única ("No sé qué estudiar")

### Labs + orquestador Docker
- [x] Modelo Laboratory/LabInstance + definición declarativa YAML (sin LabAttempt separado — simplificación documentada)
- [x] Worker orquestador (RQ) con acceso exclusivo al socket Docker
- [x] Aislamiento de red verificado (test de integración real: no alcanza Internet ni Postgres del host)
- [x] 1 lab Docker real (FlagBox, IDOR sobre TCP custom) con cleanup automático — más labs quedan pendientes de contenido, no de infraestructura
- [x] Terminal web integrada para labs (xterm.js + docker exec vía WebSockets, proxy autenticado a través del worker)

## Fase 2

### Challenges + hints progresivos
- [x] Challenges: cubierto por `Laboratory.type` (campo ya existente, sin modelo nuevo — ver `docs/superpowers/specs/2026-08-14-challenges-hints-design.md` decisión 1)
- [x] Hint Dependency + Independence Score en el Dashboard

### Gamificación (sobria)
- [x] Achievements basados en habilidad (7 en el catálogo v1: first_shell, no_hint_required, independent_mind, persistent, perfect_recall, domain_mastery, deep_focus)
- [x] XP y niveles (calculado, no almacenado) en el Dashboard
- [ ] Skill tree — explícitamente fuera de alcance del v1 (ver `docs/superpowers/specs/2026-08-14-gamificacion-design.md`)

### Pendientes de Fase 2
- [ ] Knowledge graph navegable — vista visual interactiva (hoy solo lista jerárquica vía relaciones)
- [ ] Base de datos de vulnerabilidades
- [ ] Error Memory completo (`ErrorPattern`)
- [ ] Fragmentation score + ejercicios integradores
- [ ] Export/Import Obsidian (notas y lecciones)
- [ ] Búsqueda global / Command Palette (Ctrl+K)

## Fase 3

- [ ] Activar extensión IA: generación de preguntas cuando el banco se agota (`AI_GENERATION_ENABLED`)
- [ ] Calificación asistida por IA para respuestas abiertas (`AI_GRADING_ENABLED`)
- [ ] Tutor socrático
- [ ] Spaced repetition avanzado (ajuste refinado de S con más señales)
- [ ] Confidence calibration completo
- [ ] Transfer tests
- [ ] Attack Path Visualizer

## Fase 4

- [ ] Labs multi-host, Active Directory, pivoting
- [ ] Blue/Purple team (Detection Lab)

## Fase 5

- [ ] Synthetic unknown vulnerabilities
- [ ] Research labs, reversing, exploit dev controlado

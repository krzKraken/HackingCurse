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
- [ ] LearningSession/FocusSession, timer (4 modos), Focus Mode
- [ ] Session resume + context recap
- [ ] Algoritmo de recomendación única ("No sé qué estudiar")

### Labs + orquestador Docker
- [ ] Modelo Laboratory/LabInstance/LabAttempt + definición declarativa YAML
- [ ] Worker orquestador (Celery/RQ) con acceso exclusivo al socket Docker
- [ ] Aislamiento de red verificado (test de integración de seguridad)
- [ ] 2-3 labs Docker reales con cleanup automático

## Fase 2

- [ ] Challenges + hints progresivos
- [ ] Gamificación (sobria)
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

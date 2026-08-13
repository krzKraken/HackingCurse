# CyberLearn — Fase 0: Diseño técnico

> **Fuente funcional/pedagógica:** `CYBERLEARN_MASTER_PROMPT.md` (documento maestro, fuente de verdad de producto).
> **Este documento:** entregable obligatorio de la sección 158 del master prompt — arquitectura, modelo de datos, threat model y diseño de los subsistemas centrales, antes de escribir código.
> **Estado:** aprobado por el usuario el 2026-08-13.

---

## 0. Decisiones de alcance (respuestas del usuario durante brainstorming)

- **Punto de partida:** Fase 0 completa (diseño) antes de tocar código.
- **Stack:** el sugerido por el master prompt, con un ajuste — ver sección 1.
- **Entorno destino:** servidor propio expuesto en red (VPS / home server accesible remotamente). Esto eleva la prioridad del threat model.
- **Infraestructura de labs:** un solo servidor, todo en Docker, con redes Docker aisladas.
- **IA generativa:** banco de preguntas curado ahora (autor: el usuario) + punto de extensión diseñado para conectar una API de LLM cuando el banco sea insuficiente. No se implementa la llamada a IA en Fase 1.
- **Autenticación:** usuario/contraseña (Argon2) + MFA TOTP desde el inicio.

---

## 1. Arquitectura general

```
                         Internet
                            │
                       (HTTPS/TLS)
                            │
                    ┌───────▼────────┐
                    │  Reverse Proxy │  (Caddy o Nginx — TLS termination,
                    │  + rate limit  │   rate limiting, security headers)
                    └───────┬────────┘
                            │
              ┌─────────────┴─────────────┐
              │                           │
      ┌───────▼────────┐         ┌────────▼────────┐
      │  Frontend       │         │  API Backend     │
      │  React + Vite   │◄───────►│  FastAPI          │
      │  (SPA)          │  REST   │  (monolito         │
      └─────────────────┘         │   modular)         │
                                   └────────┬───────────┘
                                            │
                        ┌───────────────────┼────────────────────┐
                        │                   │                    │
                ┌───────▼──────┐   ┌────────▼───────┐   ┌────────▼────────┐
                │ PostgreSQL   │   │ Redis           │   │ Lab Orchestrator │
                │ (datos,      │   │ (cache, colas,  │   │ Worker           │
                │  progreso,   │   │  rate limit)    │   │ (Celery/RQ,      │
                │  contenido)  │   └─────────────────┘   │  único con       │
                └──────────────┘                         │  acceso al       │
                                                           │  socket Docker)  │
                                                           └────────┬─────────┘
                                                                    │
                                                     ┌──────────────▼───────────────┐
                                                     │   LAB NETWORK (aislada)      │
                                                     │   Docker bridge network(s)   │
                                                     │   sin salida a Internet      │
                                                     │   por defecto                │
                                                     │                              │
                                                     │  [attacker] [target1] [db]…  │
                                                     └───────────────────────────────┘
```

**Decisiones clave:**

- **Frontend: React + Vite + React Router**, no Next.js. Es una SPA privada autenticada de un solo usuario, sin necesidad de SEO ni SSR; Next.js añadiría complejidad (server components, rutas híbridas) sin beneficio real aquí.
- El **API Backend** nunca toca Docker directamente. Solo publica jobs ("crear lab X para user Y") en una cola Redis. El **Lab Orchestrator Worker** es el único proceso con acceso al socket de Docker — así, si el API (expuesto a Internet) se compromete, el atacante no llega directo a Docker.
- La red de labs es una red Docker **bridge aislada, sin acceso a Internet por defecto** (excepción puntual y auditada si un lab necesita build-time internet, sección 97 del master prompt).
- El reverse proxy hace TLS, rate limiting y cabeceras de seguridad (CSP, HSTS) — el servidor está expuesto públicamente.
- Redis se usa para cola de jobs de labs, cache de sesión y rate limiting — no como base de datos de progreso (eso vive en Postgres).

**Arquitectura de backend:** monolito modular en FastAPI + worker separado para orquestar labs (Celery/RQ), en vez de microservicios (serían sobre-ingeniería para un solo usuario).

**Modelo de datos:** PostgreSQL + SQLAlchemy + Alembic, esquema único, normalizado, sin sharding ni multi-tenancy prematura.

**Motor de aprendizaje adaptativo:** fórmulas determinísticas y explicables, no ML — el master prompt exige poder explicar siempre el "por qué" de una recomendación (secciones 41, 154).

---

## 2. Mapa de módulos

### Backend (FastAPI, monolito modular)

```
backend/
├── auth/             → login, MFA TOTP, sesiones, RBAC preparado (solo OWNER activo)
├── content/          → Domain, Topic, Concept, Lesson, ConceptRelationship
├── learning/         → motor adaptativo: ConceptMastery, SkillProgress, difficulty engine
├── retention/        → ReviewSchedule, ReviewSession, forgetting engine, spaced repetition
├── fragmentation/     → ConceptRelationshipScore, fragmentation score, ejercicios integradores
├── evaluation/         → Question, QuestionVariant, Answer, Evaluation, exam mode
├── errors/               → ErrorPattern, FailedAttempt, error memory
├── confidence/            → ConfidenceMeasurement, calibration
├── notes/                  → Note, Tag, Markdown, wikilinks, export Obsidian
├── knowledge_graph/         → grafo navegable, prerequisitos, relaciones
├── labs/                     → Laboratory, LabInstance, LabAttempt (llama al orchestrator vía cola)
├── lab_orchestrator/ (worker) → Docker Compose lifecycle: create/start/stop/reset/destroy/health
├── challenges/                → Challenge, ChallengeAttempt, hints progresivos
├── vulnerabilities/            → Vulnerability, CVE, CWE, AttackChain
├── focus/                       → LearningSession, FocusSession, timer, break reminders
├── gamification/                 → Achievement, XP, badges (sobrio)
├── dashboard/                     → agregación de métricas para el home/dashboard
├── search/                          → búsqueda global (Postgres full-text al inicio)
└── audit/                            → audit log (lab created, hint requested, etc.)
```

### Frontend (React + Vite, por feature)

```
frontend/src/
├── app/           → shell, routing, layout (sidebar desktop / drawer móvil)
├── features/
│   ├── dashboard/
│   ├── lessons/
│   ├── review/       → "Repasar ahora", test aleatorio, modos de repaso
│   ├── labs/           → terminal/lab UI, lab lifecycle controls
│   ├── notes/            → editor Markdown + preview + backlinks
│   ├── knowledge-graph/    → visualización de grafo
│   ├── focus/               → timer, focus mode, "No sé qué estudiar"
│   ├── challenges/
│   └── exams/
├── components/     → UI compartida (design system propio, sobrio)
└── lib/             → cliente API, hooks de auth, estado global
```

**Regla de dependencia:** los módulos pedagógicos (`learning`, `retention`, `fragmentation`, `errors`, `confidence`) son el núcleo — otros módulos (`labs`, `evaluation`, `challenges`) *reportan eventos hacia* ellos, nunca al revés. Esto protege el motor pedagógico de acoplarse a features específicas (sección 159 del master prompt: no sacrificar el motor pedagógico por simplificar features).

---

## 3. Modelo de datos

Basado en el modelo mínimo de la sección 136 del master prompt, agrupado por dominio funcional.

**Contenido & Knowledge Graph**
```
Domain 1──* Topic 1──* Concept
Concept *──* Concept   (vía ConceptRelationship: prerequisite | related | continues_with)
Concept 1──* Lesson
```
`Concept` es el nodo central del grafo — preguntas, labs y notas referencian conceptos, no lecciones directamente.

**Progreso pedagógico (por usuario × concepto)**
```
User 1──* ConceptMastery (por Concept)
  campos: theoretical_score, practical_score, retention_score,
          autonomy_score, confidence_declared, confidence_real,
          level (0-7, sección 5 del master prompt), last_seen, last_tested
User 1──* ConceptRelationshipScore  (Concept Connectivity, sección 11)
```

**Repetición espaciada / Forgetting Engine**
```
ConceptMastery 1──1 ReviewSchedule (next_due_at, interval_stage)
ReviewSession 1──* ReviewItem 1──1 Concept
```
`ReviewSchedule` guarda solo el próximo punto de repaso; el historial vive en `ReviewItem`, de donde se recalcula `retention_score`.

**Evaluación**
```
Concept 1──* Question 1──* QuestionVariant
Evaluation 1──* Answer *──1 QuestionVariant
```
`QuestionVariant` es la unidad servida al usuario (nunca la misma `Question` literal dos veces). `Question.source` distingue `curated` vs `ai_generated`.

**Errores y calibración**
```
User 1──* ErrorPattern *──1 Concept  (repetitions, last_seen)
User 1──* ConfidenceMeasurement *──1 QuestionVariant
User 1──* TransferAssessment *──1 Concept
```

**Labs**
```
Laboratory (definición declarativa, versionada) 1──* LabInstance *──1 User
LabInstance 1──* LabAttempt
Laboratory *──* Concept
```
`Laboratory` es la plantilla; `LabInstance` es una ejecución concreta con su propia red Docker aislada y valores randomizados.

**Retos, notas, vulnerabilidades, focus, auditoría** — mismo patrón 1-a-muchos por `User`, referenciando `Concept` cuando aplica.

**Por qué una sola base de datos:** con un solo usuario no hay necesidad de particionar; mantener todo en un Postgres permite joins directos entre progreso, contenido y labs para calcular fragmentación/retención sin sincronización entre sistemas.

---

## 4. Threat model & modelo de seguridad de labs

**Activos a proteger**
1. Cuenta OWNER (credenciales, sesión, MFA).
2. Datos de progreso/notas (mitigado con backups, no catastrófico si se pierde parcialmente).
3. El socket de Docker del host — control total del servidor si se compromete.
4. La red del laboratorio — no debe ser trampolín hacia Internet ni hacia la red del servidor/casa.

**Actores de amenaza**
- Atacante anónimo en Internet contra el servidor expuesto (caso principal).
- Código dentro de un contenedor de lab comportándose maliciosamente — **por diseño**, el lab es hostil (el usuario lo está explotando activamente).
- Fuga de credenciales/tokens si un lab captura tráfico o se reusan secretos entre plataforma y lab.

**Fronteras de confianza**

```
Internet  ───────▶  [Reverse Proxy]  ───────▶  [API Backend]
  (no confiable)        (TLS, rate limit)         (confiable, sin acceso Docker)
                                                          │
                                                    (cola de jobs)
                                                          │
                                                          ▼
                                              [Lab Orchestrator Worker]
                                              (confiable, ÚNICO con socket Docker)
                                                          │
                                                          ▼
                                              [LAB NETWORK] ← NO CONFIABLE
                                              (hostil por diseño, aislada,
                                               sin salida a Internet ni a
                                               la red del host/casa)
```

**Controles concretos**

| Riesgo | Control |
|---|---|
| API comprometida intenta escapar a Docker | API nunca tiene el socket Docker montado; solo encola jobs en Redis. El worker valida y limita qué jobs puede ejecutar (allowlist de imágenes/templates definidos en `Laboratory`, nunca comandos arbitrarios). |
| Contenedor de lab intenta pivotar a la LAN de casa o a Internet | Red Docker `internal: true` por defecto. Excepción de build-time solo si el `Laboratory.yaml` lo declara explícitamente, y se cierra al terminar el build. |
| Contenedor de lab intenta alcanzar la API/DB de la plataforma | Red de labs completamente separada de la red donde viven API/Postgres/Redis. |
| Fuerza bruta / credential stuffing contra login | Rate limiting en proxy + backend, lockout progresivo, MFA TOTP obligatorio, hashing Argon2. |
| Fuga de sesión / XSS | Cookies `httpOnly` + `secure` + `SameSite=strict`, CSP estricta (el editor de notas no ejecuta HTML/JS embebido). |
| Lab corriendo indefinidamente / DoS de recursos | Límites de CPU/memoria por contenedor (`Laboratory.yaml`), `max_lifetime_min` por `LabInstance`, job programado que destruye instancias huérfanas. |
| Reset/destroy deja residuos | Orchestrator valida post-destroy: lista contenedores/redes/volúmenes con label `lab_instance_id` y confirma limpieza total; se audita el resultado. |
| Compromiso del host (fuera del threat model de software) | Recomendado a nivel de infraestructura: usuario Docker sin privilegios root del host, actualizaciones automáticas del SO, firewall exponiendo solo el puerto 443. |

**Fuera de alcance Fase 0-1 (explícito, no omisión):** atacante con acceso físico al servidor; "synthetic zero-day" labs con exploit development real (Fase 5, con aislamiento reforzado adicional).

---

## 5. Motor de aprendizaje adaptativo

Determinístico y explicable — cada score tiene una fórmula clara.

**5.1 Retention Score — curva de olvido**

```
R(t) = e^(−t / S)
```
- `t` = días desde la última práctica del concepto.
- `S` = stability, sube con recuerdos exitosos, baja con fallos o hints.
- Actualización por `ReviewItem`: `S_new = S_old × factor` (`factor > 1` si acertó sin pistas y sin demora excesiva; `factor < 1` si falló o usó hints).

`forgetting_risk = 1 − R(t)`, alimenta `ReviewSchedule.next_due_at` cuando `R(t)` cruza un umbral configurable (ej. 0.85). Los días 0/1/3/7/14/30/90/180/365 del master prompt son el punto de partida de `S` para un concepto nuevo, no una tabla fija.

**5.2 Difficulty Engine**

Rolling window de últimos N=5 intentos por concepto:
```
accuracy_rolling = aciertos_sin_hint / N
```
- `accuracy_rolling ≥ 0.8` y último intento sin hints → sube un nivel (máx +1 por sesión).
- ≥3 fallos consecutivos o dependencia de hints creciente → baja un nivel, dispara microlección (sección 59 del master prompt).
- Cambios acotados a ±1 por evento — evita que una mala racha se convierta en barrera.

**5.3 Fragmentation Score**

```
fragmentation_score = avg(individual_concept_mastery del escenario) − integrated_scenario_score
```
Bandas: `<15pp = LOW`, `15–30pp = MEDIUM`, `>30pp = HIGH` (configurable). MEDIUM/HIGH dispara un ejercicio integrador específico para esos conceptos (no genérico).

**5.4 Concept Connectivity Score**

`ConceptRelationshipScore` (par de conceptos, ej. ARP↔Routing) se actualiza solo con evidencia directa: ejercicios que exigen relacionar ambos, o escenarios integradores donde ambos participan. Distinto de fragmentación (que mide el conjunto, no el par).

**5.5 Confidence Calibration**

```
calibration_gap = confidence_declared − (1 si correcto, 0 si incorrecto)
```
Caso vigilado: confianza alta + respuesta incorrecta → prioridad alta de repaso (conocimiento incorrecto consolidado, sección 29).

**5.6 Orquestación**

Todos los cálculos viven en `learning/` y se ejecutan **síncronamente** al registrar una `Answer` o `ReviewItem` (operaciones baratas, sin IA). `dashboard/` solo lee scores ya calculados.

---

## 6. Flujo de repaso / spaced repetition (nivel de usuario)

**6.1 Puntos de entrada**

```
Dashboard "Repaso recomendado hoy"     → automático, tamaño pequeño
Botón "Repasar ahora"                   → usuario elige cantidad o duración
Botón "🎲 Test aleatorio"                → usuario elige dominio/modo
"No sé qué estudiar"                    → una sola actividad recomendada
Antes de laboratorio                    → repaso de prerequisitos
```
Todos entran al mismo servicio central `ReviewSelector` (módulo `retention/`), solo cambian los filtros.

**6.2 `ReviewSelector`**

```
Input: { modo, budget (N preguntas | minutos), dominio opcional }

1. Candidatos = ReviewSchedule WHERE next_due_at <= now()
                (filtros según modo: forgetting_risk desc, mastery asc,
                 por Domain/Topic, join ErrorPattern, fragmentation alto,
                 sample ponderado si es "sorpresa"/"mixto")

2. Interleaving: NO agrupar por concepto — round-robin entre
   conceptos distintos, para forzar identificación de qué
   conocimiento aplica en cada pregunta.

3. QuestionVariantPicker por concepto: variante no vista en los
   últimos K repasos (ReviewItem.variant_id). Si no quedan,
   sube dificultad o cambia representación en vez de repetir literal.

4. Recorta a budget.

Output: Evaluation (sesión) con QuestionVariants ordenadas.
```

**6.3 Ciclo de una pregunta**

```
Mostrar QuestionVariant → Confidence check (opcional) → Intento →
Evaluación → Explicación (nunca antes del intento) →
Registrar Answer + ReviewItem →
Motor recalcula: S → retention_score → next_due_at;
                 accuracy_rolling → difficulty;
                 ErrorPattern si aplica
```

**6.4 No repetición**

`ReviewItem` guarda `variant_id` y `context_seed` mostrados; `QuestionVariantPicker` excluye variantes/contextos recientes.

**6.5 Relación con Cold Case**

Cold Case reutiliza el mismo motor a nivel de `Laboratory`: busca un `LabInstance` completado hace meses y genera una nueva instancia con `context_seed` distinto. Vive en `labs/`.

---

## 7. Modelo de preguntas — banco curado + extensión IA

**7.1 Autoría (Fase 1)**

Contenido como código versionado, no UI de administración:
```
content/
├── networking/
│   ├── ARP.concept.yaml
│   └── ARP.questions.yaml
```
Script de seed carga estos YAML a Postgres en cada deploy/migración — da versionado en git y encaja con export/import Obsidian.

**7.2 Estructura**

```
Question
  concept_id, type (multiple_choice | true_false | free_explanation |
  complete_command | identify_error | interpret_output | analyze_pcap |
  analyze_http | analyze_logs | analyze_code | debugging |
  troubleshooting | open_research | lab)
  difficulty: 0-7
  source: curated | ai_generated
  status: draft | published
  evaluation_criteria, expected_answer

QuestionVariant
  question_id, template (placeholders), context_generator,
  representation: text | diagram | pcap | terminal | code
```

**7.3 Calificación**

- Tipos estructurados → auto-calificados.
- Tipos abiertos → auto-evaluación guiada: se muestran `evaluation_criteria` + `expected_answer` **después** del intento, el usuario se autocalifica (correcto/parcial/incorrecto). Único enfoque viable sin IA en Fase 1; alineado con no-shame design.

**7.4 Punto de extensión IA (diseñado, no implementado en Fase 1)**

```
QuestionVariantPicker sin variantes sin usar para un concepto
   ↓
Si AI_GENERATION_ENABLED (flag, off por defecto):
   encola job async → worker llama API de LLM →
   genera Question+QuestionVariant (status=draft, source=ai_generated)
   con concepto, dificultad, criterios, prerequisitos
   ↓
Revisión manual: usuario aprueba (draft → published) antes de
entrar en rotación — evita preguntas desconectadas del knowledge graph
Si flag off: se reutilizan variantes con mayor separación temporal.
```
Async porque llamar a un LLM externo no debe bloquear el request HTTP ni acoplar `evaluation/` a una API externa síncrona.

---

## 8. Sistema de notas & knowledge graph

**8.1 Unificación de grafos**

Wikilink `[[X]]` en una nota:
- Si `X` coincide con un `Concept` existente → apunta al nodo del knowledge graph.
- Si no → link nota-a-nota libre.

El knowledge graph visualizado combina relaciones curadas (`ConceptRelationship`) + relaciones emergentes (wikilinks de notas propias), sin duplicar modelos.

**8.2 Modelo**

```
Note
  owner_id, title, body_markdown, is_global, linked_concept_id (nullable)
  tags: *──* Tag
  created_at, updated_at (autosave)

NoteLink (recalculado en cada autosave)
  source_note_id, target_note_id | target_concept_id, link_text
```

**8.3 Editor**

Layout sidebar/contenido/notas en desktop (notas a la derecha); notas debajo del contenido en móvil. Markdown con preview en vivo, autosave con debounce (~1-2s), sin botón "guardar" explícito. Autocompletado de `[[` sugiriendo Concepts primero.

**8.4 Visualización**

Fase 1: vista de lista jerárquica (prerequisitos/relacionados/continúa + notas vinculadas). Grafo visual interactivo (force-directed): Fase 2, misma data.

**8.5 Export/Import Obsidian**

Serialización a Markdown con frontmatter YAML (id, tags) y wikilinks intactos. Import preserva `id` de frontmatter para evitar duplicados.

**8.6 Búsqueda**

Postgres full-text search (`tsvector`) sobre notas, conceptos y cheatsheets. Alimenta el Command Palette (Ctrl+K).

---

## 9. Sistema de labs

**9.1 `Laboratory` — definición declarativa**

```yaml
id: web-sqli-001
title: "SmallShop"
type: guided | semi_guided | black_box | multi_stage | mystery | research
difficulty: beginner
duration_estimate_min: 45
concepts: [SQLi, Authentication, Linux Privilege Escalation]

services:
  web:
    build: ./services/web
    randomize: [port, admin_username, flag_token]
  database:
    image: postgres:16

network:
  isolated: true
  internet: false

hints:
  - level: 1
    text: "¿Qué endpoints has enumerado?"

resources:
  cpu_limit: "1.0"
  memory_limit: "512m"
  max_lifetime_min: 180

cleanup:
  remove_volumes: true
```
Vive en `content/labs/*.yaml`, mismo flujo de autoría que preguntas/lecciones.

**9.2 Ciclo de vida — `LabInstance`**

```
requested → provisioning → running → (paused) → completed | destroyed | expired
```

```
Frontend → API (labs/) crea LabInstance (requested) → encola job en Redis
   → Worker consume → genera context_seed (randomiza puertos, usuarios,
     flags, mismo mecanismo que QuestionVariant) → docker compose up en
     red aislada DEDICADA a esta instancia → health check → running
   → API actualiza status, frontend hace poll/WS
```

Cada `LabInstance` tiene su **propia red Docker** (no compartida ni entre instancias del mismo `Laboratory`) — evita colisiones y mantiene el aislamiento del threat model por instancia.

**9.3 API del orquestador**

```
create(laboratory_id, user_id) → LabInstance
start(instance_id) / stop(instance_id)
reset(instance_id)     → destruye y recrea con nuevo context_seed
destroy(instance_id)   → docker compose down -v + verifica limpieza
health_check(instance_id)
```
Job programado destruye `LabInstance` con `now() > requested_at + max_lifetime_min`.

**9.4 Hints y anti-walkthrough**

`HintUsage` registra nivel de hint pedido → alimenta Hint Dependency y Difficulty Engine (mucho uso de hints baja dificultad). `context_seed` (puertos, usuarios, flags, rutas) evita que un walkthrough externo memorizado sirva literal.

**9.5 Tipos de lab**

`guided`/`semi_guided`/`black_box` solo cambian cuánta info se muestra antes de empezar; `multi_stage`/`network` declaran más servicios con dependencias; `mystery`/`research` son metadatos que ocultan categoría en la UI. Misma infraestructura subyacente (`Laboratory` + `LabInstance`) para todos.

---

## 10. Focus / Timer UX + "No sé qué estudiar"

**10.1 Modelo de sesión**

```
LearningSession
  user_id, started_at, ended_at, active_time_sec,
  topic/activity_type, lab_instance_id (nullable),
  last_position (lesson_id | note_draft_id | lab_instance_id)
  interruptions_declared (opcional)

FocusSession (1:1 con LearningSession activa)
  timer_mode: count_up | pomodoro | countdown | no_timer
  pomodoro_preset: 15/5 | 25/5 | 40/10 | 50/10 | custom
  break_reminder_threshold_min (default ~50)
  hyperfocus_reminder_min (default 90, configurable)
```
`count_up` es default y no puede desactivarse por completo (el conteo interno sigue corriendo para métricas aunque el usuario elija `no_timer` en la UI).

**10.2 Recordatorios — nunca bloquean**

```
active_time >= break_reminder_threshold
   → "Llevas 52 minutos. ¿Pausa de 5 min?" [Pausa] [Seguir] [No preguntar hoy]

active_time >= hyperfocus_reminder_min
   → "Has trabajado 90 minutos. Guarda notas. Pausa si la necesitas."
   (informativo, nunca detiene la sesión)
```
Timer corre client-side, ping al backend cada N min para persistir `active_time_sec`.

**10.3 Session Resume + Context Recap**

```
LearningSession sin ended_at → ofrecer "Continuar donde estabas" (last_position)

Gap desde última sesión > N días (ej. 3):
  → ReviewSelector budget=3, filtrado a conceptos de la última sesión
  → si responde bien: continuar directo
  → si falla: microrepaso antes de continuar
```

**10.4 "No sé qué estudiar" — scoring**

```
score = w1·forgetting_risk + w2·(1−mastery_score) + w3·fragmentation_flag
      + w4·error_recency + w5·roadmap_proximity

Filtrar candidatos por tiempo disponible declarado (5/15/25/45/90 min o libre)
Elegir el de mayor score
Explicar con el factor dominante ("ARP tiene retención baja y afecta Routing")
```
Pesos son constantes configurables, no aprendidas — mantiene explicabilidad. Devuelve una sola actividad con `[Empezar]`.

**10.5 Focus Mode**

Modo de render del frontend (no módulo de backend nuevo): oculta stats secundarias/gamificación/nav, muestra objetivo actual + contenido + timer + notas. Persistido como `LearningPreference`.

---

## 11. Roadmap por fases

**Fase 0 — Diseño** ✅ (este documento)

**Fase 1 — Core**
- Auth (usuario/contraseña + MFA TOTP), sesiones seguras.
- `content/`: Domain/Topic/Concept/Lesson + seed inicial (roadmap NET-01 en adelante).
- `notes/`: editor Markdown, autosave, wikilinks básicos (sin export Obsidian aún).
- `evaluation/`: banco curado, tipos estructurados + auto-evaluación guiada.
- `retention/`: `ReviewSelector` (general/debilidades/olvidado/por tema), forgetting engine end-to-end.
- `dashboard/`: nivel por dominio, retención, repasos pendientes (sin fragmentación/connectivity aún).
- `focus/`: timer (4 modos), Focus Mode, session resume.
- `labs/` + `lab_orchestrator/`: 2-3 labs Docker reales, aislamiento de red, cleanup automático.
- Sin IA todavía (`AI_GENERATION_ENABLED=false`).

**Fase 2**
- `challenges/` + hints progresivos + `gamification/` (sobria).
- Knowledge graph navegable (lista jerárquica + grafo visual).
- `vulnerabilities/`: base de datos de vulnerabilidades.
- `errors/`: Error Memory completo.
- `fragmentation/`: fragmentation score + ejercicios integradores.
- Export/Import Obsidian.

**Fase 3**
- Extensión IA: generación de preguntas cuando el banco se agota, tutor socrático.
- Spaced repetition avanzado.
- `confidence/`: calibración de confianza.
- Transfer tests, Attack Path Visualizer.

**Fase 4**
- Labs multi-host, Active Directory, pivoting, topologías `network`.
- Blue/Purple team (Detection Lab).

**Fase 5**
- Synthetic unknown vulnerabilities, research labs, reversing, exploit dev controlado — aislamiento reforzado adicional.

---

## 12. Criterios de aceptación

| Criterio | Cómo se demuestra |
|---|---|
| No es "leer + quiz + completado" | Concepto con: lección → evaluación → `ErrorPattern` si falla → `ReviewSchedule` creado → nueva `QuestionVariant` en el siguiente repaso → `retention_score` recalculado visible en dashboard. (Fase 1) |
| Retención medible | Concepto aprendido → `ReviewSchedule` → variante nueva servida → respuesta registrada → `retention_score`/`forgetting_risk` actualizados → visible en dashboard. (Fase 1) |
| Error Memory funcional | Error repetido 2+ veces → `ErrorPattern` creado → siguiente `QuestionVariant` apunta a ese error → al resolverse, `ErrorPattern.status` cambia. (Fase 2) |
| Fragmentación detectable | Mastery individual alto en 3+ conceptos + falla en escenario integrador → `fragmentation_score` en banda HIGH → ejercicio integrador generado con esos conceptos exactos. (Fase 2) |
| "No sé qué estudiar" explica su elección | Endpoint devuelve una actividad + factor dominante del score, no una lista. (Fase 1) |
| Cold Case distingue comprensión de memorización | Lab completado ≥30 días atrás (simulable en test) → nueva instancia con `context_seed` distinto → walkthrough anterior no aplica literal. (Fase 1) |
| Aislamiento de labs verificable | Test de integración: contenedor de lab no alcanza red de API/DB; no sale a Internet sin declaración explícita. (Fase 1, bloqueante) |
| Atención/reentrada mínima viable | Continuar, No sé qué estudiar, Solo 5 minutos, Focus Mode, Count Up, Pomodoro configurable, recordatorio de pausa, resume exacto, recap contextual — todos presentes. (Fase 1) |
| Privacidad de datos | Endpoint para borrar historial completo; export JSON/Markdown funcional; ninguna métrica de foco se etiqueta como diagnóstico. (Fase 1) |

---

## 13. Riesgos y decisiones abiertas

- **Riesgo:** el orquestador de Docker, aunque aislado del API, sigue siendo el componente de mayor impacto si falla — punto de máximo escrutinio de seguridad en Fase 1.
- **Riesgo:** autoría de contenido (lecciones + preguntas + labs) es manual — el ritmo de la plataforma depende de cuánto contenido escriba el usuario antes de activar IA en Fase 3.
- **Decisión abierta:** proveedor de LLM para Fase 3 (no se fija ahora; el diseño solo deja el punto de extensión listo).
- **Decisión abierta:** hosting concreto del VPS (proveedor, specs de CPU/RAM con margen para correr labs Docker) — fuera del alcance de este spec de software.

---

## 14. ADRs iniciales

**ADR-001: Frontend React+Vite en vez de Next.js**
Contexto: app privada de un solo usuario autenticado, sin necesidad de SEO/SSR.
Decisión: React + Vite + React Router.
Consecuencia: menos complejidad de framework; se pierde SSR si en el futuro se necesitara contenido público indexable (no previsto).

**ADR-002: Monolito modular + worker aislado, no microservicios**
Contexto: un solo usuario, pero el orquestador de labs necesita un privilegio sensible (socket Docker).
Decisión: FastAPI monolito modular para todo excepto orquestación de labs, que vive en un worker separado sin exposición HTTP directa.
Consecuencia: separación de privilegios sin la complejidad operativa de microservicios completos.

**ADR-003: Motor de aprendizaje determinístico, no ML**
Contexto: el producto exige poder explicar siempre por qué se recomienda algo.
Decisión: fórmulas explícitas (curva de olvido, scoring ponderado) en vez de modelos entrenados.
Consecuencia: menos "inteligente" en el sentido de aprender patrones ocultos, pero cada número es trazable y ajustable a mano.

**ADR-004: Contenido pedagógico como código versionado (YAML + seed), no CMS/admin UI**
Contexto: un único autor (el usuario) que además es el estudiante.
Decisión: lecciones, preguntas y labs se definen en archivos YAML/Markdown en el repo, cargados por script de seed.
Consecuencia: versionado en git gratis y compatibilidad natural con export/import Obsidian; si en el futuro hay múltiples autores, se necesitará una UI de administración (no planeada aún).

**ADR-005: Banco de preguntas curado en Fase 1; generación por IA como extensión diferida**
Contexto: se quiere evitar costo/latencia de IA en el camino crítico mientras el banco es pequeño.
Decisión: `Question.source` distingue `curated`/`ai_generated`; generación IA solo se activa vía flag cuando el `QuestionVariantPicker` agota variantes, y pasa por aprobación manual antes de publicarse.
Consecuencia: Fase 1 funciona sin ninguna dependencia de API externa; el esquema de datos ya soporta la extensión sin migración futura.

# CyberLearn — Sub-plan A: Labs (orquestador + aislamiento + puerto publicado)

> **Depende de:** `docs/superpowers/specs/2026-08-13-cyberlearn-fase0-design.md` (§1 arquitectura, §4 threat model, §9 sistema de labs), y de `Concept` para relacionar labs con contenido.
> **Estado:** aprobado por el usuario el 2026-08-13.
> **Sub-plan B (siguiente, no cubierto aquí):** terminal web integrada (xterm.js + `docker exec` vía WebSockets) sobre esta misma base.

## 0. Decisión de acceso al lab (Sub-plan A)

El estudiante se conecta al servicio del lab con sus propias herramientas (netcat, Wireshark, Python) contra un **puerto publicado directamente en el host**, asignado por Docker de forma efímera por instancia. No hay terminal web en este sub-plan — eso es Sub-plan B.

## 1. Modelo de datos

```
Laboratory
  id: str (slug estable, ej. "net-tcp-flagbox-001"), PK
  title: str
  type: str (guided | semi_guided | black_box | mystery | research, sección 89 master prompt)
  difficulty: str
  duration_estimate_min: int
  docker_build_context: str (ruta relativa, ej. "labs/flagbox")
  hints: json (lista de {level, text})
  cpu_limit: str (ej. "0.5")
  memory_limit_mb: int
  max_lifetime_min: int
  cleanup_remove_volumes: bool

LaboratoryConcept (tabla puente)
  laboratory_id (FK), concept_id (FK)

LabInstance
  id: uuid, PK
  laboratory_id (FK), user_id (FK)
  status: requested | provisioning | running | stopped | destroyed | expired | failed
  container_id: str | null
  network_id: str | null
  host_port: int | null
  context_seed: json          (ej. {"flag_token": "a3f9..."})
  hints_used: int, default 0
  solved: bool, default false
  solved_at: datetime | null
  requested_at: datetime
  started_at: datetime | null
  destroyed_at: datetime | null
```

Sin tabla `LabAttempt` separada — con un solo usuario, cada `LabInstance` ya es efectivamente un intento (simplificación deliberada, igual patrón que otras ya documentadas en sub-planes previos).

## 2. Arquitectura y separación de privilegios

```
API (FastAPI, mismo proceso que siempre)
   │  nunca importa el SDK de Docker
   │  solo encola jobs con instance_id
   ▼
Redis (cola RQ, nombre de cola "labs")
   ▼
Worker (proceso Python separado — "rq worker labs")
   │  ÚNICO proceso con acceso a /var/run/docker.sock
   │  valida que docker_build_context esté dentro de labs/ (allowlist,
   │  nunca ejecuta rutas arbitrarias)
   ▼
Docker daemon del host
   → por instancia: red aislada (internal=True) + contenedor con
     límites de CPU/memoria + puerto publicado efímero
```

En desarrollo, el worker corre como proceso Python plano en el host (mismo patrón que `uvicorn` — no hay despliegue containerizado propio todavía), apuntando al Redis ya existente (puerto 6380).

**Jobs** (`worker/jobs.py`, funciones RQ):
```
provision_lab(instance_id)
  → genera context_seed (flag_token aleatorio)
  → crea red Docker aislada, labeled cyberlearn_instance_id=<id>
  → build/run del contenedor del lab, variables de entorno con context_seed,
    conectado a esa red, puerto publicado en 0 (Docker asigna uno libre)
  → aplica límites de recursos (mem_limit, nano_cpus)
  → inspecciona el contenedor para leer el host_port asignado
  → actualiza LabInstance: container_id, network_id, host_port,
    status=running, started_at

destroy_lab(instance_id)
  → detiene y elimina contenedor + red + (si aplica) volúmenes
  → verifica que no queden recursos con esa label (limpieza real, no asumida)
  → status=destroyed, destroyed_at

reset_lab(instance_id)
  → destroy_lab + provision_lab con un context_seed nuevo

sweep_expired_labs()  (bucle interno del worker, cada 60s)
  → LabInstance con status=running y now() > started_at + max_lifetime_min
    → destroy_lab
```

## 3. API

```
GET  /api/v1/labs                              → catálogo de Laboratory
POST /api/v1/labs/{lab_id}/instances             → crea LabInstance (status=requested), encola provision_lab
GET  /api/v1/labs/instances/{instance_id}          → estado actual (incluye host_port cuando running)
POST /api/v1/labs/instances/{instance_id}/reset      → encola reset_lab
POST /api/v1/labs/instances/{instance_id}/destroy      → encola destroy_lab
GET  /api/v1/labs/instances/{instance_id}/hints/{level} → revela un hint, incrementa hints_used
POST /api/v1/labs/instances/{instance_id}/submit          → body {flag}, compara contra context_seed.flag_token
```
Autenticadas, mismo patrón que los módulos anteriores.

## 4. Primer lab real: "FlagBox"

Servicio TCP custom, protocolo de texto simple por líneas (sin framing binario — mantiene el foco pedagógico en "lee el protocolo con Wireshark/netcat", no en parsing binario):

```
Al conectar: "FLAGBOX v1\r\n"

Comandos (uno por línea, terminados en \r\n):
  LOGIN <username>   → crea/reusa un usuario en memoria, responde "OK session=<n>\r\n"
  WHOAMI             → responde "USER <username> id=<n>\r\n" (o "ERR not logged in")
  GET <id>           → responde "NOTE <content>\r\n" o "ERR not found"
  (comando desconocido) → "ERR unknown command\r\n"
```

**La vulnerabilidad**: el servicio pre-siembra `notes[0]` con el contenido del flag (`context_seed.flag_token`, formato `FLAG{...}`), perteneciente a un usuario "admin", y `notes[1..N]` con contenido señuelo para otros usuarios. `GET <id>` **no valida que `id` pertenezca a la sesión autenticada** — es un índice directo al arreglo de notas. Cualquier usuario logueado con `GET 0` obtiene el flag. Es un IDOR clásico, expresado a nivel de protocolo crudo en vez de HTTP — encaja con NET-05 (TCP) y NET-09 (Análisis de Paquetes), sin requerir contenido de dominio Web.

Implementación: Python (`asyncio` TCP server), ~100 líneas, imagen `python:3.12-slim`, sin dependencias externas. `flag_token` inyectado por variable de entorno desde `context_seed`.

`Laboratory` YAML (`labs/flagbox/lab.yaml`, cargado por `seed_labs.py` — mismo patrón idempotente que `seed_content.py`/`seed_questions.py`):
```yaml
id: net-tcp-flagbox-001
title: "FlagBox"
type: black_box
difficulty: beginner
duration_estimate_min: 30
concept_slugs: [net-05-tcp-udp, net-09-packet-analysis]
docker_build_context: labs/flagbox
cpu_limit: "0.5"
memory_limit_mb: 128
max_lifetime_min: 120
cleanup_remove_volumes: true
hints:
  - level: 1
    text: "Conéctate al servicio con netcat y observa el banner. ¿Qué comandos acepta?"
  - level: 2
    text: "Captura el tráfico con Wireshark mientras interactúas — es texto plano por línea."
  - level: 3
    text: "Prueba el comando GET con distintos IDs. ¿El servicio valida que el ID te pertenece?"
  - level: 4
    text: "GET 0 es el registro más antiguo del sistema — ¿de quién podría ser?"
```

## 5. Controles de seguridad (verificados, no asumidos)

Reafirma y concreta el threat model de la sección 4 del spec de Fase 0:

| Control | Implementación |
|---|---|
| API no puede tocar Docker | El proceso API nunca importa el paquete `docker`; solo encola jobs RQ con `instance_id` (un string), nunca comandos. |
| Red de lab sin salida a Internet | Red Docker creada con `internal=True`. Verificado con un test de integración real: un contenedor en esa red no puede hacer `curl` a un host externo. |
| Red de lab no alcanza la API/DB/Redis | Red completamente separada de la red donde corren API/Postgres/Redis — verificado intentando conectar desde el contenedor del lab al puerto de Postgres y confirmando que falla. |
| Build de imágenes restringido | El worker valida que `docker_build_context` esté dentro de `labs/` antes de construir — nunca una ruta arbitraria de la request. |
| Límite de recursos por instancia | `mem_limit`/`nano_cpus` aplicados al crear el contenedor. |
| Limpieza real, no asumida | `destroy_lab` verifica que no queden contenedores/redes con la label `cyberlearn_instance_id` después de destruir. |
| Expiración automática | `sweep_expired_labs()` destruye instancias que superan `max_lifetime_min`, corre cada 60s en el worker. |
| Puerto publicado expuesto en un servidor con Internet | Decisión explícita del usuario (sección 0) — mitigado por los controles anteriores: aislamiento de red, límites de recursos, expiración automática, y el hecho de que el propio "lab" es hostil por diseño. |

## 6. Frontend

- `/labs`: catálogo (lista de `Laboratory`, con dificultad/duración/conceptos relacionados).
- `/labs/:labId`: crea instancia al entrar (o retoma una activa si el usuario ya tiene una para ese lab), hace polling de `GET /labs/instances/{id}` hasta `status=running`, muestra `host_port` con instrucciones de conexión (`nc <host> <port>`), hints progresivos, campo para enviar el flag, y botones Reset/Destroy.

## 7. Criterio de aceptación

- Crear una instancia de FlagBox termina en `status=running` con un `host_port` real, alcanzable con `nc localhost <port>` desde el propio host de desarrollo.
- Resolver el lab (`GET 0` tras `LOGIN`) obtiene el flag correcto, y enviarlo a `/submit` marca `solved=true`.
- Un contenedor dentro de la red del lab **no puede** alcanzar Internet ni la red de Postgres/Redis/API — probado con un test de integración real, no solo documentado.
- `reset` genera un `flag_token` distinto al anterior (nueva instancia, mismo lab).
- Una instancia con `max_lifetime_min` vencido se destruye sola sin intervención manual, y no quedan contenedores/redes huérfanos con su label.

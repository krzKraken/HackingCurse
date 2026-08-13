# CyberLearn — Sub-plan: Contenido + Lecciones (Fase 1)

> **Depende de:** `docs/superpowers/specs/2026-08-13-cyberlearn-fase0-design.md` (arquitectura general, modelo de datos §3, autoría de contenido §7.1).
> **Estado:** aprobado por el usuario el 2026-08-13.

## 0. Cambio respecto al spec de Fase 0

El ADR-004 del spec de Fase 0 asumía que el usuario sería el autor del contenido. Se corrige: **el asistente de IA escribe las lecciones**; el usuario es exclusivamente el estudiante. Esto no cambia el mecanismo (contenido como YAML versionado en git, cargado por script de seed) — solo cambia quién lo escribe.

## 1. Modelo de datos

Sin cambios respecto al spec de Fase 0 §3:

```
Domain 1──* Topic 1──* Concept
Concept *──* Concept   (ConceptRelationship: prerequisite | related | continues_with)
Concept 1──* Lesson
```

`Concept.slug` (string único, ej. `"arp"`) es el identificador estable usado en YAML, URLs y por otros módulos futuros para referenciar el concepto sin acoplarse a su ID interno.

## 2. Esquema de `Lesson`

Campos Markdown (todos `nullable`, se completan solo si aplican al concepto):

```
concepto            — definición desde fundamentos
como_funciona        — mecanismo interno, no solo la definición
por_que_importa       — relevancia en seguridad
visualizacion          — diagrama en texto/ASCII cuando ayude
ejemplo                 — caso concreto
comandos                  — solo después de explicar el mecanismo
errores_frecuentes         — errores típicos de quien aprende esto
regla_mental                 — frase corta memorable (🧠, sección 55 del master prompt)
perspectiva_ofensiva           — cómo se usa/abusa en pentesting
perspectiva_defensiva            — cómo se detecta/mitiga
```

**Fuera de alcance de este sub-plan** (se integran cuando su módulo exista, referenciando `Concept.slug`, no duplicando campos en `Lesson`):
- `error_personal` → módulo `errors/` (Error Memory)
- `mini_evaluacion` → módulo `evaluation/` (banco de preguntas)
- `laboratorio` → módulo `labs/`
- `repaso` → módulo `retention/`

## 3. Autoría y carga

```
content/networking/
├── net-01-fundamentals.yaml
├── net-02-ethernet-mac-arp.yaml
├── net-03-ipv4-subnetting.yaml
├── net-04-routing.yaml
├── net-05-tcp-udp.yaml
├── net-06-dns.yaml
├── net-07-dhcp.yaml
├── net-08-http-tls.yaml
├── net-09-packet-analysis.yaml
└── net-10-nmap.yaml
```

Cada archivo declara: `domain`, `topic`, `concept` (slug, título, nivel sugerido), `lesson` (los 10 campos §2), y `relationships` (lista de `{type, target_slug}`).

Script `backend/scripts/seed_content.py`: recorre `content/**/*.yaml`, hace upsert de Domain/Topic/Concept/Lesson por `slug` (idempotente — se puede correr múltiples veces sin duplicar), y crea `ConceptRelationship` **después** de que todos los Concepts existan (dos pasadas: 1) upsert de conceptos, 2) resolución de relaciones), porque `net-02` referencia prerequisitos que viven en otros archivos.

## 4. API

```
GET /api/v1/content/domains
  → [{slug, name, topics: [{slug, name, concepts: [{slug, name}]}]}]

GET /api/v1/content/concepts/{slug}
  → {
      slug, name, level,
      lesson: { ...los 10 campos },
      relationships: {
        prerequisites: [{slug, name}],
        related: [{slug, name}],
        continues_with: [{slug, name}]
      }
    }
```

Ambos son rutas públicas dentro del perímetro autenticado (usan `get_current_user`, spec Fase 0 §1 — todo `/api/v1/*` excepto `/auth/*` requiere sesión).

## 5. Frontend

`frontend/src/features/lessons/`:
- `LessonPage.tsx` — obtiene el concepto por slug (ruta `/lessons/:slug`), renderiza los 10 campos Markdown en orden fijo (solo los que tengan contenido), y al final una sección "Relaciones" con tres listas (prerequisitos / relacionados / continúa) como links a otras lecciones.
- Reutiliza un helper `renderMarkdown` simple (sin editor, solo lectura) — no confundir con el editor de notas (sub-plan futuro).

## 6. Contenido real: NET-01 a NET-10

Se escriben las 10 lecciones completas del roadmap de Networking (master prompt §144), con relaciones de prerequisito encadenadas según el grafo de ejemplo del propio documento (§7): `IPv4 → Subnetting → Routing → ARP → TCP → Nmap → Enumeración → Pivoting` se traduce a relaciones entre NET-01..NET-10 donde corresponda (ej. NET-02 (Ethernet/MAC/ARP) tiene como prerequisito NET-01; NET-03 (IPv4/Subnetting) prerequisito de NET-04 (Routing); NET-05 (TCP/UDP) prerequisito de NET-08 (HTTP/TLS) y de NET-10 (Nmap); etc.).

## 7. Criterio de aceptación

- Correr `seed_content.py` dos veces seguidas no duplica filas (idempotencia).
- `GET /api/v1/content/concepts/arp` devuelve la lección de ARP con sus prerequisitos (`ethernet-mac`, no `ipv4` directamente — ARP depende de Ethernet/MAC, IPv4 es prerequisito de Routing, no de ARP).
- Las 10 lecciones son navegables desde `/lessons/net-01-fundamentals` siguiendo los links de "continúa con" hasta `net-10-nmap`.
- Contenido técnicamente correcto y verificable (no relleno) — cada lección debe poder usarse para aprender el tema de verdad, no solo para probar que el sistema funciona.

# CyberLearn — Sub-plan: Dashboard (Fase 1)

> **Depende de:** `docs/superpowers/specs/2026-08-13-cyberlearn-fase0-design.md` (§74 Dashboard) y de los datos ya producidos por los sub-planes de Contenido, Notas y Banco de preguntas + Motor de retención.
> **Estado:** aprobado por el usuario el 2026-08-13.

## 0. Alcance

El dashboard completo del master prompt (§74) incluye widgets que dependen de módulos que todavía no existen: fragmentación, knowledge connectivity, error memory, labs recomendados, tiempo de práctica/foco, pistas usadas, retos, achievements, independence/transfer/methodology scores. Ninguno de esos módulos está construido aún (ver `PROJECT_MASTER_CHECKLIST.md`).

Este sub-plan construye:
1. Los widgets con **datos reales**, agregados de lo que ya existe (`ConceptMastery`, `ReviewSchedule`, `ReviewItem`, `Domain`/`Topic`/`Concept`).
2. Tarjetas estáticas **"Próximamente"** para los widgets que dependen de módulos futuros — visual completo desde ahora, sin fingir datos.

## 1. Datos reales agregados

- **Nivel global**: promedio de `ConceptMastery.mastery_score` sobre todos los conceptos que el usuario ya ha practicado (con fila en `ConceptMastery`).
- **Nivel por dominio**: igual que el global pero agrupado por `Domain`, más `studied_count`/`total_count` (conceptos con `ConceptMastery` vs. total de conceptos con preguntas en ese dominio).
- **Repasos vencidos**: cuenta de `ReviewSchedule.next_due_at <= now()`.
- **Conceptos débiles**: los 5 `ConceptMastery` con `mastery_score` más bajo.
- **Conceptos más vencidos**: los 5 `ReviewSchedule` con `next_due_at` más antiguo respecto a ahora.
- **Últimos repasos**: los últimos 10 `ReviewItem` con `outcome` no nulo, más recientes primero.

## 2. API

```
GET /api/v1/dashboard/summary
  → {
      global_mastery: float,
      domains: [{slug, name, mastery_percent, studied_count, total_count}],
      reviews_due_count: int,
      weak_concepts: [{slug, name, mastery_score}],
      overdue_concepts: [{slug, name, next_due_at}],
      recent_activity: [{concept_slug, concept_name, outcome, answered_at}]
    }
```
Ruta autenticada, mismo patrón que `content`/`notes`/`reviews`.

## 3. Frontend

Ruta `/dashboard` (separada de `/`, que sigue siendo el placeholder "Dashboard (placeholder)" — este sub-plan no lo reemplaza, decisión del usuario):

- Tarjeta de nivel global.
- Lista de nivel por dominio (barra simple de texto/porcentaje, sin gráficos SVG — YAGNI, se puede mejorar visualmente después).
- "Repasos vencidos: N" con link a `/review`.
- Lista de conceptos débiles (link a cada lección).
- Lista de últimos repasos (concepto + resultado + cuándo).
- Tarjetas estáticas "Próximamente": Fragmentación, Knowledge Connectivity, Error Memory, Labs recomendados, Tiempo de práctica, Pistas usadas, Logros, Independence/Transfer/Methodology Score.

## 4. Criterio de aceptación

- Responder preguntas reales en `/review` y luego visitar `/dashboard` refleja los cambios (mastery/repasos vencidos actualizados) sin necesidad de reiniciar nada.
- Un dominio sin ningún concepto estudiado aparece con `mastery_percent = 0` y `studied_count = 0`, no con error ni con NaN.
- Las tarjetas "Próximamente" son visualmente distinguibles de los widgets reales (para no confundir al usuario sobre qué es dato real).

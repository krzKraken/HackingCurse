# Fase 2: Challenges + Hints Progresivos — Diseño

> Master prompt §33-38 (métricas pedagógicas, Hint Dependency, Independence Score),
> §114-116 (Achievements/Challenge mode), §137 (modelos `Challenge`/`ChallengeAttempt`/`Hint`/`HintUsage`).

## Objetivo

Cerrar dos huecos que quedaron pendientes de Fase 1:
1. Los "Challenges" del master prompt existen como concepto — se resuelven reutilizando
   el motor de labs ya construido (Sub-plan A/B), sin infraestructura nueva.
2. Las métricas de dependencia de pistas (Hint Dependency, Independence Score) que hoy
   figuran como placeholders "Próximamente" en el Dashboard pasan a ser reales.

## Decisiones de diseño (confirmadas con el usuario)

1. **"Challenge" no es un modelo nuevo.** `Laboratory.type` ya existe como columna de
   texto libre (`String(32)`, usado hoy con el valor `"black_box"` para FlagBox). Un
   futuro laboratorio con `type="challenge"` es, para todo el sistema, un `Laboratory`
   normal — mismo orquestador Docker, mismo modelo `LabInstance`, mismos hints. No se
   crean `Challenge`/`ChallengeAttempt`/`Hint`/`HintUsage` como tablas separadas (el
   master prompt los lista, pero serían duplicar exactamente lo que `Laboratory`/
   `LabInstance` ya hacen — YAGNI). Esta decisión no requiere ningún cambio de código;
   queda documentada aquí para que quede explícito por qué el checklist puede marcar
   "Challenges" como cubierto sin tocar `app/models/lab.py`.
2. **El alcance real de este sub-plan es Hint Dependency + Independence Score**,
   mostrados en el Dashboard existente (no una página nueva), reemplazando los
   placeholders "Pistas usadas" e "Independence / Transfer / Methodology Score" (este
   último se reduce a solo "Transfer / Methodology Score", que sigue pendiente).
3. Ambas métricas se calculan a partir de datos que **ya existen**:
   `LabInstance.hints_used` (nivel más alto de pista revelado, entero) y
   `LabInstance.solved` (booleano). No hace falta agregar columnas ni migraciones.

## Componentes

### `backend/app/dashboard/service.py` (modificado)
Nueva función:

```python
def get_hint_dependency(db: Session, user_id) -> dict:
    """Returns {"breakdown": {hints_used: count}, "independence_score": float | None}
    over the user's solved LabInstance rows. independence_score is the percentage
    solved with hints_used == 0; None if the user has solved zero labs."""
```

Implementación: `db.query(LabInstance).filter(LabInstance.user_id == user_id, LabInstance.solved == True)`,
agrupar en Python por `hints_used` (los niveles de hint son data-driven por laboratorio,
no hay un máximo fijo — algunos labs pueden tener 1 hint, otros 4). Si no hay filas
solved, `independence_score` es `None` (no `0.0`, para no sugerir falsamente "0% de
independencia" cuando en realidad no hay datos todavía).

### `backend/app/dashboard/schemas.py` (modificado)
`DashboardSummary` gana dos campos:

```python
hint_dependency: dict[int, int]  # {0: 21, 1: 12, 2: 6, ...}
independence_score: float | None  # porcentaje 0-100, o None sin datos
```

### `backend/app/dashboard/service.py` — `get_summary()` (modificado)
`get_summary(db, user_id)` es la única función que arma el dict devuelto por el router
(`app/dashboard/router.py` no cambia — ya delega todo a `service.get_summary`). Se le
agregan dos entradas que llaman a `get_hint_dependency` y desempacan su resultado:

```python
def get_summary(db: Session, user_id) -> dict:
    hint_dependency = get_hint_dependency(db, user_id)
    return {
        "global_mastery": get_global_mastery(db, user_id),
        "domains": get_domains_summary(db, user_id),
        "reviews_due_count": get_reviews_due_count(db, user_id),
        "weak_concepts": get_weak_concepts(db, user_id),
        "overdue_concepts": get_overdue_concepts(db, user_id),
        "recent_activity": get_recent_activity(db, user_id),
        "hint_dependency": hint_dependency["breakdown"],
        "independence_score": hint_dependency["independence_score"],
    }
```

### `frontend/src/lib/api.ts` (modificado)
`DashboardSummary` type gana `hint_dependency: Record<number, number>` e
`independence_score: number | null`.

### `frontend/src/features/dashboard/DashboardPage.tsx` (modificado)
Nueva sección antes de "Próximamente":

```tsx
<section>
  <h2>Uso de pistas en labs</h2>
  {summary.independence_score === null ? (
    <p>Todavía no resolviste ningún lab.</p>
  ) : (
    <>
      <p>Independence Score: {summary.independence_score.toFixed(0)}%</p>
      <ul>
        {Object.entries(summary.hint_dependency)
          .sort(([a], [b]) => Number(a) - Number(b))
          .map(([level, count]) => (
            <li key={level}>
              {level === "0" ? "Sin pistas" : `Pista ${level}`}: {count}
            </li>
          ))}
      </ul>
    </>
  )}
</section>
```

`COMING_SOON` pierde `"Pistas usadas"` e `"Independence / Transfer / Methodology Score"`
se reemplaza por `"Transfer / Methodology Score"`.

## Testing

DB-level, sin Docker (a diferencia de Sub-plan A/B, esto no toca contenedores). Ya
existen `backend/tests/dashboard/test_service.py` y `backend/tests/dashboard/test_router.py`
— se extienden, no se crean archivos nuevos:
- En `test_service.py`: seedear varias `LabInstance` con distintos `hints_used`/`solved`
  para un usuario, verificar que `get_hint_dependency` devuelve el breakdown correcto y
  el `independence_score` esperado. Caso aparte: usuario sin labs resueltos →
  `independence_score is None`.
- En `test_router.py`: extender el test existente de `GET /summary` para verificar que
  la respuesta incluye `hint_dependency` e `independence_score`.

## Fuera de alcance (explícitamente)

- Modelos `Challenge`/`ChallengeAttempt`/`Hint`/`HintUsage` separados — cubiertos
  conceptualmente por `Laboratory.type`, sin código nuevo (ver decisión 1).
- Transfer Score, Methodology Score, First Principles Score (métricas pedagógicas
  del master prompt §33 no cubiertas por este sub-plan — quedan en "Próximamente").
- Evolución mensual del Hint Dependency (el master prompt menciona "mostrar evolución
  mensual" en §38) — el dashboard actual no tiene series temporales para ninguna
  métrica; agregar eso sería un sub-plan propio de visualización histórica, no algo
  específico de hints.
- Achievements/gamificación (§114-115) — sub-plan separado ya listado en el checklist
  de Fase 2 ("Gamificación (sobria)").

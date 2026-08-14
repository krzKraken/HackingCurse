# Fase 2: Gamificación (sobria) — Diseño

> Master prompt §60 (no-shame design), §114 (Gamificación sobria y profesional:
> XP, niveles, achievements, badges, milestones), §115 (Achievements basados en
> habilidad, no solo completar contenido).

## Objetivo

Agregar Achievements + XP/niveles al Dashboard, reforzando logros de habilidad
real (labs sin pistas, mastery alta, repasos perfectos) en vez de solo
completar contenido, sin ninguna mecánica de presión (sin streaks que se
"pierden", sin XP negativo, sin comparación social — el usuario es el único
usuario del sistema).

## Decisiones de diseño (confirmadas con el usuario)

1. **Alcance v1: Achievements + XP/niveles.** Sin skill tree ni "retos"
   (challenges) como mecánica de gamificación separada — "Challenges" ya
   quedó cubierto en el sub-plan anterior vía `Laboratory.type`. Badges/
   milestones se consideran sinónimos de "achievement" en esta implementación,
   no una entidad adicional.
2. **Detección al cargar el Dashboard, no por evento.** Una función
   `sync_achievements(db, user_id)` se invoca una sola vez desde
   `get_summary()` (mismo punto de integración que ya usan Independence
   Score, mastery, etc.), evalúa todas las condiciones contra el estado
   actual de la DB y persiste las que recién se cumplen. No se instrumenta
   `labs/`, `reviews/` ni `focus/` — esos módulos no cambian. Consecuencia
   aceptada: un logro aparece "desbloqueado" la próxima vez que se visita
   `/dashboard`, no en el instante exacto en que se cumple la condición.
3. **XP se calcula, no se almacena como contador.** `xp_total` se deriva en
   cada carga a partir de: reviews correctos (`ReviewItem.outcome ==
   correct`), labs resueltos (`LabInstance.solved == True`, con bono inverso
   a `hints_used`), y achievements desbloqueados (`UserAchievement`). Evita
   bugs de doble conteo y mantiene el mismo patrón que el resto de
   `dashboard/service.py` (todo se computa fresco desde las tablas fuente,
   nada es un contador mutable).
4. **No-shame:** no hay XP negativo, no hay penalización por respuestas
   incorrectas, no hay racha que se "pierde". El catálogo de achievements
   solo suma.

## Catálogo v1 (7 achievements)

| Key | Título | Condición | XP |
|---|---|---|---|
| `first_shell` | First Shell | ≥1 `LabInstance` con `solved=True` | 20 |
| `no_hint_required` | No Hint Required | ≥1 `LabInstance` con `solved=True, hints_used=0` | 15 |
| `independent_mind` | Independent Mind | ≥5 `LabInstance` con `solved=True, hints_used=0` | 50 |
| `persistent` | Persistent | ≥10 `LabInstance` con `solved=True` | 40 |
| `perfect_recall` | Perfect Recall | ≥1 `ReviewSession` con ≥5 `ReviewItem` respondidos y el 100% con `outcome=correct` | 25 |
| `domain_mastery` | Domain Mastery | algún dominio con promedio de `ConceptMastery.mastery_score` (entre los conceptos estudiados de ese dominio) ≥90 | 60 |
| `deep_focus` | Deep Focus | suma de `LearningSession.active_time_sec` del usuario ≥36000 (10h) | 30 |

Este catálogo es fácil de extender después: cada entrada nueva es una función
Python + una fila en una lista, sin migración (ver Componentes).

## Fórmula de XP y niveles

```
xp_from_reviews = 2 * count(ReviewItem donde outcome == correct, vía su ReviewSession.user_id)
xp_from_labs = sum(max(10, 30 - 5 * hints_used) por cada LabInstance con solved=True)
xp_from_achievements = sum(xp_value de cada UserAchievement del usuario)
xp_total = xp_from_reviews + xp_from_labs + xp_from_achievements
level = 1 + xp_total // 100
```

## Componentes

### Migración: `UserAchievement` (única tabla nueva)
```python
class UserAchievement(Base):
    __tablename__ = "user_achievements"
    __table_args__ = (UniqueConstraint("user_id", "achievement_key", name="uq_user_achievement"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    achievement_key: Mapped[str] = mapped_column(String(64), nullable=False)
    unlocked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```
Vive en un nuevo `backend/app/models/gamification.py` (modelo, no lógica).

### `backend/app/gamification/achievements.py` (nuevo)
Catálogo estático: una lista de `Achievement` (dataclass: `key, title,
description, xp_value, check: Callable[[Session, UUID], bool]`). Cada `check`
es una query corta y autocontenida contra `LabInstance`/`ReviewSession`+
`ReviewItem`/`ConceptMastery` (vía `Concept`→`Topic`→`Domain`)/`LearningSession`
— sin depender de `app/dashboard/service.py` (evita import circular: el
dashboard va a importar `gamification`, no al revés).

### `backend/app/gamification/service.py` (nuevo)
- `sync_achievements(db, user_id) -> list[str]`: para cada `Achievement` del
  catálogo cuya key no esté ya en `UserAchievement` para ese usuario, evalúa
  `check(db, user_id)`; si es `True`, inserta la fila con `unlocked_at=now()`.
  Devuelve las keys recién insertadas (no usado por el Dashboard en v1, pero
  es la interfaz natural para una futura notificación in-app).
- `get_xp_summary(db, user_id) -> dict`: calcula `xp_total`/`level` con la
  fórmula de arriba y arma la lista de achievements desbloqueados
  (`{key, title, description, xp_value, unlocked_at}`, ordenada por
  `unlocked_at` descendente) leyendo `UserAchievement` y cruzando contra el
  catálogo para título/descripción/xp_value.

### `app/dashboard/service.py` — `get_summary()` (modificado)
Al principio de `get_summary`, llama `sync_achievements(db, user_id)` (ignora
el resultado — no hay notificación en v1), luego `get_xp_summary(db, user_id)`
y agrega sus tres campos al dict devuelto.

### `backend/app/dashboard/schemas.py` (modificado)
`DashboardSummary` gana:
```python
xp_total: int
level: int
achievements: list[AchievementSummary]  # AchievementSummary: key, title, description, xp_value, unlocked_at
```

### Frontend
`DashboardSummary` type en `api.ts` espeja lo anterior. Nueva sección
"Logros" en `DashboardPage.tsx`, colocada junto a "Uso de pistas en labs":
nivel + XP arriba, debajo una lista de **solo los achievements
desbloqueados** (título, descripción, fecha) — sin lista de pendientes ni
barras de progreso, para no introducir la presión que el master prompt pide
evitar explícitamente (§60).

## Testing

Mismo patrón que el sub-plan de Hint Dependency: tests de servicio contra una
DB real (sin mocks), sembrando filas de `LabInstance`/`ReviewSession`/
`ReviewItem`/`ConceptMastery`/`LearningSession` con distintos valores y
verificando qué achievements se desbloquean y qué XP/nivel resulta. Casos
límite explícitos: usuario sin actividad (`xp_total == 0`, `level == 1`,
`achievements == []`), un achievement justo en el borde de su condición
(ej. exactamente 5 labs sin pistas), y `sync_achievements` llamado dos veces
seguidas no duplica filas (constraint único + verificación de idempotencia).

## Fuera de alcance (explícitamente)

- Skill tree, "retos" como mecánica separada de gamificación.
- Notificación in-app en el momento del desbloqueo (queda para cuando/si se
  decide hacer detección por evento en vez de al cargar el Dashboard).
- Lista de achievements bloqueados con progreso — decisión explícita de
  diseño para evitar presión (§60), no una limitación técnica.
- Comparación social / leaderboards — no aplica, app de un solo usuario.

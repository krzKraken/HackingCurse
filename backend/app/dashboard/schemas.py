from datetime import datetime

from pydantic import BaseModel


class DomainMasterySummary(BaseModel):
    slug: str
    name: str
    mastery_percent: float
    studied_count: int
    total_count: int


class ConceptScoreSummary(BaseModel):
    slug: str
    name: str
    mastery_score: float


class OverdueConceptSummary(BaseModel):
    slug: str
    name: str
    next_due_at: datetime


class RecentActivityItem(BaseModel):
    concept_slug: str
    concept_name: str
    outcome: str
    answered_at: datetime


class AchievementSummary(BaseModel):
    key: str
    title: str
    description: str
    xp_value: int
    unlocked_at: datetime


class DashboardSummary(BaseModel):
    global_mastery: float
    domains: list[DomainMasterySummary]
    reviews_due_count: int
    weak_concepts: list[ConceptScoreSummary]
    overdue_concepts: list[OverdueConceptSummary]
    recent_activity: list[RecentActivityItem]
    hint_dependency: dict[int, int]
    independence_score: float | None
    xp_total: int
    level: int
    achievements: list[AchievementSummary]

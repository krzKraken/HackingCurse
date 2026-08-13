import math
from datetime import datetime, timedelta

THRESHOLD = 0.85
MIN_STABILITY_DAYS = 0.5
INITIAL_STABILITY_DAYS = 1 / -math.log(THRESHOLD)

OUTCOME_FACTORS = {"correct": 1.6, "partial": 1.1, "incorrect": 0.5}
OUTCOME_SCORES = {"correct": 100.0, "partial": 50.0, "incorrect": 0.0}


def retention(stability_days: float, days_since_tested: float) -> float:
    if stability_days <= 0:
        return 0.0
    return math.exp(-days_since_tested / stability_days)


def forgetting_risk(stability_days: float, days_since_tested: float) -> float:
    return 1 - retention(stability_days, days_since_tested)


def update_stability(old_stability_days: float, outcome: str) -> float:
    factor = OUTCOME_FACTORS[outcome]
    return max(old_stability_days * factor, MIN_STABILITY_DAYS)


def compute_next_due_at(stability_days: float, now: datetime) -> datetime:
    days_until_threshold = -stability_days * math.log(THRESHOLD)
    return now + timedelta(days=days_until_threshold)


def rolling_mastery_score(outcomes: list[str]) -> float:
    if not outcomes:
        return 0.0
    return sum(OUTCOME_SCORES[o] for o in outcomes) / len(outcomes)


def suggest_difficulty_delta(accuracy_rolling: float, consecutive_failures: int) -> int:
    if accuracy_rolling >= 0.8:
        return 1
    if consecutive_failures >= 3:
        return -1
    return 0

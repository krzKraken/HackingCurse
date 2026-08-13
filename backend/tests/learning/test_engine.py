import math
from datetime import datetime, timezone

from app.learning import engine


def test_retention_at_zero_days_is_one():
    assert engine.retention(stability_days=10, days_since_tested=0) == 1.0


def test_retention_decays_over_time():
    r1 = engine.retention(stability_days=10, days_since_tested=5)
    r2 = engine.retention(stability_days=10, days_since_tested=10)
    assert r1 > r2


def test_forgetting_risk_is_complement_of_retention():
    risk = engine.forgetting_risk(stability_days=10, days_since_tested=5)
    assert math.isclose(risk, 1 - engine.retention(10, 5))


def test_update_stability_increases_on_correct():
    new = engine.update_stability(old_stability_days=5, outcome="correct")
    assert new > 5


def test_update_stability_decreases_on_incorrect_but_floors():
    new = engine.update_stability(old_stability_days=1, outcome="incorrect")
    assert new >= engine.MIN_STABILITY_DAYS


def test_compute_next_due_at_initial_stability_is_about_one_day():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    due = engine.compute_next_due_at(engine.INITIAL_STABILITY_DAYS, now)
    delta_days = (due - now).total_seconds() / 86400
    assert math.isclose(delta_days, 1.0, rel_tol=0.01)


def test_rolling_mastery_score_averages_outcomes():
    score = engine.rolling_mastery_score(["correct", "correct", "incorrect"])
    assert math.isclose(score, (100 + 100 + 0) / 3)


def test_rolling_mastery_score_empty_is_zero():
    assert engine.rolling_mastery_score([]) == 0.0


def test_suggest_difficulty_delta_up_when_accuracy_high():
    assert engine.suggest_difficulty_delta(accuracy_rolling=0.9, consecutive_failures=0) == 1


def test_suggest_difficulty_delta_down_after_three_failures():
    assert engine.suggest_difficulty_delta(accuracy_rolling=0.2, consecutive_failures=3) == -1


def test_suggest_difficulty_delta_neutral_otherwise():
    assert engine.suggest_difficulty_delta(accuracy_rolling=0.5, consecutive_failures=1) == 0

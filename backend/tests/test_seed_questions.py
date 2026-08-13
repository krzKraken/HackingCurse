import os
import tempfile

import yaml

from app.models.content import Concept, Domain, Topic
from app.models.question import Question, QuestionVariant
from scripts.seed_questions import seed_questions

QUESTIONS_YAML = {
    "concept_slug": "net-01",
    "questions": [
        {
            "type": "multiple_choice",
            "difficulty": 1,
            "variants": [{"prompt_markdown": "¿2+2?", "options": ["3", "4"], "correct_option_index": 1}],
        },
        {
            "type": "true_false",
            "difficulty": 1,
            "variants": [{"prompt_markdown": "El cielo es azul", "correct_bool": True}],
        },
    ],
}


def _seed_concept(db, slug="net-01"):
    domain = Domain(slug="networking", name="Networking")
    db.add(domain)
    db.flush()
    topic = Topic(domain_id=domain.id, slug="fundamentals", name="Fundamentos")
    db.add(topic)
    db.flush()
    concept = Concept(topic_id=topic.id, slug=slug, name=slug)
    db.add(concept)
    db.commit()
    return concept


def _write_content_dir(tmpdir, filename, data):
    content_dir = os.path.join(tmpdir, "content", "networking")
    os.makedirs(content_dir, exist_ok=True)
    with open(os.path.join(content_dir, filename), "w") as f:
        yaml.safe_dump(data, f)
    return os.path.join(tmpdir, "content")


def test_seed_questions_creates_questions_and_variants(db_session):
    _seed_concept(db_session)
    with tempfile.TemporaryDirectory() as tmpdir:
        content_dir = _write_content_dir(tmpdir, "net-01.questions.yaml", QUESTIONS_YAML)
        seed_questions(content_dir)

    assert db_session.query(Question).count() == 2
    assert db_session.query(QuestionVariant).count() == 2


def test_seed_questions_is_idempotent(db_session):
    _seed_concept(db_session)
    with tempfile.TemporaryDirectory() as tmpdir:
        content_dir = _write_content_dir(tmpdir, "net-01.questions.yaml", QUESTIONS_YAML)
        seed_questions(content_dir)
        seed_questions(content_dir)

    assert db_session.query(Question).count() == 2

import glob

import yaml
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.content import Concept
from app.models.question import Question, QuestionStatus, QuestionType, QuestionVariant


def _upsert_question(db: Session, concept: Concept, q_data: dict) -> Question:
    q_type = QuestionType(q_data["type"])
    first_prompt = q_data["variants"][0]["prompt_markdown"]

    existing = (
        db.query(Question)
        .join(QuestionVariant, QuestionVariant.question_id == Question.id)
        .filter(
            Question.concept_id == concept.id,
            Question.type == q_type,
            QuestionVariant.prompt_markdown == first_prompt,
        )
        .first()
    )
    if existing is not None:
        return existing

    question = Question(
        concept_id=concept.id,
        type=q_type,
        difficulty=q_data.get("difficulty", 1),
        evaluation_criteria=q_data.get("evaluation_criteria"),
        expected_answer=q_data.get("expected_answer"),
        status=QuestionStatus.published,
    )
    db.add(question)
    db.flush()

    for v in q_data["variants"]:
        db.add(
            QuestionVariant(
                question_id=question.id,
                prompt_markdown=v["prompt_markdown"],
                options=v.get("options"),
                correct_option_index=v.get("correct_option_index"),
                correct_bool=v.get("correct_bool"),
            )
        )
    return question


def seed_questions(content_dir: str = "content") -> None:
    db = SessionLocal()
    try:
        paths = sorted(glob.glob(f"{content_dir}/**/*.questions.yaml", recursive=True))
        count = 0
        for path in paths:
            with open(path) as f:
                data = yaml.safe_load(f)
            concept = db.query(Concept).filter(Concept.slug == data["concept_slug"]).first()
            if concept is None:
                print(f"WARNING: unknown concept_slug '{data['concept_slug']}' in {path}")
                continue
            for q_data in data["questions"]:
                _upsert_question(db, concept, q_data)
                count += 1
        db.commit()
        print(f"Seeded {count} questions from {content_dir}/")
    finally:
        db.close()


if __name__ == "__main__":
    seed_questions()

import glob

import yaml
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.content import Concept
from app.models.lab import Laboratory, LaboratoryConcept


def _upsert_laboratory(db: Session, data: dict) -> Laboratory:
    lab = db.query(Laboratory).filter(Laboratory.id == data["id"]).first()
    if lab is None:
        lab = Laboratory(id=data["id"])
        db.add(lab)

    lab.title = data["title"]
    lab.type = data["type"]
    lab.difficulty = data["difficulty"]
    lab.duration_estimate_min = data["duration_estimate_min"]
    lab.docker_build_context = data["docker_build_context"]
    lab.hints = data.get("hints", [])
    lab.cpu_limit = data["cpu_limit"]
    lab.memory_limit_mb = data["memory_limit_mb"]
    lab.max_lifetime_min = data["max_lifetime_min"]
    lab.cleanup_remove_volumes = data.get("cleanup_remove_volumes", True)
    db.flush()
    return lab


def seed_labs(labs_dir: str = "labs") -> None:
    db = SessionLocal()
    try:
        paths = sorted(glob.glob(f"{labs_dir}/**/lab.yaml", recursive=True))
        for path in paths:
            with open(path) as f:
                data = yaml.safe_load(f)
            lab = _upsert_laboratory(db, data)

            db.query(LaboratoryConcept).filter(LaboratoryConcept.laboratory_id == lab.id).delete()
            for slug in data.get("concept_slugs", []):
                concept = db.query(Concept).filter(Concept.slug == slug).first()
                if concept is None:
                    print(f"WARNING: unknown concept_slug '{slug}' in {path}")
                    continue
                db.add(LaboratoryConcept(laboratory_id=lab.id, concept_id=concept.id))
        db.commit()
        print(f"Seeded {len(paths)} laboratories from {labs_dir}/")
    finally:
        db.close()


if __name__ == "__main__":
    seed_labs()

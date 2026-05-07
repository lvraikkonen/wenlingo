from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.api.deps import get_db_session
from app.domain.models import StudentProfile
from app.domain.seed import seed_demo_data

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/demo-login")
def demo_login(session: Session = Depends(get_db_session)):
    parent = seed_demo_data(session)
    students = session.exec(select(StudentProfile).where(StudentProfile.parent_id == parent.id)).all()
    return {"parent": parent, "students": students}

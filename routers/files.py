import os

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from core.db import get_sqlite
from core.deps import require_role
from core.upload import PRIVATE, PRIVATE_DIR

router = APIRouter()

OWNER_SQL = {
    "resumes": "SELECT user_id FROM resumes WHERE resume_path=?",
    "resume_photos": "SELECT user_id FROM resumes WHERE photo_path=?",
    "profile_resumes": "SELECT user_id FROM seeker_profiles WHERE resume_path=?",
    "biz_docs": "SELECT user_id FROM companies WHERE biz_doc_path=?",
}


def _allowed(conn, user, area, owner_id):
    if user["role"] == "operator" or user["id"] == owner_id:
        return True
    if area == "biz_docs":
        return False
    if user["role"] == "manager":
        return bool(conn.execute(
            "SELECT 1 FROM manager_assignments WHERE manager_user_id=? AND seeker_user_id=?",
            (user["id"], owner_id),
        ).fetchone())
    if user["role"] == "company":
        # 자사 공고 지원자만 열람
        return bool(conn.execute(
            "SELECT 1 FROM candidacies c "
            "JOIN job_postings j ON c.job_id=j.id "
            "JOIN companies co ON j.company_id=co.id "
            "WHERE co.user_id=? AND c.seeker_user_id=?",
            (user["id"], owner_id),
        ).fetchone())
    return False


@router.get("/files/{area}/{name}")
async def serve_file(request: Request, area: str, name: str):
    user = require_role(request, "seeker", "company", "manager", "operator")
    if area not in PRIVATE or "/" in name or name.startswith("."):
        raise HTTPException(status_code=404)
    path = os.path.join(PRIVATE_DIR, area, name)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404)
    conn = get_sqlite()
    try:
        row = conn.execute(OWNER_SQL[area], (f"/files/{area}/{name}",)).fetchone()
        if not row or not _allowed(conn, user, area, row["user_id"]):
            raise HTTPException(status_code=404)
    finally:
        conn.close()
    return FileResponse(path)

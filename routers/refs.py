from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from core.db import get_sqlite
from core.deps import require_role

router = APIRouter()

ROLES = ("seeker", "company", "manager", "operator")


@router.get("/api/refs/certs")
async def search_certs(request: Request, q: str = Query("")):
    require_role(request, *ROLES)
    # 음성 인식 결과는 띄어쓰기가 일정하지 않아 공백을 제외하고 비교함
    q = q.replace(" ", "")
    if not q:
        return JSONResponse([])
    conn = get_sqlite()
    try:
        rows = conn.execute(
            """SELECT name, org FROM ref_certs WHERE REPLACE(name, ' ', '') LIKE ?
               ORDER BY CASE WHEN REPLACE(name, ' ', '') LIKE ? THEN 0 ELSE 1 END, name LIMIT 10""",
            (f"%{q}%", f"{q}%"),
        ).fetchall()
    finally:
        conn.close()
    return JSONResponse([{"name": r["name"], "org": r["org"]} for r in rows])


@router.get("/api/refs/schools")
async def search_schools(request: Request, q: str = Query("")):
    require_role(request, *ROLES)
    q = q.replace(" ", "")
    if not q:
        return JSONResponse([])
    conn = get_sqlite()
    try:
        rows = conn.execute(
            """SELECT name, level FROM ref_schools WHERE REPLACE(name, ' ', '') LIKE ?
               ORDER BY CASE WHEN REPLACE(name, ' ', '') LIKE ? THEN 0 ELSE 1 END, name LIMIT 10""",
            (f"%{q}%", f"{q}%"),
        ).fetchall()
    finally:
        conn.close()
    return JSONResponse([{"name": r["name"], "level": r["level"]} for r in rows])

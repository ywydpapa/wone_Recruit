import json
from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from core.db import get_sqlite
from core.deps import require_role, templates
from core.constants import DUTY_DIFFICULTY, FIT_TYPES, FIT_LEVELS, DUTY_ANALYSIS_STATUS
from core.notifications import create_notification

router = APIRouter()

MARKET_DEMAND_LABELS = {"explosive": "폭발적 성장", "growing": "성장", "stable": "안정"}


def get_company(conn, user):
    return conn.execute("SELECT * FROM companies WHERE user_id=?", (user["id"],)).fetchone()


def get_duty(conn, duty_id, company_id):
    return conn.execute(
        "SELECT * FROM company_duties WHERE id=? AND company_id=?", (duty_id, company_id)
    ).fetchone()


def parse_fit(form):
    fit = {}
    for col in FIT_TYPES:
        raw = form.get(col, "")
        fit[col] = int(raw) if raw.isdigit() and 0 <= int(raw) <= 3 else 0
    return fit


def fit_rows(fit_dict):
    rows = []
    for col, label in FIT_TYPES.items():
        val = fit_dict.get(col, 0)
        level_label, color = FIT_LEVELS[val]
        rows.append({"col": col, "label": label, "value": val, "level_label": level_label, "color": color})
    return rows


@router.get("/company/duties", response_class=HTMLResponse)
async def duty_list(request: Request):
    user = require_role(request, "company")
    conn = get_sqlite()
    try:
        company = get_company(conn, user)
        if not company:
            return RedirectResponse(url="/company/profile", status_code=303)
        rows = conn.execute(
            """SELECT d.*, jc.minor_name_ko AS category_name
               FROM company_duties d
               LEFT JOIN job_categories jc ON d.category_id = jc.id
               WHERE d.company_id=? ORDER BY d.created_at DESC""",
            (company["id"],),
        ).fetchall()
        duties = []
        for d in rows:
            fit = json.loads(d["fit"])
            status_label, status_color = DUTY_ANALYSIS_STATUS[d["analysis_status"]]
            duties.append({
                "id": d["id"], "title": d["title"], "category_name": d["category_name"],
                "difficulty_label": DUTY_DIFFICULTY[d["difficulty"]],
                "remote_ok": d["remote_ok"],
                "fit_count": sum(1 for v in fit.values() if v >= 2),
                "status_label": status_label, "status_color": status_color,
            })
        rec_rows = conn.execute(
            """SELECT * FROM job_categories WHERE onsite_required=0
               ORDER BY CASE market_demand WHEN 'explosive' THEN 0 WHEN 'growing' THEN 1 WHEN 'stable' THEN 2 ELSE 3 END,
                        major_code, minor_code"""
        ).fetchall()
        recommends = [
            {
                "id": c["id"], "title": c["minor_name_ko"], "description": c["description"],
                "market_demand_label": MARKET_DEMAND_LABELS[c["market_demand"]],
            }
            for c in rec_rows
        ]
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="company/duties.html", context={
            "request": request, "page_title": "직무 관리",
            "user_name": user["name"], "user_role": "company",
            "duties": duties, "recommends": recommends,
        }
    )


@router.get("/company/duties/new", response_class=HTMLResponse)
async def duty_new_form(request: Request, category_id: int = Query(None)):
    user = require_role(request, "company")
    conn = get_sqlite()
    try:
        categories = conn.execute("SELECT * FROM job_categories ORDER BY major_code, minor_code").fetchall()
        form_data = {
            "title": "", "category_id": "", "tasks": "", "tools": "",
            "difficulty": "mid", "remote_ok": 1, "note": "",
        }
        fit_dict = {}
        if category_id:
            cat = conn.execute("SELECT * FROM job_categories WHERE id=?", (category_id,)).fetchone()
            if cat:
                tools = json.loads(cat["tools_software"])
                form_data.update({
                    "title": cat["minor_name_ko"], "category_id": cat["id"],
                    "tasks": cat["daily_tasks"], "tools": ", ".join(tools),
                    "difficulty": cat["difficulty"], "remote_ok": 0 if cat["onsite_required"] else 1,
                })
                fit_dict = {col: cat[col] for col in FIT_TYPES}
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="company/duty_form.html", context={
            "request": request, "page_title": "새 직무 등록",
            "user_name": user["name"], "user_role": "company",
            "duty": None, "form_data": form_data, "categories": categories,
            "duty_fit_rows": fit_rows(fit_dict), "difficulty_options": DUTY_DIFFICULTY,
            "fit_levels": FIT_LEVELS,
        }
    )


@router.post("/company/duties")
async def duty_create(
    request: Request,
    title: str = Form(...),
    category_id: str = Form(""),
    tasks: str = Form(""),
    tools: str = Form(""),
    difficulty: str = Form("mid"),
    remote_ok: str = Form("0"),
    note: str = Form(""),
):
    user = require_role(request, "company")
    form = await request.form()
    fit = parse_fit(form)
    title = title.strip()[:100]
    if difficulty not in DUTY_DIFFICULTY:
        difficulty = "mid"
    cat_id = int(category_id) if category_id.isdigit() else None
    remote_val = 1 if remote_ok in ("1", "on", "true") else 0
    conn = get_sqlite()
    try:
        company = get_company(conn, user)
        if not company:
            return RedirectResponse(url="/company/profile", status_code=303)
        conn.execute(
            """INSERT INTO company_duties
               (company_id, category_id, title, tasks, tools, difficulty, remote_ok, fit, note)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (company["id"], cat_id, title, tasks, tools, difficulty, remote_val,
             json.dumps(fit, ensure_ascii=False), note),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/company/duties", status_code=303)


@router.get("/company/duties/{duty_id}/edit", response_class=HTMLResponse)
async def duty_edit_form(request: Request, duty_id: int):
    user = require_role(request, "company")
    conn = get_sqlite()
    try:
        company = get_company(conn, user)
        if not company:
            return RedirectResponse(url="/company/profile", status_code=303)
        duty = get_duty(conn, duty_id, company["id"])
        if not duty:
            raise HTTPException(status_code=404, detail="직무를 찾을 수 없습니다.")
        categories = conn.execute("SELECT * FROM job_categories ORDER BY major_code, minor_code").fetchall()
        fit_dict = json.loads(duty["fit"])
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="company/duty_form.html", context={
            "request": request, "page_title": "직무 수정",
            "user_name": user["name"], "user_role": "company",
            "duty": duty, "form_data": dict(duty), "categories": categories,
            "duty_fit_rows": fit_rows(fit_dict), "difficulty_options": DUTY_DIFFICULTY,
            "fit_levels": FIT_LEVELS, "analysis_status": DUTY_ANALYSIS_STATUS[duty["analysis_status"]],
        }
    )


@router.post("/company/duties/{duty_id}")
async def duty_update(
    request: Request,
    duty_id: int,
    title: str = Form(...),
    category_id: str = Form(""),
    tasks: str = Form(""),
    tools: str = Form(""),
    difficulty: str = Form("mid"),
    remote_ok: str = Form("0"),
    note: str = Form(""),
):
    user = require_role(request, "company")
    form = await request.form()
    fit = parse_fit(form)
    title = title.strip()[:100]
    if difficulty not in DUTY_DIFFICULTY:
        difficulty = "mid"
    cat_id = int(category_id) if category_id.isdigit() else None
    remote_val = 1 if remote_ok in ("1", "on", "true") else 0
    conn = get_sqlite()
    try:
        company = get_company(conn, user)
        if not company:
            return RedirectResponse(url="/company/profile", status_code=303)
        duty = get_duty(conn, duty_id, company["id"])
        if not duty:
            raise HTTPException(status_code=404, detail="직무를 찾을 수 없습니다.")
        conn.execute(
            """UPDATE company_duties SET category_id=?, title=?, tasks=?, tools=?, difficulty=?,
               remote_ok=?, fit=?, note=?, updated_at=datetime('now','localtime')
               WHERE id=? AND company_id=?""",
            (cat_id, title, tasks, tools, difficulty, remote_val,
             json.dumps(fit, ensure_ascii=False), note, duty_id, company["id"]),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/company/duties", status_code=303)


@router.post("/company/duties/{duty_id}/delete")
async def duty_delete(request: Request, duty_id: int):
    user = require_role(request, "company")
    conn = get_sqlite()
    try:
        company = get_company(conn, user)
        if not company:
            return RedirectResponse(url="/company/profile", status_code=303)
        duty = get_duty(conn, duty_id, company["id"])
        if not duty:
            raise HTTPException(status_code=404, detail="직무를 찾을 수 없습니다.")
        conn.execute("DELETE FROM company_duties WHERE id=? AND company_id=?", (duty_id, company["id"]))
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/company/duties", status_code=303)


@router.post("/company/duties/{duty_id}/analysis")
async def duty_analysis_request(request: Request, duty_id: int, request_text: str = Form(...)):
    user = require_role(request, "company")
    request_text = request_text.strip()[:1000]
    conn = get_sqlite()
    try:
        company = get_company(conn, user)
        if not company:
            return RedirectResponse(url="/company/profile", status_code=303)
        duty = get_duty(conn, duty_id, company["id"])
        if not duty:
            raise HTTPException(status_code=404, detail="직무를 찾을 수 없습니다.")
        conn.execute(
            """UPDATE company_duties SET analysis_status='requested', analysis_request=?,
               updated_at=datetime('now','localtime') WHERE id=? AND company_id=?""",
            (request_text, duty_id, company["id"]),
        )
        operators = conn.execute("SELECT id FROM users WHERE role='operator'").fetchall()
        msg = f"{company['company_name']}에서 '{duty['title']}' 직무 분석을 요청했습니다."
        for op in operators:
            create_notification(conn, op["id"], msg, link=f"/op/duties/{duty_id}", kind="system")
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=f"/company/duties/{duty_id}/edit", status_code=303)


@router.get("/company/duties/{duty_id}/job")
async def duty_to_job(request: Request, duty_id: int):
    user = require_role(request, "company")
    conn = get_sqlite()
    try:
        company = get_company(conn, user)
        if not company:
            return RedirectResponse(url="/company/profile", status_code=303)
        duty = get_duty(conn, duty_id, company["id"])
        if not duty:
            raise HTTPException(status_code=404, detail="직무를 찾을 수 없습니다.")
    finally:
        conn.close()
    return RedirectResponse(url=f"/company/jobs/new?duty_id={duty_id}", status_code=303)


@router.get("/op/duties", response_class=HTMLResponse)
async def op_duty_list(request: Request, status: str = Query(None)):
    user = require_role(request, "operator")
    conn = get_sqlite()
    try:
        count_rows = conn.execute(
            "SELECT analysis_status, COUNT(*) AS cnt FROM company_duties WHERE analysis_status IN ('requested','done') GROUP BY analysis_status"
        ).fetchall()
        tab_counts = {r["analysis_status"]: r["cnt"] for r in count_rows}
        tab_counts.setdefault("requested", 0)
        tab_counts.setdefault("done", 0)
        tab_counts["all"] = tab_counts["requested"] + tab_counts["done"]

        where = "d.analysis_status IN ('requested','done')"
        params = []
        if status in ("requested", "done"):
            where = "d.analysis_status=?"
            params.append(status)
        rows = conn.execute(
            f"""SELECT d.*, c.company_name FROM company_duties d
                JOIN companies c ON d.company_id=c.id
                WHERE {where} ORDER BY d.updated_at DESC, d.created_at DESC""",
            params,
        ).fetchall()
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="op/duties.html", context={
            "request": request, "page_title": "직무 분석 요청",
            "user_name": user["name"], "user_role": "operator",
            "duties": rows, "tab_counts": tab_counts, "selected_status": status or "",
            "status_labels": DUTY_ANALYSIS_STATUS,
        }
    )


@router.get("/op/duties/{duty_id}", response_class=HTMLResponse)
async def op_duty_detail(request: Request, duty_id: int):
    user = require_role(request, "operator")
    conn = get_sqlite()
    try:
        duty = conn.execute(
            """SELECT d.*, c.company_name, jc.minor_name_ko AS category_name,
                      u.name AS analyzed_by_name
               FROM company_duties d
               JOIN companies c ON d.company_id=c.id
               LEFT JOIN job_categories jc ON d.category_id=jc.id
               LEFT JOIN users u ON d.analyzed_by=u.id
               WHERE d.id=?""",
            (duty_id,),
        ).fetchone()
        if not duty:
            raise HTTPException(status_code=404, detail="직무를 찾을 수 없습니다.")
        fit_dict = json.loads(duty["fit"])
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request, name="op/duty_detail.html", context={
            "request": request, "page_title": duty["title"],
            "user_name": user["name"], "user_role": "operator",
            "duty": duty, "duty_fit_rows": fit_rows(fit_dict),
            "difficulty_label": DUTY_DIFFICULTY[duty["difficulty"]],
            "fit_levels": FIT_LEVELS, "status_labels": DUTY_ANALYSIS_STATUS,
        }
    )


@router.post("/op/duties/{duty_id}/analysis")
async def op_duty_analysis(request: Request, duty_id: int, analysis_note: str = Form(...)):
    user = require_role(request, "operator")
    form = await request.form()
    fit = parse_fit(form)
    analysis_note = analysis_note.strip()[:2000]
    conn = get_sqlite()
    try:
        duty = conn.execute("SELECT * FROM company_duties WHERE id=?", (duty_id,)).fetchone()
        if not duty:
            raise HTTPException(status_code=404, detail="직무를 찾을 수 없습니다.")
        conn.execute(
            """UPDATE company_duties SET analysis_status='done', analysis_note=?, fit=?,
               analyzed_by=?, analyzed_at=datetime('now','localtime'),
               updated_at=datetime('now','localtime') WHERE id=?""",
            (analysis_note, json.dumps(fit, ensure_ascii=False), user["id"], duty_id),
        )
        company = conn.execute("SELECT user_id FROM companies WHERE id=?", (duty["company_id"],)).fetchone()
        create_notification(
            conn, company["user_id"], f"'{duty['title']}' 직무 분석 결과가 도착했습니다.",
            link=f"/company/duties/{duty_id}/edit", kind="system",
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=f"/op/duties/{duty_id}", status_code=303)

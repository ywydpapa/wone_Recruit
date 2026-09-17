import json
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from core.db import get_sqlite
from core.deps import require_role, templates

router = APIRouter(prefix="/company")


@router.get("/jobs/{job_id}/report", response_class=HTMLResponse)
async def job_report(request: Request, job_id: int):
    user = require_role(request, "company")
    conn = get_sqlite()
    try:
        company = conn.execute("SELECT * FROM companies WHERE user_id=?", (user["id"],)).fetchone()
        if not company:
            return RedirectResponse(url="/company/profile", status_code=303)

        job = conn.execute(
            "SELECT * FROM job_postings WHERE id=? AND company_id=?",
            (job_id, company["id"]),
        ).fetchone()
        if job is None:
            raise HTTPException(status_code=404, detail="공고를 찾을 수 없습니다.")

        # 장애유형별 분포
        dtype_rows = conn.execute(
            """SELECT dt.name AS dtype, COUNT(*) AS cnt
               FROM candidacies c
               JOIN seeker_profiles sp ON c.seeker_user_id = sp.user_id
               LEFT JOIN disability_types dt ON sp.disability_type_id = dt.id
               WHERE c.job_id=?
                 AND (c.source='direct' OR c.match_stage='submitted')
               GROUP BY dt.name""",
            (job_id,),
        ).fetchall()
        dtype_labels = [r["dtype"] or "미등록" for r in dtype_rows]
        dtype_data = [r["cnt"] for r in dtype_rows]

        # 중증도별 분포
        severity_rows = conn.execute(
            """SELECT sp.severity, COUNT(*) AS cnt
               FROM candidacies c
               JOIN seeker_profiles sp ON c.seeker_user_id = sp.user_id
               WHERE c.job_id=?
                 AND (c.source='direct' OR c.match_stage='submitted')
               GROUP BY sp.severity""",
            (job_id,),
        ).fetchall()
        severity_labels = [r["severity"] or "미등록" for r in severity_rows]
        severity_data = [r["cnt"] for r in severity_rows]

        # 일별 지원 추이 (created_at 날짜 기준)
        trend_rows = conn.execute(
            """SELECT DATE(c.created_at) AS day, COUNT(*) AS cnt
               FROM candidacies c
               WHERE c.job_id=?
                 AND (c.source='direct' OR c.match_stage='submitted')
               GROUP BY DATE(c.created_at)
               ORDER BY day""",
            (job_id,),
        ).fetchall()
        trend_labels = [r["day"] for r in trend_rows]
        trend_data = [r["cnt"] for r in trend_rows]

        # 파이프라인 전환 (status별 카운트)
        pipeline_rows = conn.execute(
            """SELECT c.status, COUNT(*) AS cnt
               FROM candidacies c
               WHERE c.job_id=?
                 AND (c.source='direct' OR c.match_stage='submitted')
               GROUP BY c.status""",
            (job_id,),
        ).fetchall()

        # 커스텀 스테이지 레이블 적용
        stage_label_rows = conn.execute(
            "SELECT stage_key, label FROM company_pipeline_stages WHERE company_id=?",
            (company["id"],),
        ).fetchall()
        stage_labels = {r["stage_key"]: r["label"] for r in stage_label_rows}

        pipeline_labels = [stage_labels.get(r["status"], r["status"]) for r in pipeline_rows]
        pipeline_data = [r["cnt"] for r in pipeline_rows]

    finally:
        conn.close()

    return templates.TemplateResponse(
        request=request,
        name="company/job_report.html",
        context={
            "request": request,
            "page_title": f"채용 보고서 - {job['title']}",
            "user_name": user["name"],
            "user_role": "company",
            "job": job,
            "dtype_labels": json.dumps(dtype_labels, ensure_ascii=False),
            "dtype_data": json.dumps(dtype_data),
            "severity_labels": json.dumps(severity_labels, ensure_ascii=False),
            "severity_data": json.dumps(severity_data),
            "trend_labels": json.dumps(trend_labels),
            "trend_data": json.dumps(trend_data),
            "pipeline_labels": json.dumps(pipeline_labels, ensure_ascii=False),
            "pipeline_data": json.dumps(pipeline_data),
        },
    )

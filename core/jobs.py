import asyncio
import json
from datetime import date

from core.db import get_sqlite
from core.logger import log
from core.notifications import create_notification

SCHED_INTERVAL = 3600


def build_search_sql(filters):
    sql = (
        "SELECT jp.id, jp.created_at FROM job_postings jp "
        "LEFT JOIN regions r ON jp.region_id=r.id "
        "WHERE jp.status='open'"
    )
    params = []
    if filters.get('q'):
        sql += " AND (jp.title LIKE ? OR jp.description LIKE ?)"
        params += [f"%{filters['q']}%", f"%{filters['q']}%"]
    if filters.get('region_id'):
        sql += " AND jp.region_id=?"
        params.append(int(filters['region_id']))
    elif filters.get('sido'):
        sql += " AND r.sido=?"
        params.append(filters['sido'])
    if filters.get('employment_type'):
        sql += " AND jp.employment_type=?"
        params.append(filters['employment_type'])
    if filters.get('remote'):
        sql += " AND jp.remote_available=1"
    if filters.get('category'):
        sql += " AND jp.category_id=?"
        params.append(int(filters['category']))
    if filters.get('max_hours'):
        sql += " AND jp.min_work_hours<=?"
        params.append(int(filters['max_hours']))
    if filters.get('accommodation'):
        sql += " AND jp.accommodations_provided LIKE ?"
        params.append(f"%{filters['accommodation']}%")
    if filters.get('disability_type'):
        sql += " AND jp.preferred_disability LIKE ?"
        params.append(f"%{filters['disability_type']}%")
    if filters.get('severity'):
        sql += " AND (jp.preferred_severity=? OR jp.preferred_severity='무관')"
        params.append(filters['severity'])
    return sql, params



def close_expired_jobs():
    conn = get_sqlite()
    try:
        today = date.today().isoformat()
        cur = conn.execute(
            "UPDATE job_postings SET status='closed' WHERE status='open' AND deadline!='' AND deadline<?",
            (today,),
        )
        cnt = cur.rowcount
        conn.commit()
        if cnt:
            log.info("마감 공고 %d건 자동 종료", cnt)
        return cnt
    finally:
        conn.close()


def notify_saved_searches():
    conn = get_sqlite()
    try:
        searches = conn.execute(
            "SELECT id, user_id, name, filters, "
            "COALESCE(last_notified_at, last_checked_at, created_at) AS since "
            "FROM saved_searches"
        ).fetchall()
        sent = 0
        for s in searches:
            sql, params = build_search_sql(json.loads(s["filters"] or "{}"))
            cnt = conn.execute(
                f"SELECT COUNT(*) FROM ({sql} AND jp.created_at > ?)", params + [s["since"]]
            ).fetchone()[0]
            if not cnt:
                continue
            create_notification(
                conn, s["user_id"],
                f"[{s['name'] or '검색 알림'}] 조건에 맞는 새 공고가 {cnt}건 올라왔습니다.",
                "/saved-searches",
                kind="job",
            )
            conn.execute(
                "UPDATE saved_searches SET last_notified_at=datetime('now','localtime') WHERE id=?",
                (s["id"],),
            )
            sent += 1
        conn.commit()
        if sent:
            log.info("검색 알림 %d건 발송", sent)
        return sent
    finally:
        conn.close()


# 단일 서버 프로세스 기준으로 동작함. 워커를 여러 개 기동하면 중복 실행됨
async def run_scheduler():
    while True:
        await asyncio.sleep(SCHED_INTERVAL)
        for job in (close_expired_jobs, notify_saved_searches):
            try:
                await asyncio.to_thread(job)
            except Exception:
                log.exception("스케줄 작업 실패: %s", job.__name__)

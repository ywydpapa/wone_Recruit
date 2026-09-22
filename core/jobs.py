from datetime import date

from core.db import get_sqlite
from core.logger import log


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

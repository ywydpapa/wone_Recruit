# static/uploads 비공개 파일을 var/uploads로 이동하고 DB 경로 갱신
# 기본 드라이런. 실제 반영은 --apply. 실행 전 DB 백업 필수
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.db import get_sqlite
from core.upload import PRIVATE, PRIVATE_DIR, UPLOAD_DIR

COLUMNS = [
    ("resumes", "resume_path"),
    ("resumes", "photo_path"),
    ("seeker_profiles", "resume_path"),
    ("companies", "biz_doc_path"),
]

apply = "--apply" in sys.argv

moved = 0
for area in sorted(PRIVATE):
    src = os.path.join(UPLOAD_DIR, area)
    if not os.path.isdir(src):
        continue
    dst = os.path.join(PRIVATE_DIR, area)
    names = [n for n in os.listdir(src) if not n.startswith(".")]
    print(f"{area}: {len(names)}개 -> {dst}")
    if apply:
        os.makedirs(dst, exist_ok=True)
        for n in names:
            shutil.move(os.path.join(src, n), os.path.join(dst, n))
    moved += len(names)

conn = get_sqlite()
try:
    for table, col in COLUMNS:
        for area in PRIVATE:
            old = f"/static/uploads/{area}/"
            cnt = conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {col} LIKE ?", (old + "%",)
            ).fetchone()[0]
            if not cnt:
                continue
            print(f"{table}.{col} {area}: {cnt}건")
            if apply:
                conn.execute(
                    f"UPDATE {table} SET {col}=REPLACE({col}, ?, ?) WHERE {col} LIKE ?",
                    (old, f"/files/{area}/", old + "%"),
                )
    if apply:
        conn.commit()
finally:
    conn.close()

print(f"파일 {moved}개, {'반영 완료' if apply else '드라이런. --apply로 실행'}")

import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(ROOT, "static", "uploads")
# 이력서, 사업자등록증은 웹루트 밖 저장. /files 라우트에서 권한 확인 후 서빙
PRIVATE_DIR = os.path.join(ROOT, "var", "uploads")
PRIVATE = {"resumes", "resume_photos", "profile_resumes", "biz_docs"}

_MAGIC = {
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/png": [b"\x89PNG"],
    "image/gif": [b"GIF87a", b"GIF89a"],
    "image/webp": [b"RIFF"],
    "application/pdf": [b"%PDF"],
}


async def save_upload(upload, subdir, user_id, allowed_types, max_bytes):
    if not upload or not upload.filename:
        return ""
    if upload.content_type not in allowed_types:
        return ""
    content = await upload.read()
    if len(content) > max_bytes or len(content) == 0:
        return ""
    sigs = _MAGIC.get(upload.content_type)
    if sigs and not any(content.startswith(s) for s in sigs):
        return ""
    ext = upload.filename.rsplit(".", 1)[-1].lower() if "." in upload.filename else "bin"
    filename = f"{user_id}_{int(time.time())}.{ext}"
    private = subdir in PRIVATE
    dirpath = os.path.join(PRIVATE_DIR if private else UPLOAD_DIR, subdir)
    os.makedirs(dirpath, exist_ok=True)
    filepath = os.path.join(dirpath, filename)
    with open(filepath, "wb") as f:
        f.write(content)
    if private:
        return f"/files/{subdir}/{filename}"
    return f"/static/uploads/{subdir}/{filename}"

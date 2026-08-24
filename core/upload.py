import os
import time

from fastapi import UploadFile

UPLOAD_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "uploads"
)


async def save_upload(
    upload: UploadFile, subdir: str, user_id: int,
    allowed_types: list, max_bytes: int,
) -> str:
    if not upload or not upload.filename:
        return ""
    if upload.content_type not in allowed_types:
        return ""
    content = await upload.read()
    if len(content) > max_bytes or len(content) == 0:
        return ""
    ext = upload.filename.rsplit(".", 1)[-1].lower() if "." in upload.filename else "bin"
    filename = f"{user_id}_{int(time.time())}.{ext}"
    dirpath = os.path.join(UPLOAD_DIR, subdir)
    os.makedirs(dirpath, exist_ok=True)
    filepath = os.path.join(dirpath, filename)
    with open(filepath, "wb") as f:
        f.write(content)
    return f"/static/uploads/{subdir}/{filename}"

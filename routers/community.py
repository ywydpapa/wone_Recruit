from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from core.db import get_sqlite
from core.deps import check_login, templates
from core.constants import POST_CATEGORIES

router = APIRouter()

PER_PAGE = 10


def _get_session_user(request):
    return {
        "user_id": request.session["user_id"],
        "user_name": request.session.get("user_name", ""),
        "user_role": request.session.get("user_role", ""),
    }


@router.get("/community", response_class=HTMLResponse)
async def community_list(
    request: Request,
    category: str = Query("all"),
    q: str = Query(""),
    page: int = Query(1),
):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    user = _get_session_user(request)

    conn = get_sqlite()
    try:
        sql = (
            "SELECT p.*, "
            "(SELECT COUNT(*) FROM comments c WHERE c.post_id=p.id) AS comment_count, "
            "(SELECT COUNT(*) FROM post_likes pl WHERE pl.post_id=p.id) AS like_count "
            "FROM posts p WHERE 1=1"
        )
        params = []
        if category != "all":
            sql += " AND p.category=?"
            params.append(category)
        if q:
            sql += " AND (p.title LIKE ? OR p.content LIKE ?)"
            params += [f"%{q}%", f"%{q}%"]

        count_sql = f"SELECT COUNT(*) FROM ({sql})"
        total = conn.execute(count_sql, params).fetchone()[0]
        total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
        page = max(1, min(page, total_pages))

        sql += " ORDER BY p.created_at DESC"
        sql += f" LIMIT {PER_PAGE} OFFSET {(page - 1) * PER_PAGE}"
        posts = conn.execute(sql, params).fetchall()

        my_post_count = conn.execute(
            "SELECT COUNT(*) FROM posts WHERE user_id=?", (user["user_id"],)
        ).fetchone()[0]
        my_comment_count = conn.execute(
            "SELECT COUNT(*) FROM comments WHERE user_id=?", (user["user_id"],)
        ).fetchone()[0]
        my_like_received = conn.execute(
            "SELECT COUNT(*) FROM post_likes pl JOIN posts p ON pl.post_id=p.id WHERE p.user_id=?",
            (user["user_id"],),
        ).fetchone()[0]
    finally:
        conn.close()

    return templates.TemplateResponse(
        request=request,
        name="community/community.html",
        context={
            "request": request,
            "page_title": "커뮤니티",
            "user_name": user["user_name"],
            "user_role": user["user_role"],
            "posts": posts,
            "categories": POST_CATEGORIES,
            "current_category": category,
            "q": q,
            "page": page,
            "total_pages": total_pages,
            "my_post_count": my_post_count,
            "my_comment_count": my_comment_count,
            "my_like_received": my_like_received,
        },
    )


@router.get("/write_post", response_class=HTMLResponse)
async def write_post_form(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    user = _get_session_user(request)
    return templates.TemplateResponse(
        request=request,
        name="community/write_post.html",
        context={
            "request": request,
            "page_title": "글 작성",
            "user_name": user["user_name"],
            "user_role": user["user_role"],
            "categories": POST_CATEGORIES,
        },
    )


@router.post("/api/posts")
async def create_post(
    request: Request,
    category: str = Form(...),
    title: str = Form(...),
    content: str = Form(...),
):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    user = _get_session_user(request)
    conn = get_sqlite()
    try:
        conn.execute(
            "INSERT INTO posts (user_id, category, title, content, author) VALUES (?,?,?,?,?)",
            (user["user_id"], category, title, content, user["user_name"]),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/community", status_code=303)


@router.get("/post/{post_id}", response_class=HTMLResponse)
async def post_detail(request: Request, post_id: int):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    user = _get_session_user(request)
    conn = get_sqlite()
    try:
        post = conn.execute("SELECT * FROM posts WHERE id=?", (post_id,)).fetchone()
        if not post:
            return RedirectResponse(url="/community", status_code=303)
        conn.execute("UPDATE posts SET views=views+1 WHERE id=?", (post_id,))
        conn.commit()
        comments = conn.execute(
            "SELECT * FROM comments WHERE post_id=? ORDER BY created_at", (post_id,)
        ).fetchall()
        like_count = conn.execute(
            "SELECT COUNT(*) FROM post_likes WHERE post_id=?", (post_id,)
        ).fetchone()[0]
        liked = bool(
            conn.execute(
                "SELECT 1 FROM post_likes WHERE post_id=? AND user_id=?",
                (post_id, user["user_id"]),
            ).fetchone()
        )
        bookmarked = bool(
            conn.execute(
                "SELECT 1 FROM post_bookmarks WHERE post_id=? AND user_id=?",
                (post_id, user["user_id"]),
            ).fetchone()
        )
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request,
        name="community/post_detail.html",
        context={
            "request": request,
            "page_title": post["title"],
            "user_name": user["user_name"],
            "user_role": user["user_role"],
            "post": post,
            "comments": comments,
            "like_count": like_count,
            "liked": liked,
            "bookmarked": bookmarked,
            "session_uid": user["user_id"],
            "categories": POST_CATEGORIES,
        },
    )


@router.post("/api/posts/{post_id}/comments")
async def add_comment(request: Request, post_id: int, content: str = Form(...)):
    if not check_login(request):
        return JSONResponse({"error": "login required"}, status_code=401)
    user = _get_session_user(request)
    conn = get_sqlite()
    try:
        conn.execute(
            "INSERT INTO comments (post_id, user_id, author, content) VALUES (?,?,?,?)",
            (post_id, user["user_id"], user["user_name"], content),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=f"/post/{post_id}", status_code=303)


@router.post("/api/posts/{post_id}/like")
async def toggle_like(request: Request, post_id: int):
    if not check_login(request):
        return JSONResponse({"error": "login required"}, status_code=401)
    user = _get_session_user(request)
    conn = get_sqlite()
    try:
        existing = conn.execute(
            "SELECT 1 FROM post_likes WHERE post_id=? AND user_id=?",
            (post_id, user["user_id"]),
        ).fetchone()
        if existing:
            conn.execute(
                "DELETE FROM post_likes WHERE post_id=? AND user_id=?",
                (post_id, user["user_id"]),
            )
            liked = False
        else:
            conn.execute(
                "INSERT INTO post_likes (post_id, user_id) VALUES (?,?)",
                (post_id, user["user_id"]),
            )
            liked = True
        conn.commit()
        count = conn.execute(
            "SELECT COUNT(*) FROM post_likes WHERE post_id=?", (post_id,)
        ).fetchone()[0]
    finally:
        conn.close()
    return JSONResponse({"liked": liked, "count": count})


@router.post("/api/posts/{post_id}/bookmark")
async def toggle_bookmark(request: Request, post_id: int):
    if not check_login(request):
        return JSONResponse({"error": "login required"}, status_code=401)
    user = _get_session_user(request)
    conn = get_sqlite()
    try:
        existing = conn.execute(
            "SELECT 1 FROM post_bookmarks WHERE post_id=? AND user_id=?",
            (post_id, user["user_id"]),
        ).fetchone()
        if existing:
            conn.execute(
                "DELETE FROM post_bookmarks WHERE post_id=? AND user_id=?",
                (post_id, user["user_id"]),
            )
            bookmarked = False
        else:
            conn.execute(
                "INSERT INTO post_bookmarks (post_id, user_id) VALUES (?,?)",
                (post_id, user["user_id"]),
            )
            bookmarked = True
        conn.commit()
    finally:
        conn.close()
    return JSONResponse({"bookmarked": bookmarked})


@router.delete("/api/posts/{post_id}")
async def delete_post(request: Request, post_id: int):
    if not check_login(request):
        return JSONResponse({"error": "login required"}, status_code=401)
    user = _get_session_user(request)
    conn = get_sqlite()
    try:
        post = conn.execute("SELECT user_id FROM posts WHERE id=?", (post_id,)).fetchone()
        if not post or post["user_id"] != user["user_id"]:
            return JSONResponse({"error": "unauthorized"}, status_code=403)
        conn.execute("DELETE FROM comments WHERE post_id=?", (post_id,))
        conn.execute("DELETE FROM post_likes WHERE post_id=?", (post_id,))
        conn.execute("DELETE FROM post_bookmarks WHERE post_id=?", (post_id,))
        conn.execute("DELETE FROM posts WHERE id=?", (post_id,))
        conn.commit()
    finally:
        conn.close()
    return JSONResponse({"ok": True})


@router.delete("/api/comments/{comment_id}")
async def delete_comment(request: Request, comment_id: int):
    if not check_login(request):
        return JSONResponse({"error": "login required"}, status_code=401)
    user = _get_session_user(request)
    conn = get_sqlite()
    try:
        comment = conn.execute("SELECT user_id FROM comments WHERE id=?", (comment_id,)).fetchone()
        if not comment or comment["user_id"] != user["user_id"]:
            return JSONResponse({"error": "unauthorized"}, status_code=403)
        conn.execute("DELETE FROM comments WHERE id=?", (comment_id,))
        conn.commit()
    finally:
        conn.close()
    return JSONResponse({"ok": True})


@router.get("/my_posts", response_class=HTMLResponse)
async def my_posts(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    user = _get_session_user(request)
    conn = get_sqlite()
    try:
        posts = conn.execute(
            "SELECT p.*, (SELECT COUNT(*) FROM comments c WHERE c.post_id=p.id) AS comment_count "
            "FROM posts p WHERE p.user_id=? ORDER BY p.created_at DESC",
            (user["user_id"],),
        ).fetchall()
        comments = conn.execute(
            "SELECT c.*, p.title AS post_title FROM comments c "
            "JOIN posts p ON c.post_id=p.id WHERE c.user_id=? ORDER BY c.created_at DESC",
            (user["user_id"],),
        ).fetchall()
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request,
        name="community/my_posts.html",
        context={
            "request": request,
            "page_title": "내 글/댓글",
            "user_name": user["user_name"],
            "user_role": user["user_role"],
            "posts": posts,
            "comments": comments,
            "categories": POST_CATEGORIES,
        },
    )


@router.get("/my_bookmarks_posts", response_class=HTMLResponse)
async def my_bookmarked_posts(request: Request):
    if not check_login(request):
        return RedirectResponse(url="/login", status_code=303)
    user = _get_session_user(request)
    conn = get_sqlite()
    try:
        posts = conn.execute(
            "SELECT p.*, (SELECT COUNT(*) FROM comments c WHERE c.post_id=p.id) AS comment_count "
            "FROM posts p JOIN post_bookmarks pb ON p.id=pb.post_id "
            "WHERE pb.user_id=? ORDER BY p.created_at DESC",
            (user["user_id"],),
        ).fetchall()
    finally:
        conn.close()
    return templates.TemplateResponse(
        request=request,
        name="community/my_bookmarks.html",
        context={
            "request": request,
            "page_title": "스크랩한 글",
            "user_name": user["user_name"],
            "user_role": user["user_role"],
            "posts": posts,
            "categories": POST_CATEGORIES,
        },
    )



@router.get("/api/messages/thread")
async def message_thread(request: Request, with_name: str = Query(...)):
    if not check_login(request):
        return JSONResponse({"error": "login required"}, status_code=401)
    user = _get_session_user(request)
    conn = get_sqlite()
    try:
        messages = conn.execute(
            "SELECT * FROM messages WHERE user_id=? AND "
            "(sender=? OR recipient=?) ORDER BY created_at DESC LIMIT 20",
            (user["user_id"], with_name, with_name),
        ).fetchall()
        result = [dict(m) for m in reversed(messages)]
    finally:
        conn.close()
    return JSONResponse(result)


@router.post("/api/messages/send")
async def send_message(
    request: Request,
    to_name: str = Form(...),
    body: str = Form(...),
):
    if not check_login(request):
        return JSONResponse({"error": "login required"}, status_code=401)
    user = _get_session_user(request)
    conn = get_sqlite()
    try:
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        conn.execute(
            "INSERT INTO messages (user_id, sender, recipient, body, time_label, direction) "
            "VALUES (?,?,?,?,?,?)",
            (user["user_id"], user["user_name"], to_name, body, now, "out"),
        )
        recipient = conn.execute(
            "SELECT id FROM users WHERE name=?", (to_name,)
        ).fetchone()
        if recipient:
            conn.execute(
                "INSERT INTO messages (user_id, sender, recipient, body, time_label, direction) "
                "VALUES (?,?,?,?,?,?)",
                (recipient["id"], user["user_name"], to_name, body, now, "in"),
            )
        conn.commit()
    finally:
        conn.close()
    return JSONResponse({"ok": True})

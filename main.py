import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
import dotenv

from core.logger import log
from core.deps import templates

dotenv.load_dotenv()


def _ensure_db():
    from core.db import get_sqlite
    conn = get_sqlite()
    try:
        conn.execute("SELECT 1 FROM users LIMIT 1")
    except Exception:
        conn.close()
        from init_db import init
        init()
        return

    _MISSING_TABLE_MIGRATIONS = {
        "bookmarks": """
            CREATE TABLE IF NOT EXISTS bookmarks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                job_id INTEGER NOT NULL,
                created_at TEXT DEFAULT (datetime('now','localtime')),
                UNIQUE(user_id, job_id)
            );
            CREATE INDEX IF NOT EXISTS idx_bookmarks_user ON bookmarks(user_id);
        """,
        "recent_views": """
            CREATE TABLE IF NOT EXISTS recent_views (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                job_id INTEGER NOT NULL,
                viewed_at TEXT DEFAULT (datetime('now','localtime')),
                UNIQUE(user_id, job_id)
            );
            CREATE INDEX IF NOT EXISTS idx_recent_views_user ON recent_views(user_id);
        """,
        "notifications": """
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                link TEXT NOT NULL DEFAULT '',
                is_read INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, is_read);
        """,
        "job_categories": """
            CREATE TABLE IF NOT EXISTS job_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                major_code TEXT NOT NULL,
                major_name_ko TEXT NOT NULL,
                major_name_en TEXT NOT NULL,
                minor_code TEXT NOT NULL,
                minor_name_ko TEXT NOT NULL,
                minor_name_en TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                daily_tasks TEXT NOT NULL DEFAULT '',
                tools_software TEXT NOT NULL DEFAULT '[]',
                min_qualifications TEXT NOT NULL DEFAULT '[]',
                training_days INTEGER NOT NULL DEFAULT 7,
                difficulty TEXT NOT NULL DEFAULT 'mid',
                work_hours_type TEXT NOT NULL DEFAULT 'full',
                min_hours_per_day INTEGER NOT NULL DEFAULT 4,
                shift_required INTEGER NOT NULL DEFAULT 0,
                onsite_required INTEGER NOT NULL DEFAULT 0,
                kpi_metrics TEXT NOT NULL DEFAULT '[]',
                salary_min INTEGER NOT NULL DEFAULT 2096270,
                salary_max INTEGER NOT NULL DEFAULT 2096270,
                salary_basis TEXT NOT NULL DEFAULT 'full_8h',
                fit_physical_lower INTEGER NOT NULL DEFAULT 3,
                fit_physical_upper INTEGER NOT NULL DEFAULT 2,
                fit_hearing INTEGER NOT NULL DEFAULT 3,
                fit_visual_low INTEGER NOT NULL DEFAULT 1,
                fit_intellectual INTEGER NOT NULL DEFAULT 1,
                fit_autism INTEGER NOT NULL DEFAULT 2,
                fit_mental INTEGER NOT NULL DEFAULT 2,
                fit_internal_organ INTEGER NOT NULL DEFAULT 3,
                fit_brain_lesion INTEGER NOT NULL DEFAULT 2,
                fit_notes TEXT NOT NULL DEFAULT '',
                market_demand TEXT NOT NULL DEFAULT 'stable',
                is_wone_exclusive INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(major_code, minor_code)
            );
        """,
        "posts": """
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                category TEXT NOT NULL DEFAULT 'general',
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                author TEXT NOT NULL DEFAULT '',
                views INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_posts_user ON posts(user_id);
        """,
        "comments": """
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                author TEXT NOT NULL DEFAULT '',
                content TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_comments_post ON comments(post_id);
        """,
        "post_likes": """
            CREATE TABLE IF NOT EXISTS post_likes (
                post_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                PRIMARY KEY (post_id, user_id)
            );
        """,
        "post_bookmarks": """
            CREATE TABLE IF NOT EXISTS post_bookmarks (
                post_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                PRIMARY KEY (post_id, user_id)
            );
        """,
        "messages": """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                sender TEXT NOT NULL DEFAULT '',
                recipient TEXT NOT NULL DEFAULT '',
                body TEXT NOT NULL DEFAULT '',
                time_label TEXT NOT NULL DEFAULT '',
                is_read INTEGER NOT NULL DEFAULT 0,
                direction TEXT NOT NULL DEFAULT 'in',
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id);
        """,
        "talent_offers": """
            CREATE TABLE IF NOT EXISTS talent_offers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seeker_user_id INTEGER NOT NULL,
                company_user_id INTEGER NOT NULL,
                company_name TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                contact TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_talent_offers_seeker ON talent_offers(seeker_user_id);
        """,
        "interview_schedules": """
            CREATE TABLE IF NOT EXISTS interview_schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidacy_id INTEGER NOT NULL,
                interview_date TEXT NOT NULL,
                interview_time TEXT NOT NULL DEFAULT '10:00',
                interview_type TEXT NOT NULL DEFAULT 'onsite',
                location TEXT NOT NULL DEFAULT '',
                memo TEXT NOT NULL DEFAULT '',
                created_at TEXT DEFAULT (datetime('now','localtime')),
                updated_at TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_interview_candidacy ON interview_schedules(candidacy_id);
        """,
        "applicant_notes": """
            CREATE TABLE IF NOT EXISTS applicant_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidacy_id INTEGER NOT NULL,
                author_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_notes_candidacy ON applicant_notes(candidacy_id);
        """,
        "attendance": """
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL,
                employee_user_id INTEGER NOT NULL,
                work_date TEXT NOT NULL,
                check_in TEXT,
                check_out TEXT,
                status TEXT NOT NULL DEFAULT 'normal',
                memo TEXT NOT NULL DEFAULT '',
                created_at TEXT DEFAULT (datetime('now','localtime')),
                updated_at TEXT DEFAULT (datetime('now','localtime')),
                UNIQUE(company_id, employee_user_id, work_date)
            );
            CREATE INDEX IF NOT EXISTS idx_attendance_company ON attendance(company_id, work_date);
            CREATE INDEX IF NOT EXISTS idx_attendance_employee ON attendance(employee_user_id, work_date);
        """,
        "company_pipeline_stages": """
            CREATE TABLE IF NOT EXISTS company_pipeline_stages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL,
                stage_key TEXT NOT NULL,
                label TEXT NOT NULL,
                sort_order INTEGER NOT NULL,
                UNIQUE(company_id, stage_key)
            );
        """,
        "education_history": """
            CREATE TABLE IF NOT EXISTS education_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                education_level TEXT NOT NULL DEFAULT '',
                school_name TEXT NOT NULL DEFAULT '',
                major TEXT NOT NULL DEFAULT '',
                start_date TEXT NOT NULL DEFAULT '',
                end_date TEXT NOT NULL DEFAULT '',
                graduation_status TEXT NOT NULL DEFAULT '',
                gpa TEXT NOT NULL DEFAULT '',
                gpa_scale TEXT NOT NULL DEFAULT '',
                is_transfer INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_edu_user ON education_history(user_id);
        """,
        "career_history": """
            CREATE TABLE IF NOT EXISTS career_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                company_name TEXT NOT NULL DEFAULT '',
                department TEXT NOT NULL DEFAULT '',
                position TEXT NOT NULL DEFAULT '',
                start_date TEXT NOT NULL DEFAULT '',
                end_date TEXT NOT NULL DEFAULT '',
                is_current INTEGER NOT NULL DEFAULT 0,
                employment_type TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_career_user ON career_history(user_id);
        """,
        "language_skills": """
            CREATE TABLE IF NOT EXISTS language_skills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                language TEXT NOT NULL DEFAULT '',
                test_name TEXT NOT NULL DEFAULT '',
                score TEXT NOT NULL DEFAULT '',
                level TEXT NOT NULL DEFAULT '',
                test_date TEXT NOT NULL DEFAULT '',
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_lang_user ON language_skills(user_id);
        """,
        "awards_activities": """
            CREATE TABLE IF NOT EXISTS awards_activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                category TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL DEFAULT '',
                organizer TEXT NOT NULL DEFAULT '',
                activity_date TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_award_user ON awards_activities(user_id);
        """,
        "portfolio_links": """
            CREATE TABLE IF NOT EXISTS portfolio_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                link_type TEXT NOT NULL DEFAULT '',
                url TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_port_user ON portfolio_links(user_id);
        """,
        "self_intro_items": """
            CREATE TABLE IF NOT EXISTS self_intro_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                title TEXT NOT NULL DEFAULT '',
                content TEXT NOT NULL DEFAULT '',
                char_limit INTEGER NOT NULL DEFAULT 1000,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_intro_user ON self_intro_items(user_id);
        """,
        "self_intro_presets": """
            CREATE TABLE IF NOT EXISTS self_intro_presets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                sort_order INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );
        """,
    }
    existing_tables = {
        row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    for table, ddl in _MISSING_TABLE_MIGRATIONS.items():
        if table not in existing_tables:
            conn.executescript(ddl)

    _COLUMN_MIGRATIONS = [
        ("seeker_profiles", "consent_withdrawn_at", "ALTER TABLE seeker_profiles ADD COLUMN consent_withdrawn_at TEXT"),
        ("seeker_profiles", "photo_path", "ALTER TABLE seeker_profiles ADD COLUMN photo_path TEXT NOT NULL DEFAULT ''"),
        ("seeker_profiles", "disability_visibility", "ALTER TABLE seeker_profiles ADD COLUMN disability_visibility TEXT NOT NULL DEFAULT 'manager_only'"),
    ]
    _col_cache = {}
    for tbl, col, ddl in _COLUMN_MIGRATIONS:
        if tbl not in _col_cache:
            _col_cache[tbl] = {row[1] for row in conn.execute(f"PRAGMA table_info({tbl})").fetchall()}
        if col not in _col_cache[tbl]:
            conn.execute(ddl)
            conn.commit()

    if "self_intro_presets" not in existing_tables or \
       conn.execute("SELECT COUNT(*) FROM self_intro_presets").fetchone()[0] == 0:
        _presets = [
            ("성장과정", "본인의 성장 배경과 가치관을 소개해 주세요"),
            ("지원동기", "이 분야/직무에 관심을 갖게 된 계기를 알려주세요"),
            ("직무역량 및 경험", "관련 경험, 프로젝트, 보유 역량을 구체적으로 작성해 주세요"),
            ("성격의 장단점", "자신의 성격에서 업무에 도움이 되는 점을 중심으로 작성해 주세요"),
            ("입사 후 포부", "입사 후 이루고 싶은 목표를 구체적으로 작성해 주세요"),
            ("프로젝트 경험", "참여한 프로젝트의 역할과 성과를 알려주세요"),
            ("근무 시 참고사항", "업무 수행 시 필요한 배려나 환경을 자유롭게 작성해 주세요"),
        ]
        for idx, (title, desc) in enumerate(_presets):
            conn.execute(
                "INSERT OR IGNORE INTO self_intro_presets (title, description, sort_order) VALUES (?,?,?)",
                (title, desc, idx),
            )
        conn.commit()

    conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ensure_db()
    yield


app = FastAPI(lifespan=lifespan)


@app.exception_handler(404)
async def not_found(request: Request, exc):
    return templates.TemplateResponse(
        request=request, name="error.html",
        context={
            "request": request, "page_title": "404",
            "user_name": request.session.get("user_name", ""),
            "user_role": request.session.get("user_role", "seeker"),
            "status_code": 404,
            "message": "페이지를 찾을 수 없습니다",
            "detail": "요청하신 페이지가 존재하지 않거나 이동되었습니다.",
        },
        status_code=404,
    )


@app.exception_handler(500)
async def server_error(request: Request, exc):
    log.exception("500 에러: %s %s", request.method, request.url.path)
    return templates.TemplateResponse(
        request=request, name="error.html",
        context={
            "request": request, "page_title": "오류",
            "user_name": request.session.get("user_name", ""),
            "user_role": request.session.get("user_role", "seeker"),
            "status_code": 500,
            "message": "서버 오류가 발생했습니다",
            "detail": "잠시 후 다시 시도해 주세요.",
        },
        status_code=500,
    )

_secret = os.getenv("SESSION_SECRET_KEY", "")
if not _secret:
    import warnings
    warnings.warn("SESSION_SECRET_KEY 미설정, 개발용 임시키 사용", stacklevel=1)
    _secret = "recruit-dev-key-insecure"

app.add_middleware(
    SessionMiddleware,
    secret_key=_secret,
)

os.makedirs("static/css", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

from routers import auth, dashboard, company, seeker, info, operator
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(company.router)
app.include_router(company.api_router)
app.include_router(seeker.router)
app.include_router(info.router)
app.include_router(operator.router)
from routers import community
app.include_router(community.router)

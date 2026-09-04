import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
import dotenv

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
    ]
    _col_cache = {}
    for tbl, col, ddl in _COLUMN_MIGRATIONS:
        if tbl not in _col_cache:
            _col_cache[tbl] = {row[1] for row in conn.execute(f"PRAGMA table_info({tbl})").fetchall()}
        if col not in _col_cache[tbl]:
            conn.execute(ddl)
            conn.commit()

    conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ensure_db()
    yield


app = FastAPI(lifespan=lifespan)

_secret = os.getenv("SESSION_SECRET_KEY", "")
if not _secret:
    import warnings
    warnings.warn("SESSION_SECRET_KEY not set, using insecure default for development only", stacklevel=1)
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

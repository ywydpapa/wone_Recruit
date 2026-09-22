import os
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
import dotenv

from core.logger import log
from core.deps import templates
from core.csrf import ensure_token, verify_csrf

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
        "resumes": """
            CREATE TABLE IF NOT EXISTS resumes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL DEFAULT '기본 이력서',
                is_default INTEGER NOT NULL DEFAULT 0,
                desired_job TEXT NOT NULL DEFAULT '',
                work_pref TEXT NOT NULL DEFAULT '무관',
                mobility_type TEXT NOT NULL DEFAULT '',
                commute_max_minutes INTEGER,
                daily_work_hours INTEGER NOT NULL DEFAULT 8,
                preferred_time TEXT NOT NULL DEFAULT '풀타임',
                rest_frequency TEXT NOT NULL DEFAULT '불필요',
                accommodation_needs TEXT NOT NULL DEFAULT '[]',
                experience_summary TEXT NOT NULL DEFAULT '',
                resume_path TEXT NOT NULL DEFAULT '',
                created_at TEXT DEFAULT (datetime('now','localtime')),
                updated_at TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_resumes_user ON resumes(user_id);
        """,
        "resume_educations": """
            CREATE TABLE IF NOT EXISTS resume_educations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resume_id INTEGER NOT NULL REFERENCES resumes(id) ON DELETE CASCADE,
                sort_order INTEGER NOT NULL DEFAULT 0,
                education_level TEXT NOT NULL DEFAULT '',
                school_name TEXT NOT NULL DEFAULT '',
                major TEXT NOT NULL DEFAULT '',
                start_date TEXT NOT NULL DEFAULT '',
                end_date TEXT NOT NULL DEFAULT '',
                graduation_status TEXT NOT NULL DEFAULT '',
                gpa TEXT NOT NULL DEFAULT '',
                gpa_scale TEXT NOT NULL DEFAULT '',
                is_transfer INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_resume_edu ON resume_educations(resume_id);
        """,
        "resume_careers": """
            CREATE TABLE IF NOT EXISTS resume_careers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resume_id INTEGER NOT NULL REFERENCES resumes(id) ON DELETE CASCADE,
                sort_order INTEGER NOT NULL DEFAULT 0,
                company_name TEXT NOT NULL DEFAULT '',
                department TEXT NOT NULL DEFAULT '',
                position TEXT NOT NULL DEFAULT '',
                start_date TEXT NOT NULL DEFAULT '',
                end_date TEXT NOT NULL DEFAULT '',
                is_current INTEGER NOT NULL DEFAULT 0,
                employment_type TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_resume_career ON resume_careers(resume_id);
        """,
        "resume_certifications": """
            CREATE TABLE IF NOT EXISTS resume_certifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resume_id INTEGER NOT NULL REFERENCES resumes(id) ON DELETE CASCADE,
                sort_order INTEGER NOT NULL DEFAULT 0,
                cert_name TEXT NOT NULL,
                cert_date TEXT NOT NULL DEFAULT '',
                issuing_org TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_resume_cert ON resume_certifications(resume_id);
        """,
        "resume_languages": """
            CREATE TABLE IF NOT EXISTS resume_languages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resume_id INTEGER NOT NULL REFERENCES resumes(id) ON DELETE CASCADE,
                sort_order INTEGER NOT NULL DEFAULT 0,
                language TEXT NOT NULL DEFAULT '',
                test_name TEXT NOT NULL DEFAULT '',
                score TEXT NOT NULL DEFAULT '',
                level TEXT NOT NULL DEFAULT '',
                test_date TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_resume_lang ON resume_languages(resume_id);
        """,
        "resume_awards": """
            CREATE TABLE IF NOT EXISTS resume_awards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resume_id INTEGER NOT NULL REFERENCES resumes(id) ON DELETE CASCADE,
                sort_order INTEGER NOT NULL DEFAULT 0,
                category TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL DEFAULT '',
                organizer TEXT NOT NULL DEFAULT '',
                activity_date TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_resume_award ON resume_awards(resume_id);
        """,
        "resume_portfolios": """
            CREATE TABLE IF NOT EXISTS resume_portfolios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resume_id INTEGER NOT NULL REFERENCES resumes(id) ON DELETE CASCADE,
                sort_order INTEGER NOT NULL DEFAULT 0,
                link_type TEXT NOT NULL DEFAULT '',
                url TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_resume_port ON resume_portfolios(resume_id);
        """,
        "resume_intros": """
            CREATE TABLE IF NOT EXISTS resume_intros (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resume_id INTEGER NOT NULL REFERENCES resumes(id) ON DELETE CASCADE,
                sort_order INTEGER NOT NULL DEFAULT 0,
                title TEXT NOT NULL DEFAULT '',
                content TEXT NOT NULL DEFAULT '',
                char_limit INTEGER NOT NULL DEFAULT 1000
            );
            CREATE INDEX IF NOT EXISTS idx_resume_intro ON resume_intros(resume_id);
        """,
        "saved_searches": """
            CREATE TABLE IF NOT EXISTS saved_searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL DEFAULT '',
                filters TEXT NOT NULL DEFAULT '{}',
                last_checked_at TEXT DEFAULT (datetime('now','localtime')),
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_saved_searches_user ON saved_searches(user_id);
        """,
        "consultations": """
            CREATE TABLE IF NOT EXISTS consultations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seeker_user_id INTEGER NOT NULL,
                operator_user_id INTEGER NOT NULL,
                physical_note TEXT NOT NULL DEFAULT '',
                sensory_note TEXT NOT NULL DEFAULT '',
                cognitive_note TEXT NOT NULL DEFAULT '',
                communication_note TEXT NOT NULL DEFAULT '',
                work_capacity_note TEXT NOT NULL DEFAULT '',
                environment_note TEXT NOT NULL DEFAULT '',
                summary TEXT NOT NULL DEFAULT '',
                created_at TEXT DEFAULT (datetime('now','localtime')),
                updated_at TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_consultations_seeker ON consultations(seeker_user_id);
            CREATE INDEX IF NOT EXISTS idx_consultations_operator ON consultations(operator_user_id);
        """,
        "manager_assignments": """
            CREATE TABLE IF NOT EXISTS manager_assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                manager_user_id INTEGER NOT NULL,
                seeker_user_id INTEGER NOT NULL UNIQUE,
                assigned_by INTEGER NOT NULL,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_mgr_assign_manager ON manager_assignments(manager_user_id);
        """,
        "consultation_sessions": """
            CREATE TABLE IF NOT EXISTS consultation_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seeker_user_id INTEGER NOT NULL,
                manager_user_id INTEGER NOT NULL,
                session_type TEXT NOT NULL DEFAULT 'other',
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_consult_session_seeker ON consultation_sessions(seeker_user_id);
            CREATE INDEX IF NOT EXISTS idx_consult_session_manager ON consultation_sessions(manager_user_id);
        """,
        "company_reviews": """
            CREATE TABLE IF NOT EXISTS company_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
                content TEXT NOT NULL DEFAULT '',
                pros TEXT NOT NULL DEFAULT '',
                cons TEXT NOT NULL DEFAULT '',
                created_at TEXT DEFAULT (datetime('now','localtime')),
                UNIQUE(company_id, user_id)
            );
            CREATE INDEX IF NOT EXISTS idx_reviews_company ON company_reviews(company_id);
        """,
        "placement_followups": """
            CREATE TABLE IF NOT EXISTS placement_followups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                placement_id INTEGER NOT NULL,
                followup_type TEXT NOT NULL,
                due_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                notes TEXT NOT NULL DEFAULT '',
                completed_at TEXT,
                completed_by INTEGER,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_followup_placement ON placement_followups(placement_id);
            CREATE INDEX IF NOT EXISTS idx_followup_status ON placement_followups(status, due_date);
        """,
        "support_categories": """
            CREATE TABLE IF NOT EXISTS support_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                sort_order INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS support_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER NOT NULL REFERENCES support_categories(id),
                name TEXT NOT NULL,
                description TEXT,
                sort_order INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS support_item_capabilities (
                support_item_id INTEGER NOT NULL REFERENCES support_items(id),
                capability TEXT NOT NULL,
                impact TEXT NOT NULL CHECK(impact IN ('ok','at','limit','no')),
                PRIMARY KEY (support_item_id, capability)
            );
            CREATE TABLE IF NOT EXISTS seeker_support_items (
                user_id INTEGER NOT NULL REFERENCES users(id),
                support_item_id INTEGER NOT NULL REFERENCES support_items(id),
                PRIMARY KEY (user_id, support_item_id)
            );
            INSERT OR IGNORE INTO support_categories (id, name, sort_order) VALUES
                (1, '시각 보조', 1),
                (2, '청각 보조', 2),
                (3, '이동 보조', 3),
                (4, '상지 보조', 4),
                (5, '인지/정서 지원', 5),
                (6, '건강관리 지원', 6);
            INSERT OR IGNORE INTO support_items (id, category_id, name, description, sort_order) VALUES
                (1,  1, '화면낭독기(스크린리더)',       '화면 내용을 음성으로 출력',          1),
                (2,  1, '화면확대 소프트웨어',           '화면 내용을 확대 표시',               2),
                (3,  1, '점자정보단말기',                '화면 내용을 점자로 출력',             3),
                (4,  1, '독서확대기/전자돋보기',         '문서를 확대하여 표시',                4),
                (5,  2, '보청기',                        '소리를 증폭',                         1),
                (6,  2, '인공와우',                      '전기 신호로 청각 보조',               2),
                (7,  2, '음성인식 자막 소프트웨어',      '음성을 실시간 자막으로 변환',         3),
                (8,  2, '영상전화(수어통역)',             '수어통역사를 통한 전화',              4),
                (9,  3, '수동휠체어',                    '자력으로 이동',                       1),
                (10, 3, '전동휠체어',                    '전동 이동',                           2),
                (11, 3, '보행보조기(목발/워커)',          '보행 지원',                           3),
                (12, 3, '의족',                          '하지 보조',                           4),
                (13, 4, '특수 키보드/마우스',            '한 손 또는 제한된 손 기능으로 입력',  1),
                (14, 4, '음성인식 입력 소프트웨어',      '음성으로 텍스트 입력',                2),
                (15, 4, '의수/상지보조기',               '상지 기능 보조',                      3),
                (16, 4, '머리/시선 추적 입력장치',       '머리 움직임이나 시선으로 커서 조작',  4),
                (17, 5, '구조화된 업무 지시 필요',       '단계별로 분리된 명확한 지시',         1),
                (18, 5, '업무 관리 보조(체크리스트/타이머)', '일정, 순서 관리 지원',            2),
                (19, 5, '정서 안정 지원(상담/휴식)',     '정기 상담, 감정 조절 지원',           3),
                (20, 5, '감각 자극 조절 환경',           '소음/조명 조절 가능한 환경',          4),
                (21, 6, '정기 투석',                     '주 2-3회 투석 일정 필요',             1),
                (22, 6, '정기 복약 관리',                '근무 중 투약 시간 보장',              2),
                (23, 6, '호흡 보조기기',                 '산소공급기 등',                       3),
                (24, 6, '장루/요루 관리',                '위생 관리 시간 및 시설 필요',         4),
                (25, 6, '휴식 시간 보장(1-2시간 간격)', '잦은 휴식 필요',                      5);
            INSERT OR IGNORE INTO support_item_capabilities (support_item_id, capability, impact) VALUES
                (1,  'visual_acuity',     'no'),
                (1,  'screen_use',        'at'),
                (2,  'visual_acuity',     'limit'),
                (2,  'screen_use',        'at'),
                (3,  'visual_acuity',     'no'),
                (3,  'screen_use',        'at'),
                (4,  'visual_acuity',     'limit'),
                (4,  'reading',           'at'),
                (5,  'hearing',           'limit'),
                (5,  'verbal_comm',       'at'),
                (6,  'hearing',           'at'),
                (6,  'verbal_comm',       'at'),
                (7,  'hearing',           'limit'),
                (7,  'verbal_comm',       'limit'),
                (8,  'hearing',           'no'),
                (8,  'verbal_comm',       'no'),
                (8,  'written_comm',      'ok'),
                (9,  'lower_mobility',    'no'),
                (9,  'upper_mobility',    'ok'),
                (9,  'sitting_endurance', 'at'),
                (10, 'lower_mobility',    'no'),
                (10, 'upper_mobility',    'limit'),
                (10, 'sitting_endurance', 'at'),
                (11, 'lower_mobility',    'limit'),
                (11, 'standing_endurance','limit'),
                (12, 'lower_mobility',    'at'),
                (12, 'standing_endurance','limit'),
                (13, 'fine_motor',        'limit'),
                (13, 'typing',            'at'),
                (14, 'fine_motor',        'no'),
                (14, 'typing',            'at'),
                (15, 'fine_motor',        'limit'),
                (15, 'lifting',           'limit'),
                (16, 'fine_motor',        'no'),
                (16, 'typing',            'at'),
                (16, 'upper_mobility',    'no'),
                (17, 'complex_reasoning', 'limit'),
                (17, 'task_switching',    'limit'),
                (18, 'time_management',   'at'),
                (18, 'task_switching',    'at'),
                (19, 'stress_tolerance',  'limit'),
                (19, 'interpersonal',     'limit'),
                (20, 'concentration',     'at'),
                (20, 'stress_tolerance',  'at'),
                (21, 'work_continuity',   'limit'),
                (21, 'physical_endurance','limit'),
                (22, 'work_continuity',   'at'),
                (23, 'physical_endurance','limit'),
                (24, 'work_continuity',   'at'),
                (25, 'work_continuity',   'limit'),
                (25, 'sitting_endurance', 'limit');
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
        ("seeker_profiles", "birth_date", "ALTER TABLE seeker_profiles ADD COLUMN birth_date TEXT NOT NULL DEFAULT ''"),
        ("candidacies", "resume_id", "ALTER TABLE candidacies ADD COLUMN resume_id INTEGER"),
        ("candidacies", "resume_snapshot", "ALTER TABLE candidacies ADD COLUMN resume_snapshot TEXT NOT NULL DEFAULT ''"),
        ("resumes", "photo_path", "ALTER TABLE resumes ADD COLUMN photo_path TEXT NOT NULL DEFAULT ''"),
        ("companies", "ceo", "ALTER TABLE companies ADD COLUMN ceo TEXT NOT NULL DEFAULT ''"),
        ("companies", "est_year", "ALTER TABLE companies ADD COLUMN est_year INTEGER"),
        ("companies", "biz_type", "ALTER TABLE companies ADD COLUMN biz_type TEXT NOT NULL DEFAULT ''"),
        ("companies", "address", "ALTER TABLE companies ADD COLUMN address TEXT NOT NULL DEFAULT ''"),
        ("job_postings", "tasks", "ALTER TABLE job_postings ADD COLUMN tasks TEXT NOT NULL DEFAULT ''"),
        ("job_postings", "tools", "ALTER TABLE job_postings ADD COLUMN tools TEXT NOT NULL DEFAULT ''"),
        ("job_postings", "experience_level", "ALTER TABLE job_postings ADD COLUMN experience_level TEXT NOT NULL DEFAULT '무관'"),
        ("job_postings", "education", "ALTER TABLE job_postings ADD COLUMN education TEXT NOT NULL DEFAULT ''"),
        ("job_postings", "hiring_process", "ALTER TABLE job_postings ADD COLUMN hiring_process TEXT NOT NULL DEFAULT ''"),
        ("job_postings", "headcount", "ALTER TABLE job_postings ADD COLUMN headcount TEXT NOT NULL DEFAULT ''"),
        ("job_postings", "preferred", "ALTER TABLE job_postings ADD COLUMN preferred TEXT NOT NULL DEFAULT ''"),
        ("companies", "approval_status", "ALTER TABLE companies ADD COLUMN approval_status TEXT NOT NULL DEFAULT 'pending'"),
        ("companies", "biz_doc_path", "ALTER TABLE companies ADD COLUMN biz_doc_path TEXT NOT NULL DEFAULT ''"),
        ("companies", "rejection_reason", "ALTER TABLE companies ADD COLUMN rejection_reason TEXT NOT NULL DEFAULT ''"),
        ("companies", "contact_phone", "ALTER TABLE companies ADD COLUMN contact_phone TEXT NOT NULL DEFAULT ''"),
        ("companies", "contact_email", "ALTER TABLE companies ADD COLUMN contact_email TEXT NOT NULL DEFAULT ''"),
        ("companies", "hr_name", "ALTER TABLE companies ADD COLUMN hr_name TEXT NOT NULL DEFAULT ''"),
        ("companies", "hr_position", "ALTER TABLE companies ADD COLUMN hr_position TEXT NOT NULL DEFAULT ''"),
        ("companies", "hr_phone", "ALTER TABLE companies ADD COLUMN hr_phone TEXT NOT NULL DEFAULT ''"),
        ("companies", "hr_email", "ALTER TABLE companies ADD COLUMN hr_email TEXT NOT NULL DEFAULT ''"),
        ("job_postings", "rejection_reason", "ALTER TABLE job_postings ADD COLUMN rejection_reason TEXT NOT NULL DEFAULT ''"),
        ("candidacies", "assigned_manager_id", "ALTER TABLE candidacies ADD COLUMN assigned_manager_id INTEGER"),
        ("placements", "assigned_manager_id", "ALTER TABLE placements ADD COLUMN assigned_manager_id INTEGER"),
        ("placements", "status", "ALTER TABLE placements ADD COLUMN status TEXT NOT NULL DEFAULT 'active'"),
        ("placements", "end_date", "ALTER TABLE placements ADD COLUMN end_date TEXT"),
        ("company_reviews", "pros", "ALTER TABLE company_reviews ADD COLUMN pros TEXT NOT NULL DEFAULT ''"),
        ("company_reviews", "cons", "ALTER TABLE company_reviews ADD COLUMN cons TEXT NOT NULL DEFAULT ''"),
        ("consultation_sessions", "scheduled_at", "ALTER TABLE consultation_sessions ADD COLUMN scheduled_at TEXT"),
        ("consultation_sessions", "method", "ALTER TABLE consultation_sessions ADD COLUMN method TEXT NOT NULL DEFAULT 'in_person'"),
        ("consultation_sessions", "location", "ALTER TABLE consultation_sessions ADD COLUMN location TEXT NOT NULL DEFAULT ''"),
        ("consultation_sessions", "status", "ALTER TABLE consultation_sessions ADD COLUMN status TEXT NOT NULL DEFAULT 'completed'"),
    ]
    _col_cache = {}
    for tbl, col, ddl in _COLUMN_MIGRATIONS:
        if tbl not in _col_cache:
            _col_cache[tbl] = {row[1] for row in conn.execute(f"PRAGMA table_info({tbl})").fetchall()}
        if col not in _col_cache[tbl]:
            conn.execute(ddl)
            conn.commit()

    try:
        conn.execute("UPDATE companies SET approval_status='approved' WHERE approval_status='pending' AND biz_no != ''")
        conn.commit()
    except:
        pass

    _jp_cols = {row[1] for row in conn.execute("PRAGMA table_info(job_postings)").fetchall()}
    if "requirements" in _jp_cols and "qualifications" not in _jp_cols:
        conn.execute("ALTER TABLE job_postings RENAME COLUMN requirements TO qualifications")
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

    from datetime import date
    today = date.today().isoformat()
    conn.execute(
        "UPDATE job_postings SET status='closed' WHERE status='open' AND deadline != '' AND deadline < ?",
        (today,),
    )
    conn.commit()

    conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ensure_db()
    from core.jobs import close_expired_jobs
    close_expired_jobs()
    yield


app = FastAPI(lifespan=lifespan, dependencies=[Depends(verify_csrf)])


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    status = exc.status_code
    if status == 403:
        tpl = "errors/403.html"
        title = "접근 권한 없음"
    elif status == 404:
        tpl = "errors/404.html"
        title = "페이지를 찾을 수 없음"
    else:
        tpl = "errors/500.html"
        title = "서버 오류"
    try:
        user_name = request.session.get("name", "")
        user_role = request.session.get("role", "")
    except Exception:
        user_name = ""
        user_role = ""
    return templates.TemplateResponse(
        request=request, name=tpl,
        status_code=status,
        context={
            "request": request, "page_title": title,
            "user_name": user_name, "user_role": user_role,
            "status_code": status,
            "detail": str(exc.detail) if exc.detail else "",
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    log.exception("500 에러: %s %s", request.method, request.url.path)
    try:
        user_name = request.session.get("name", "")
        user_role = request.session.get("role", "")
    except Exception:
        user_name = ""
        user_role = ""
    return templates.TemplateResponse(
        request=request, name="errors/500.html",
        status_code=500,
        context={
            "request": request, "page_title": "서버 오류",
            "user_name": user_name, "user_role": user_role,
            "status_code": 500,
            "detail": "",
        },
    )

_secret = os.getenv("SESSION_SECRET_KEY")
if not _secret:
    raise RuntimeError("SESSION_SECRET_KEY 환경변수 필수")

class CSRFTokenMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        token = ensure_token(request)
        request.state.csrf_token = token
        return await call_next(request)


app.add_middleware(CSRFTokenMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=_secret,
    https_only=os.getenv("ENVIRONMENT") == "production",
    same_site="strict",
)

os.makedirs("static/css", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

from routers import auth, dashboard, company, seeker, info, operator, resume, community, manager, messages
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(company.router)
app.include_router(company.api_router)
app.include_router(seeker.router)
app.include_router(resume.router)
app.include_router(info.router)
app.include_router(operator.router)
app.include_router(community.router)
app.include_router(messages.router)
app.include_router(manager.router)

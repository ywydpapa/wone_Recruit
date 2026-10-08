import json
import os
import sys
from datetime import date, timedelta

from core.db import get_sqlite
from core.security import hash_password

DISABILITY_TYPES = [
    "지체", "뇌병변", "시각", "청각", "언어", "안면", "신장", "심장",
    "간", "호흡기", "장루·요루", "뇌전증", "지적", "자폐성", "정신",
]


# 기동 시 close_expired_jobs()로 시드 공고가 마감되지 않도록 마감일을 생성일 기준으로 둠
def dl(days):
    return (date.today() + timedelta(days=days)).isoformat()


def init():
    conn = get_sqlite()

    for t in ("password_resets", "bookmarks", "notifications", "seeker_certifications",
              "education_history", "career_history", "language_skills",
              "awards_activities", "portfolio_links", "self_intro_items", "self_intro_presets",
              "resume_educations", "resume_careers", "resume_certifications", "resume_languages",
              "resume_awards", "resume_portfolios", "resume_intros", "resumes",
              "consultations", "job_categories", "access_log", "placements", "status_history", "candidacies",
              "job_postings", "seeker_profiles", "company_photos", "companies",
              "regions", "levy_rates", "disability_types", "users",
              "job_applications"):
        conn.execute(f"DROP TABLE IF EXISTS {t}")

    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        name TEXT NOT NULL DEFAULT '',
        phone TEXT NOT NULL DEFAULT '',
        email TEXT DEFAULT '',
        role TEXT NOT NULL DEFAULT 'seeker',
        agreed_terms_at TEXT,
        agreed_privacy_at TEXT,
        agreed_marketing_at TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime')),
        is_deleted INTEGER NOT NULL DEFAULT 0,
        deleted_at TEXT,
        accessibility_settings TEXT NOT NULL DEFAULT '{}',
        notify_settings TEXT NOT NULL DEFAULT '{}',
        must_change_password INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS disability_types (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    );
    CREATE TABLE IF NOT EXISTS regions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sido TEXT NOT NULL,
        sigungu TEXT NOT NULL,
        UNIQUE(sido, sigungu)
    );
    CREATE INDEX IF NOT EXISTS idx_regions_sido ON regions(sido);
    CREATE TABLE IF NOT EXISTS seeker_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL,
        disability_type_id INTEGER,
        severity TEXT NOT NULL DEFAULT '경증',
        gender TEXT NOT NULL DEFAULT '',
        birth_year INTEGER,
        birth_date TEXT NOT NULL DEFAULT '',
        region_id INTEGER,
        education_level TEXT NOT NULL DEFAULT '',
        school_name TEXT NOT NULL DEFAULT '',
        major TEXT NOT NULL DEFAULT '',
        career_years INTEGER NOT NULL DEFAULT 0,
        recent_company TEXT NOT NULL DEFAULT '',
        recent_job_title TEXT NOT NULL DEFAULT '',
        experience_summary TEXT NOT NULL DEFAULT '',
        desired_job TEXT NOT NULL DEFAULT '',
        work_pref TEXT NOT NULL DEFAULT '무관',
        mobility_type TEXT NOT NULL DEFAULT '',
        commute_max_minutes INTEGER,
        communication_pref TEXT NOT NULL DEFAULT '[]',
        assistive_tech TEXT NOT NULL DEFAULT '[]',
        target_categories TEXT NOT NULL DEFAULT '[]',
        match_note TEXT NOT NULL DEFAULT '',
        match_updated_at TEXT,
        match_updated_by INTEGER,
        daily_work_hours INTEGER NOT NULL DEFAULT 8,
        preferred_time TEXT NOT NULL DEFAULT '풀타임',
        rest_frequency TEXT NOT NULL DEFAULT '불필요',
        accommodation_needs TEXT NOT NULL DEFAULT '[]',
        resume_path TEXT NOT NULL DEFAULT '',
        photo_path TEXT NOT NULL DEFAULT '',
        disability_visibility TEXT NOT NULL DEFAULT 'manager_only',
        consent_sensitive INTEGER NOT NULL DEFAULT 0,
        consented_at TEXT,
        consent_withdrawn_at TEXT,
        updated_at TEXT DEFAULT (datetime('now','localtime'))
    );
    CREATE TABLE IF NOT EXISTS seeker_certifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        cert_name TEXT NOT NULL,
        cert_date TEXT NOT NULL DEFAULT '',
        issuing_org TEXT NOT NULL DEFAULT '',
        file_path TEXT NOT NULL DEFAULT '',
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );
    CREATE INDEX IF NOT EXISTS idx_cert_user ON seeker_certifications(user_id);
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
    CREATE TABLE IF NOT EXISTS self_intro_presets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        sort_order INTEGER NOT NULL DEFAULT 0,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );
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
        photo_path TEXT NOT NULL DEFAULT '',
        created_at TEXT DEFAULT (datetime('now','localtime')),
        updated_at TEXT DEFAULT (datetime('now','localtime'))
    );
    CREATE INDEX IF NOT EXISTS idx_resumes_user ON resumes(user_id);
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
    CREATE TABLE IF NOT EXISTS resume_certifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        resume_id INTEGER NOT NULL REFERENCES resumes(id) ON DELETE CASCADE,
        sort_order INTEGER NOT NULL DEFAULT 0,
        cert_name TEXT NOT NULL,
        cert_date TEXT NOT NULL DEFAULT '',
        issuing_org TEXT NOT NULL DEFAULT ''
    );
    CREATE INDEX IF NOT EXISTS idx_resume_cert ON resume_certifications(resume_id);
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
    CREATE TABLE IF NOT EXISTS resume_portfolios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        resume_id INTEGER NOT NULL REFERENCES resumes(id) ON DELETE CASCADE,
        sort_order INTEGER NOT NULL DEFAULT 0,
        link_type TEXT NOT NULL DEFAULT '',
        url TEXT NOT NULL DEFAULT '',
        description TEXT NOT NULL DEFAULT ''
    );
    CREATE INDEX IF NOT EXISTS idx_resume_port ON resume_portfolios(resume_id);
    CREATE TABLE IF NOT EXISTS resume_intros (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        resume_id INTEGER NOT NULL REFERENCES resumes(id) ON DELETE CASCADE,
        sort_order INTEGER NOT NULL DEFAULT 0,
        title TEXT NOT NULL DEFAULT '',
        content TEXT NOT NULL DEFAULT '',
        char_limit INTEGER NOT NULL DEFAULT 1000
    );
    CREATE INDEX IF NOT EXISTS idx_resume_intro ON resume_intros(resume_id);
    CREATE TABLE IF NOT EXISTS companies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL,
        company_name TEXT NOT NULL DEFAULT '',
        biz_no TEXT NOT NULL DEFAULT '',
        industry TEXT NOT NULL DEFAULT '',
        employee_count INTEGER NOT NULL DEFAULT 0,
        disabled_count INTEGER NOT NULL DEFAULT 0,
        region_id INTEGER,
        intro TEXT NOT NULL DEFAULT '',
        website TEXT NOT NULL DEFAULT '',
        company_size TEXT NOT NULL DEFAULT '',
        accessibility_facilities TEXT NOT NULL DEFAULT '[]',
        accessibility_note TEXT NOT NULL DEFAULT '',
        hiring_experience INTEGER NOT NULL DEFAULT 0,
        retention_note TEXT NOT NULL DEFAULT '',
        benefits TEXT NOT NULL DEFAULT '',
        logo_path TEXT NOT NULL DEFAULT '',
        ceo TEXT NOT NULL DEFAULT '',
        est_year INTEGER,
        biz_type TEXT NOT NULL DEFAULT '',
        address TEXT NOT NULL DEFAULT '',
        approval_status TEXT NOT NULL DEFAULT 'pending',
        biz_doc_path TEXT NOT NULL DEFAULT '',
        rejection_reason TEXT NOT NULL DEFAULT '',
        reverify INTEGER NOT NULL DEFAULT 0,
        tagline TEXT NOT NULL DEFAULT '',
        description TEXT NOT NULL DEFAULT '',
        esg_items TEXT NOT NULL DEFAULT '[]',
        esg_note TEXT NOT NULL DEFAULT '',
        remote_ok INTEGER NOT NULL DEFAULT 0,
        flexible_ok INTEGER NOT NULL DEFAULT 0,
        shared_office_ok INTEGER NOT NULL DEFAULT 0,
        work_env_note TEXT NOT NULL DEFAULT '',
        updated_at TEXT DEFAULT (datetime('now','localtime'))
    );
    CREATE TABLE IF NOT EXISTS company_photos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER NOT NULL REFERENCES companies(id),
        file_path TEXT NOT NULL,
        caption TEXT NOT NULL DEFAULT '',
        sort_order INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS job_categories (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        major_code          TEXT NOT NULL,
        major_name_ko       TEXT NOT NULL,
        major_name_en       TEXT NOT NULL,
        minor_code          TEXT NOT NULL,
        minor_name_ko       TEXT NOT NULL,
        minor_name_en       TEXT NOT NULL,
        description         TEXT NOT NULL DEFAULT '',
        daily_tasks         TEXT NOT NULL DEFAULT '',
        tools_software      TEXT NOT NULL DEFAULT '[]',
        min_qualifications  TEXT NOT NULL DEFAULT '[]',
        training_days       INTEGER NOT NULL DEFAULT 7,
        difficulty          TEXT NOT NULL DEFAULT 'mid',
        work_hours_type     TEXT NOT NULL DEFAULT 'full',
        min_hours_per_day   INTEGER NOT NULL DEFAULT 4,
        shift_required      INTEGER NOT NULL DEFAULT 0,
        onsite_required     INTEGER NOT NULL DEFAULT 0,
        kpi_metrics         TEXT NOT NULL DEFAULT '[]',
        salary_min          INTEGER NOT NULL DEFAULT 2096270,
        salary_max          INTEGER NOT NULL DEFAULT 2096270,
        salary_basis        TEXT NOT NULL DEFAULT 'full_8h',
        fit_physical_lower  INTEGER NOT NULL DEFAULT 3,
        fit_physical_upper  INTEGER NOT NULL DEFAULT 2,
        fit_hearing         INTEGER NOT NULL DEFAULT 3,
        fit_visual_low      INTEGER NOT NULL DEFAULT 1,
        fit_intellectual    INTEGER NOT NULL DEFAULT 1,
        fit_autism           INTEGER NOT NULL DEFAULT 2,
        fit_mental          INTEGER NOT NULL DEFAULT 2,
        fit_internal_organ  INTEGER NOT NULL DEFAULT 3,
        fit_brain_lesion    INTEGER NOT NULL DEFAULT 2,
        fit_notes           TEXT NOT NULL DEFAULT '',
        market_demand       TEXT NOT NULL DEFAULT 'stable',
        is_wone_exclusive   INTEGER NOT NULL DEFAULT 0,
        created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(major_code, minor_code)
    );
    CREATE TABLE IF NOT EXISTS job_postings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        category_id INTEGER,
        region_id INTEGER,
        employment_type TEXT NOT NULL DEFAULT '정규직',
        remote_available INTEGER NOT NULL DEFAULT 0,
        work_start_time TEXT NOT NULL DEFAULT '09:00',
        work_end_time TEXT NOT NULL DEFAULT '18:00',
        work_days TEXT NOT NULL DEFAULT '월~금',
        flexible_hours INTEGER NOT NULL DEFAULT 0,
        salary TEXT NOT NULL DEFAULT '',
        deadline TEXT NOT NULL DEFAULT '',
        accommodations_provided TEXT NOT NULL DEFAULT '[]',
        accommodations_note TEXT NOT NULL DEFAULT '',
        preferred_disability TEXT NOT NULL DEFAULT '[]',
        preferred_severity TEXT NOT NULL DEFAULT '무관',
        min_work_hours INTEGER NOT NULL DEFAULT 8,
        benefits TEXT NOT NULL DEFAULT '',
        qualifications TEXT NOT NULL DEFAULT '',
        preferred TEXT NOT NULL DEFAULT '',
        tasks TEXT NOT NULL DEFAULT '',
        tools TEXT NOT NULL DEFAULT '',
        experience_level TEXT NOT NULL DEFAULT '무관',
        education TEXT NOT NULL DEFAULT '',
        hiring_process TEXT NOT NULL DEFAULT '',
        headcount TEXT NOT NULL DEFAULT '',
        description TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'draft',
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );
    CREATE TABLE IF NOT EXISTS candidacies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL,
        seeker_user_id INTEGER NOT NULL,
        source TEXT NOT NULL DEFAULT 'direct',
        status TEXT NOT NULL DEFAULT 'pending',
        match_stage TEXT,
        cover_letter TEXT NOT NULL DEFAULT '',
        created_at TEXT DEFAULT (datetime('now','localtime')),
        updated_at TEXT DEFAULT (datetime('now','localtime')),
        UNIQUE(job_id, seeker_user_id)
    );
    CREATE TABLE IF NOT EXISTS status_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        candidacy_id INTEGER NOT NULL,
        from_status TEXT NOT NULL DEFAULT '',
        to_status TEXT NOT NULL DEFAULT '',
        actor_id INTEGER,
        comment TEXT NOT NULL DEFAULT '',
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );
    CREATE TABLE IF NOT EXISTS placements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        candidacy_id INTEGER UNIQUE NOT NULL,
        job_id INTEGER NOT NULL,
        seeker_user_id INTEGER NOT NULL,
        company_id INTEGER NOT NULL,
        start_date TEXT NOT NULL DEFAULT '',
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );
    CREATE TABLE IF NOT EXISTS levy_rates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        year INTEGER NOT NULL,
        rate_type TEXT NOT NULL,
        amount REAL NOT NULL,
        UNIQUE(year, rate_type)
    );
    CREATE TABLE IF NOT EXISTS access_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        viewer_id INTEGER NOT NULL,
        seeker_user_id INTEGER NOT NULL,
        purpose TEXT NOT NULL DEFAULT '',
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );
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
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        message TEXT NOT NULL,
        link TEXT NOT NULL DEFAULT '',
        kind TEXT NOT NULL DEFAULT 'system',
        is_read INTEGER NOT NULL DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );
    CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, is_read);
    CREATE TABLE IF NOT EXISTS notices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        audience TEXT NOT NULL DEFAULT 'all',
        pinned INTEGER NOT NULL DEFAULT 0,
        views INTEGER NOT NULL DEFAULT 0,
        author_id INTEGER NOT NULL,
        created_at TEXT DEFAULT (datetime('now','localtime')),
        updated_at TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_notices_audience ON notices(audience, pinned);
    CREATE TABLE IF NOT EXISTS consult_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        seeker_user_id INTEGER NOT NULL,
        category TEXT NOT NULL DEFAULT 'job',
        content TEXT NOT NULL DEFAULT '',
        method TEXT NOT NULL DEFAULT 'phone',
        preferred_time TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'pending',
        manager_user_id INTEGER,
        session_id INTEGER,
        reply TEXT NOT NULL DEFAULT '',
        created_at TEXT DEFAULT (datetime('now','localtime')),
        handled_at TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_consult_req_seeker ON consult_requests(seeker_user_id);
    CREATE INDEX IF NOT EXISTS idx_consult_req_status ON consult_requests(status);
    CREATE TABLE IF NOT EXISTS company_duties (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER NOT NULL,
        category_id INTEGER,
        title TEXT NOT NULL,
        tasks TEXT NOT NULL DEFAULT '',
        tools TEXT NOT NULL DEFAULT '',
        difficulty TEXT NOT NULL DEFAULT 'mid',
        remote_ok INTEGER NOT NULL DEFAULT 1,
        fit TEXT NOT NULL DEFAULT '{}',
        note TEXT NOT NULL DEFAULT '',
        analysis_status TEXT NOT NULL DEFAULT 'none',
        analysis_request TEXT NOT NULL DEFAULT '',
        analysis_note TEXT NOT NULL DEFAULT '',
        analyzed_by INTEGER,
        analyzed_at TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime')),
        updated_at TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_company_duties_company ON company_duties(company_id);
    CREATE TABLE IF NOT EXISTS bookmarks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        job_id INTEGER NOT NULL,
        created_at TEXT DEFAULT (datetime('now','localtime')),
        UNIQUE(user_id, job_id)
    );
    CREATE INDEX IF NOT EXISTS idx_bookmarks_user ON bookmarks(user_id);
    CREATE TABLE IF NOT EXISTS recent_views (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        job_id INTEGER NOT NULL,
        viewed_at TEXT DEFAULT (datetime('now','localtime')),
        UNIQUE(user_id, job_id)
    );
    CREATE INDEX IF NOT EXISTS idx_recent_views_user ON recent_views(user_id);
    CREATE TABLE IF NOT EXISTS company_pipeline_stages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER NOT NULL,
        stage_key TEXT NOT NULL,
        label TEXT NOT NULL,
        sort_order INTEGER NOT NULL,
        UNIQUE(company_id, stage_key)
    );
    CREATE TABLE IF NOT EXISTS inquiries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        category TEXT NOT NULL DEFAULT '',
        subject TEXT NOT NULL,
        content TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'open',
        answer TEXT NOT NULL DEFAULT '',
        answered_by INTEGER,
        answered_at TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );
    CREATE INDEX IF NOT EXISTS idx_inquiries_user ON inquiries(user_id);
    CREATE INDEX IF NOT EXISTS idx_inquiries_status ON inquiries(status);
    CREATE TABLE IF NOT EXISTS password_resets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        token_hash TEXT UNIQUE NOT NULL,
        expires_at TEXT NOT NULL,
        used_at TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );
    CREATE INDEX IF NOT EXISTS idx_password_resets_user ON password_resets(user_id);
    """)

    for name in DISABILITY_TYPES:
        conn.execute("INSERT OR IGNORE INTO disability_types (name) VALUES (?)", (name,))

    _REGIONS_DATA = {
        "서울특별시": ["종로구", "중구", "용산구", "성동구", "광진구", "동대문구", "중랑구", "성북구", "강북구", "도봉구", "노원구", "은평구", "서대문구", "마포구", "양천구", "강서구", "구로구", "금천구", "영등포구", "동작구", "관악구", "서초구", "강남구", "송파구", "강동구"],
        "부산광역시": ["중구", "서구", "동구", "영도구", "부산진구", "동래구", "남구", "북구", "해운대구", "사하구", "금정구", "강서구", "연제구", "수영구", "사상구", "기장군"],
        "대구광역시": ["중구", "동구", "서구", "남구", "북구", "수성구", "달서구", "달성군", "군위군"],
        "인천광역시": ["제물포구", "영종구", "미추홀구", "연수구", "남동구", "부평구", "계양구", "서해구", "검단구", "강화군", "옹진군"],
        "대전광역시": ["동구", "중구", "서구", "유성구", "대덕구"],
        "울산광역시": ["중구", "남구", "동구", "북구", "울주군"],
        "세종특별자치시": ["세종시"],
        "경기도": ["수원시", "성남시", "의정부시", "안양시", "부천시", "광명시", "평택시", "동두천시", "안산시", "고양시", "과천시", "구리시", "남양주시", "오산시", "시흥시", "군포시", "의왕시", "하남시", "용인시", "파주시", "이천시", "안성시", "김포시", "화성시", "광주시", "양주시", "포천시", "여주시", "연천군", "가평군", "양평군"],
        "강원특별자치도": ["춘천시", "원주시", "강릉시", "동해시", "태백시", "속초시", "삼척시", "홍천군", "횡성군", "영월군", "평창군", "정선군", "철원군", "화천군", "양구군", "인제군", "고성군", "양양군"],
        "충청북도": ["청주시", "충주시", "제천시", "보은군", "옥천군", "영동군", "증평군", "진천군", "괴산군", "음성군", "단양군"],
        "충청남도": ["천안시", "공주시", "보령시", "아산시", "서산시", "논산시", "계룡시", "당진시", "금산군", "부여군", "서천군", "청양군", "홍성군", "예산군", "태안군"],
        "전북특별자치도": ["전주시", "군산시", "익산시", "정읍시", "남원시", "김제시", "완주군", "진안군", "무주군", "장수군", "임실군", "순창군", "고창군", "부안군"],
        "전남광주통합특별시": ["동구", "서구", "남구", "북구", "광산구", "목포시", "여수시", "순천시", "나주시", "광양시", "담양군", "곡성군", "구례군", "고흥군", "보성군", "화순군", "장흥군", "강진군", "해남군", "영암군", "무안군", "함평군", "영광군", "장성군", "완도군", "진도군", "신안군"],
        "경상북도": ["포항시", "경주시", "김천시", "안동시", "구미시", "영주시", "영천시", "상주시", "문경시", "경산시", "의성군", "청송군", "영양군", "영덕군", "청도군", "고령군", "성주군", "칠곡군", "예천군", "봉화군", "울진군", "울릉군"],
        "경상남도": ["창원시", "진주시", "통영시", "사천시", "김해시", "밀양시", "거제시", "양산시", "의령군", "함안군", "창녕군", "고성군", "남해군", "하동군", "산청군", "함양군", "거창군", "합천군"],
        "제주특별자치도": ["제주시", "서귀포시"],
    }
    for sido, sigungu_list in _REGIONS_DATA.items():
        for sigungu in sigungu_list:
            conn.execute("INSERT OR IGNORE INTO regions (sido, sigungu) VALUES (?,?)", (sido, sigungu))
    conn.commit()

    _region_lookup = {}
    for row in conn.execute("SELECT id, sido, sigungu FROM regions").fetchall():
        _region_lookup[(row["sido"], row["sigungu"])] = row["id"]

    for rate_type, amount in [
        ("quota_rate_private", 0.031),
        ("levy_per_person_month", 1310000),
        ("incentive_min", 350000),
        ("incentive_max", 900000),
    ]:
        conn.execute(
            "INSERT OR IGNORE INTO levy_rates (year, rate_type, amount) VALUES (2026,?,?)",
            (rate_type, amount),
        )

    _jc_cols = (
        "major_code, major_name_ko, major_name_en, minor_code, minor_name_ko, minor_name_en, "
        "description, daily_tasks, tools_software, min_qualifications, "
        "training_days, difficulty, work_hours_type, min_hours_per_day, shift_required, onsite_required, "
        "kpi_metrics, salary_min, salary_max, salary_basis, "
        "fit_physical_lower, fit_physical_upper, fit_hearing, fit_visual_low, "
        "fit_intellectual, fit_autism, fit_mental, fit_internal_organ, fit_brain_lesion, fit_notes, "
        "market_demand, is_wone_exclusive"
    )
    _jc_placeholders = ",".join(["?"] * 32)
    for _jc_row in [
        ('ADM', '사무/행정', 'Office/Admin', 'ADM-1', '데이터 입력', 'Data Entry',
         '고객 DB, 설문 응답, 명함 등 정형 데이터를 시스템에 입력하고 오류를 검수하는 단순 반복 업무',
         '09:00 당일 입력 대상 데이터 수령 및 분류 → 09:30-12:00 CRM/엑셀에 고객 정보 입력(이름·연락처·주소·구매이력), 설문 응답 코딩(리커트→숫자 변환) → 13:00-15:00 명함 스캔 후 텍스트 추출·입력 → 15:00-16:30 오타·중복 검수(VLOOKUP 대조) → 16:30-18:00 완료분 파일 저장·폴더 정리·일일 처리량 보고',
         '["Microsoft Excel", "Google Sheets", "HWP(한글)", "Ricard/Scancard(명함관리)", "Salesforce/더존 iCUBE(CRM)", "네이버폼/구글폼"]',
         '["컴퓨터활용능력 2급 이상 또는 ITQ OA마스터", "고졸 이상", "타이핑 속도 분당 200타 이상", "무경험 가능"]',
         5, 'low', 'flexible', 4, 0, 0,
         '[{"metric": "일일 입력 건수", "target": "200-400", "unit": "건/일"}, {"metric": "오류율", "target": "0.5% 미만", "unit": "%"}, {"metric": "주간 처리 데이터 총건수", "target": "1000+", "unit": "건/주"}]',
         2090000, 2300000, 'full_8h',
         3, 2, 3, 1, 3, 3, 2, 3, 2,
         '지적장애·자폐 스펙트럼 최우선 추천: 구조화된 단순 반복 업무, 명확한 규칙 기반. 상지장애는 타이핑 가능 수준 확인 필요.',
         'stable', 0),
        ('CSR', '고객서비스', 'Customer Service', 'CSR-1', '채팅 상담', 'Chat Support',
         '카카오채널·네이버톡톡·자사 챗봇을 통한 실시간 채팅 고객 응대 및 FAQ 기반 답변 처리',
         '09:00 채팅 플랫폼 로그인·전날 미처리 건 확인 → 09:30-12:00 실시간 채팅 인입 응대(카카오채널·네이버톡톡), FAQ 스크립트 조회 후 답변, 챗봇 미처리 건 수동 이관 → 13:00-16:00 오후 채팅 응대 계속, 복잡 민원 이메일/전화팀 이관 → 16:00-17:30 상담 내용 CRM 기록 → 17:30-18:00 일일 처리 현황 집계·보고',
         '["카카오 비즈니스", "네이버 스마트스토어 상담", "Zendesk Chat", "채널톡(Channel.io)", "Freshdesk", "CRM(자사 시스템)", "Microsoft Excel"]',
         '["타이핑 속도 분당 250타 이상", "비즈니스 한국어 문장 작성 능력", "CS 경험 우대", "고졸 이상"]',
         14, 'mid', 'flexible', 4, 0, 0,
         '[{"metric": "일일 채팅 처리 건수", "target": "40-80", "unit": "건/일"}, {"metric": "평균 응답 시간", "target": "2분 이내", "unit": "분"}, {"metric": "고객 만족도(CSAT)", "target": "4.0/5.0 이상", "unit": "점"}, {"metric": "1차 해결률", "target": "75% 이상", "unit": "%"}]',
         2090000, 2510000, 'full_8h',
         3, 2, 3, 1, 1, 2, 2, 3, 2,
         '청각장애 최적: 비음성 채팅 100% 텍스트 기반. 자폐 스크립트 기반 응대 가능. 지적장애는 단순 FAQ 한정.',
         'growing', 0),
        ('CRE', '콘텐츠/크리에이티브', 'Content/Creative', 'CRE-2', '영상 편집', 'Video Editing',
         '유튜브·SNS용 영상 컷 편집, AI 자동자막 교정, 썸네일 제작, Shorts/릴스 변환 등 영상 후반 작업',
         '09:00 당일 편집 대상 원본 영상 수령·분량 확인 → 09:30-12:00 원본 컷 편집(불필요 장면 삭제·순서 재배치), Vrew로 AI 자동자막 생성 후 수동 교정 → 13:00-15:00 배경음악·효과음 삽입, 유튜브 썸네일 제작(Canva/Photoshop) → 15:00-16:30 Shorts/릴스용 세로형 포맷 변환, 최종 렌더링 → 16:30-18:00 렌더링 대기 중 다음 영상 프리뷰·기획 확인, 완성 파일 납품(Google Drive 업로드)',
         '["Vrew(AI 한국어 자막)", "CapCut(PC)", "DaVinci Resolve", "Adobe Premiere Pro", "Adobe After Effects", "YouTube Studio", "Canva", "Adobe Photoshop"]',
         '["포트폴리오(편집 샘플 영상) 필수", "전문대졸 이상(영상·미디어 전공 우대)", "Vrew·CapCut 독학 입문자도 단순 편집 가능"]',
         21, 'mid-high', 'full', 8, 0, 0,
         '[{"metric": "주간 영상 편집 완성", "target": "3-7", "unit": "편/주"}, {"metric": "자막 오류율", "target": "1% 미만", "unit": "%"}, {"metric": "수정 요청 횟수", "target": "2회 이내/편", "unit": "회"}]',
         2720000, 4180000, 'full_8h',
         3, 2, 3, 1, 0, 2, 2, 3, 1,
         '청각장애 오히려 강점: 자막 교정 시 텍스트 정확도에 집중. wone 코워크 듀얼모니터·고성능 PC 장비 어드밴티지.',
         'growing', 0),
        ('DEV', 'IT/개발', 'IT/Development', 'DEV-3A', '이미지 데이터 라벨링', 'Image Data Labeling',
         'AI 학습용 이미지에 바운딩박스·폴리곤·세그멘테이션 어노테이션을 수행하고, 동료 교차 검수(QC)를 통해 품질을 관리하는 AI 데이터 구축 업무',
         '09:00 작업 플랫폼 로그인·당일 배치 확인·가이드라인 최신 버전 확인 → 09:30-12:00 이미지 어노테이션 실행(바운딩박스: 객체 사각형 표시, 폴리곤: 비정형 외곽선, 세그멘테이션: 픽셀 단위 분류), 불명확 이미지 보류/검토 요청 태그 → 13:00-15:30 오후 배치 처리 + 동료 교차 검수(QC 라운드: 서로의 작업 10-20% 샘플 검수, IoU≥0.85 기준) → 15:30-17:00 QC 피드백 반영·오류 수정, 작업량 일지 기록 → 17:00-18:00 품질 이슈 리포트·가이드라인 개선 제안',
         '["Crowdworks(크라우드웍스)", "Selectstar(셀렉트스타)", "테스트웍스 자체 툴", "Labelbox", "Label Studio", "CVAT(오픈소스)", "듀얼 모니터", "고DPI 마우스"]',
         '["학력 무관", "마우스 조작 가능", "색각 이상 없음", "집중력·꼼꼼함"]',
         5, 'low-mid', 'full', 8, 0, 0,
         '[{"metric": "바운딩박스 처리량", "target": "200-400", "unit": "객체/시간"}, {"metric": "일일 처리량", "target": "1600-3200", "unit": "객체/일"}, {"metric": "IoU(Intersection over Union)", "target": "0.85 이상", "unit": "비율"}, {"metric": "QC 통과율", "target": "95% 이상", "unit": "%"}]',
         2200000, 2700000, 'full_8h',
         3, 2, 3, 0, 2, 3, 2, 3, 2,
         '자폐 스펙트럼 1순위: 패턴 반복·규칙 준수·세밀한 경계 구분에서 비장애인 대비 높은 정확도(Specialisterne·MS 라벨링팀 사례). 시각장애 부적합(이미지 정밀 작업). 지적장애 경증은 바운딩박스 등 단순 유형에 한해 가능. 테스트웍스 모델 벤치마킹 권장.',
         'explosive', 0),
        ('DEV', 'IT/개발', 'IT/Development', 'DEV-2', 'QA/소프트웨어 테스트', 'QA/Software Testing',
         '웹·앱 기능 테스트 실행, 버그 리포트 작성, 회귀 테스트, 탐색적 테스트를 수행하는 품질 보증 업무',
         '09:00 스탠드업·스프린트 테스트 대상 확인, TestRail 테스트 케이스 시트 열기 → 09:30-12:00 기능 테스트 실행(로그인·결제·폼 제출 시나리오별), 버그 발견 시 Jira 리포트 작성(재현 절차·스크린샷·환경 정보), 회귀 테스트(이전 수정 확인) → 13:00-15:30 모바일 테스트(Android·iOS 실기기), 탐색적 테스트(시나리오 외 자유 탐색) → 15:30-17:30 버그 리포트 업데이트, 개발팀 우선순위 협의, 테스트 케이스 신규 작성 → 17:30-18:00 일일 테스트 현황 요약',
         '["TestRail/Zephyr Scale", "Jira(버그 트래킹)", "Chrome DevTools", "Postman(API 테스트)", "Android Studio/Xcode(모바일 로그)", "Snagit/Greenshot(스크린샷)", "Slack"]',
         '["ISTQB Foundation Level(CTFL) 우대, 한국어 시험 응시 가능", "정보처리기사 또는 산업기사", "SW테스트전문가(CSTS) 국내 자격", "IT 기본 소양 필수"]',
         28, 'mid', 'full', 8, 0, 0,
         '[{"metric": "일일 테스트 케이스 실행", "target": "50-100", "unit": "건/일"}, {"metric": "스프린트당 버그 발견", "target": "10-20", "unit": "건/스프린트"}, {"metric": "버그 재현 성공률", "target": "90% 이상", "unit": "%"}, {"metric": "회귀 테스트 커버리지", "target": "100%", "unit": "%"}]',
         2170000, 2670000, 'full_8h',
         3, 2, 3, 2, 0, 3, 2, 3, 1,
         '자폐 스펙트럼 강력 추천: 패턴 인식·규칙 기반 테스트·반복 실행에서 비장애인 대비 오류 발견율 높음(Microsoft Autism Hiring Program, SAP Autism at Work 사례). 시각 저시력자는 스크린리더 비호환 버그 발견에 오히려 전문성 보유.',
         'growing', 0),
        ('MKT', '마케팅', 'Marketing', 'MKT-4', '시장 조사', 'Market Research',
         '경쟁사 가격·프로모션 변동 추적, 온라인 리뷰 수집, 벤치마킹 보고서 작성 등 정기 시장 모니터링 업무',
         '09:00 지정 경쟁사 3-10개 사이트·SNS 가격·프로모션 변동 확인 → 10:00 네이버 쇼핑·쿠팡 가격 비교 데이터 수집 → 11:00 시장 조사 템플릿(Excel) 입력 → 13:00 경쟁사 리뷰·별점 수집·분석 → 14:00 벤치마킹 보고서 초안(표·스크린샷 포함) → 15:00 담당 마케터 검토 회의 자료 준비 → 16:00 다음 주 모니터링 대상 업데이트',
         '["Excel/Google Sheets", "네이버 쇼핑", "쿠팡", "아이템스카우트", "Notion(리포트 저장)", "Lightshot(화면 캡처)"]',
         '["학력·자격증 제한 없음", "정보 수집·정리 능력", "컴퓨터활용능력 2급 우대"]',
         14, 'mid', 'flexible', 4, 0, 0,
         '[{"metric": "주간 경쟁사 동향 보고서", "target": "1", "unit": "건/주"}, {"metric": "가격 데이터 정확도", "target": "98% 이상", "unit": "%"}, {"metric": "모니터링 대상 누락", "target": "0", "unit": "건"}]',
         2100000, 2400000, 'full_8h',
         3, 2, 3, 1, 3, 2, 2, 3, 2,
         '지적장애 경증 적합: 체크리스트형 반복 수집 업무. 자격증 불필요, 진입장벽 가장 낮은 마케팅 직무.',
         'stable', 0),
        ('ACC', '회계', 'Accounting', 'ACC-1', '전표 입력', 'Voucher Entry',
         '매입·매출 세금계산서 분류, 더존 Smart A를 이용한 전표 입력, 홈택스 전자세금계산서 대조 검증 업무',
         '09:00 전날 수취 세금계산서(전자·종이) 분류 → 10:00 더존 Smart A 실행, 매입 전표 입력(공급가·부가세·거래처명) → 11:00 홈택스 전자세금계산서 조회·대조 → 13:00 매출 전표 입력·거래처 원장 확인 → 14:00 입력 오류 검토(차변·대변 불일치 확인) → 15:00 담당 세무사/회계사에게 이슈 보고 → 16:00 익일 처리 예정 서류 사전 분류',
         '["더존 Smart A(iCUBE)", "세무사랑 Pro", "홈택스(hometax.go.kr)", "Microsoft Excel", "전자세금계산서 수신 이메일"]',
         '["전산회계 2급 이상(한국세무사회, 필수 우대)", "전산회계 1급 우대", "컴퓨터활용능력 2급 이상"]',
         28, 'mid', 'full', 8, 0, 0,
         '[{"metric": "일일 전표 입력 건수", "target": "50-100", "unit": "건/일"}, {"metric": "오류율", "target": "1% 미만", "unit": "%"}, {"metric": "홈택스 대조 일치율", "target": "99% 이상", "unit": "%"}]',
         2300000, 3000000, 'full_8h',
         3, 2, 3, 1, 3, 2, 2, 3, 2,
         '지적장애 경증 적합: 반복 구조화된 숫자 입력. 전산회계 2급 자격증 지원 프로그램과 연계 권장.',
         'stable', 0),
        ('SPT', '전문 지원', 'Professional Support', 'SPT-1', '번역', 'Translation',
         'EN-KR/KR-EN 문서 번역, CAT 도구를 활용한 세그먼트 단위 번역, TM(번역 메모리)·용어집 관리',
         '09:00 당일 번역 의뢰 수신·워드카운트 확인 → 09:30 CAT 도구(SDL Trados/memoQ) 프로젝트 생성·TM 로드 → 10:00-12:30 세그먼트 단위 번역 작업 → 13:30-15:00 번역 계속 → 15:00 초벌 완성·자가 교정(QA 체크 도구 실행(누락, 불일치, 용어 오류 점검)) → 16:00 담당자 전달·피드백 반영 → 16:30 TM·용어집 업데이트',
         '["SDL Trados Studio", "memoQ", "DeepL Pro(참고용)", "Microsoft Word", "Adobe Acrobat(PDF 번역 추출)", "Excel(용어집 관리)"]',
         '["TOEIC 850점 이상 또는 TOEFL iBT 95점 이상(EN-KR)", "번역 관련 전공(영문·통번역) 우대", "관광통역안내사·번역 자격 우대", "CAT 도구 사용 경험 필수"]',
         21, 'mid-high', 'full', 8, 0, 0,
         '[{"metric": "일일 번역량", "target": "2000-3000", "unit": "단어/일"}, {"metric": "오역률", "target": "1% 미만", "unit": "%"}, {"metric": "납기 준수율", "target": "100%", "unit": "%"}]',
         2700000, 4000000, 'full_8h',
         3, 2, 3, 2, 0, 1, 2, 3, 1,
         '청각장애 적합: 문서 번역이므로 음성 통역 불필요. 언어 판단 능력 필수이므로 지적장애 부적합.',
         'stable', 0),
        ('MON', '모니터링/관제', 'Monitoring/Control', 'MON-2', 'CCTV 관제(클라이언트)', 'Client CCTV Monitoring',
         '클라이언트 기업 사업장(창고·공장·매장)의 원격 CCTV 피드를 wone 관제 거점에서 실시간 감시하고, 이상 상황 탐지·통보·기록하는 아웃소싱 관제 업무',
         '업무시작: 담당 클라이언트 3-5개 사업장 VMS 채널 접속·스트림 정상 수신 확인, 통신 두절 채널 즉시 보고 → 상시감시: 사업장별 주요 포인트 순환, 클라이언트별 감시 프로토콜 카드(특이사항·비상연락처·대응절차) 참조 → 이상탐지 시: (1) 영상 정지 캡처 → (2) 클라이언트 담당자 전화/문자/이메일 통보 → (3) 필요 시 경찰·소방 신고 대행 → (4) 인시던트 시스템 상세 기록(시간·카메라ID·유형·조치) → 1시간마다 화질·접속 상태 순환 점검, 장애 티켓 발행 → 일별·주별 클라이언트별 감시 리포트 작성',
         '["Milestone XProtect Corporate", "Genetec Security Center", "IDIS Center Pro", "다후아 DSS Pro", "VPN(기업 전용 터널)", "ServiceNow/Freshdesk(인시던트)", "Greenshot/ShareX(영상 캡처)", "카카오톡 비즈채널/SMS/이메일(통보)"]',
         '["법적 필수 자격 없음", "CCTV관제사 2급(민간) 우대", "경비업 허가 사업장 시 경비원 신임교육(24시간) 이수 필수", "복수 사업장 동시 관리 경험 우대", "고졸 이상"]',
         28, 'low-mid', 'shift', 8, 1, 1,
         '[{"metric": "통보 응답 시간(이상감지→클라이언트 통보)", "target": "5분 이내", "unit": "분"}, {"metric": "채널 접속 가용률", "target": "99% 이상", "unit": "%"}, {"metric": "일별 감시 리포트 발행률", "target": "100%", "unit": "%"}, {"metric": "오탐지율", "target": "15% 이하", "unit": "%"}, {"metric": "클라이언트 만족도", "target": "4.0/5.0 이상", "unit": "점"}]',
         2100000, 3000000, 'shift_night',
         3, 1, 3, 0, 2, 3, 2, 3, 1,
         '자폐 스펙트럼 강점: 규칙 기반 프로토콜 준수·반복 감시 루틴 최적. 청각장애는 문자/이메일 전용 프로토콜 전환 시 적합도 상승. 1인당 최대 16채널(행정안전부 기준 32채널, AI 보조 시 64채널). 경비업법상 타인 시설 원격 관제 서비스 제공 시 경비업 허가 필요.',
         'growing', 1),
        ('FAC', '시설 운영', 'Facility Operations', 'FAC-4', '우편·문서 처리', 'Mail/Document Handling',
         'wone 코워크스페이스 내부 문서 분류·스캔·인쇄·제본·발송 및 물리/디지털 파일링을 담당하는 문서 물류 업무',
         '09:00-10:00 전날 접수 내부 문서 분류(부서별·수신인별), 우편물 개봉·스캔·파일명 규칙에 따라 저장(Google Drive/SharePoint) → 10:00-12:00 문서 인쇄 요청 처리(양면·컬러·제본 등 규격 맞춤), 제본기·코팅기 운용, 완성 문서 수신인 전달 → 13:00-15:00 발송 우편물 봉투 작성·무게 계량·우편 규격 확인, 등기 발송(우체국 앱/직접 방문), 택배 접수 → 15:00-17:00 문서 보관 파일링(물리 보관함·디지털 인덱스 동기화), 파기 예정 문서 목록 작성 → 17:00-18:00 일일 처리 현황 기록',
         '["복합기(Canon·Ricoh·신도리코)", "Adobe Acrobat(PDF 편집·병합)", "Google Drive/SharePoint", "HWP(한글) 기본 편집", "우체국 사전접수 앱", "바코드 스캐너(택배 등록)"]',
         '["학력 무관", "HWP·MS Word 기본 조작", "ITQ 한글·워드 우대", "문서 보안 서약서 필수"]',
         5, 'low', 'flexible', 4, 0, 1,
         '[{"metric": "문서 분류 오류율", "target": "0.5% 이하", "unit": "%"}, {"metric": "인쇄 요청 당일 완료율", "target": "98%", "unit": "%"}, {"metric": "발송 누락 건수", "target": "0", "unit": "건/월"}]',
         2090000, 2090000, 'full_8h',
         3, 2, 3, 1, 3, 3, 3, 3, 2,
         '청각장애 최우선 추천(1순위): 전 과정 음성 커뮤니케이션 불필요, 100% 문서·시스템 기반. 자폐 스펙트럼: 규칙 기반 분류·파일명 패턴 작업 매우 적합. 지적장애 경증: 명확한 체크리스트 제공 시 반복 업무 가능.',
         'stable', 1),
    ]:
        conn.execute(
            f"INSERT OR IGNORE INTO job_categories ({_jc_cols}) VALUES ({_jc_placeholders})",
            _jc_row,
        )

    conn.executescript("""
    CREATE INDEX IF NOT EXISTS idx_major_code ON job_categories(major_code);
    CREATE INDEX IF NOT EXISTS idx_difficulty ON job_categories(difficulty);
    CREATE INDEX IF NOT EXISTS idx_market_demand ON job_categories(market_demand);
    """)

    users = [
        ("op1", "운영자", "051-000-0000", "operator"),
        ("counsel1", "이상담", "051-111-0000", "manager"),
        ("comp1", "한빛테크 인사팀", "051-111-2222", "company"),
        ("comp2", "클로버커머스 인사팀", "02-222-3333", "company"),
        ("comp3", "넥스트미디어 인사팀", "031-444-5555", "company"),
        ("comp4", "세종파트너스 총무팀", "02-666-7777", "company"),
        ("seeker1", "김하늘", "010-1234-5678", "seeker"),
        ("seeker2", "박서준", "010-8765-4321", "seeker"),
    ]
    for username, name, phone, role in users:
        conn.execute(
            "INSERT OR IGNORE INTO users (username, password, name, phone, email, role) VALUES (?,?,?,?,?,?)",
            (username, hash_password("admin1234"), name, phone, f"{username}@example.com", role),
        )
    conn.commit()

    uid = {
        r["username"]: r["id"]
        for r in conn.execute("SELECT id, username FROM users").fetchall()
    }

    _r_busan = _region_lookup.get(("부산광역시", "해운대구"))
    _r_seoul_gangnam = _region_lookup.get(("서울특별시", "강남구"))
    _r_pangyo = _region_lookup.get(("경기도", "성남시"))
    _r_seoul_jongno = _region_lookup.get(("서울특별시", "종로구"))

    companies = [
        (uid["comp1"], "한빛테크", "123-45-67890", "IT/소프트웨어", 250, 3,
         _r_busan,
         "장애인 재택근무 환경을 갖춘 IT 서비스 기업입니다.",
         "https://hanbit-tech.example.com",
         "중소기업(50~299인)",
         json.dumps(["휠체어접근", "엘리베이터", "장애인화장실", "보조기기지원", "휴게공간"], ensure_ascii=False),
         "1층 전체 무장애 동선, 높이조절 책상 20대 보유",
         1, "장애인 개발자 3명 재직 중, 평균 근속 2.5년",
         "4대보험, 유연근무제, 재택근무(주2회), 자기개발비 연 100만원, 장비 지원",
         "김영호", 2015, "법인", "부산광역시 해운대구 센텀중앙로 97 센텀스카이비즈 12층"),
        (uid["comp2"], "클로버커머스", "234-56-78901", "유통/전자상거래", 180, 2,
         _r_seoul_gangnam,
         "반려동물 용품 전문 이커머스 기업입니다. 네이버 스마트스토어, 쿠팡, 자사몰을 운영하고 있습니다.",
         "https://clover-commerce.example.com",
         "중소기업(50~299인)",
         json.dumps(["휠체어접근", "엘리베이터", "장애인화장실"], ensure_ascii=False),
         "건물 1층 경사로, 각 층 장애인 화장실 설치",
         1, "장애인 디자이너 2명 재직, 평균 근속 1.8년",
         "4대보험, 자율출퇴근, 반려동물 동반 출근, 간식 무한, 생일 반차",
         "이수진", 2019, "법인", "서울특별시 강남구 테헤란로 152 강남파이낸스센터 8층"),
        (uid["comp3"], "넥스트미디어", "345-67-89012", "미디어/콘텐츠", 45, 1,
         _r_pangyo,
         "유튜브 채널 운영 대행 및 기업 영상 제작 전문 스튜디오입니다.",
         "https://next-media.example.com",
         "소기업(10~49인)",
         json.dumps(["엘리베이터", "보조기기지원"], ensure_ascii=False),
         "편집실 높이조절 책상, 4K 모니터 2대 기본 지급",
         0, "",
         "4대보험, Adobe CC 전직원 지급, 도서구입비 월 5만원, 유연근무",
         "박준혁", 2021, "법인", "경기도 성남시 분당구 판교역로 235 에이치스퀘어 N동 5층"),
        (uid["comp4"], "세종파트너스", "456-78-90123", "회계/컨설팅", 320, 5,
         _r_seoul_jongno,
         "중견기업 대상 회계감사, 세무자문, 경영컨설팅을 수행하는 종합 회계법인입니다.",
         "https://sejong-partners.example.com",
         "중기업(300~999인)",
         json.dumps(["휠체어접근", "엘리베이터", "장애인화장실", "휴게공간"], ensure_ascii=False),
         "전 층 무장애 동선, 휴게실 2개소 운영",
         1, "장애인 직원 5명 재직, 회계 보조 3명 평균 근속 3.2년",
         "4대보험, 더존 교육 지원, 자격증 응시비, 야간수당, 중식 제공",
         "최동훈", 2008, "법인", "서울특별시 종로구 종로 33 그랑서울 15층"),
    ]
    conn.executemany(
        """INSERT OR IGNORE INTO companies
           (user_id, company_name, biz_no, industry, employee_count, disabled_count,
            region_id, intro, website, company_size,
            accessibility_facilities, accessibility_note,
            hiring_experience, retention_note, benefits,
            ceo, est_year, biz_type, address)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        companies,
    )
    conn.execute("UPDATE companies SET approval_status='approved'")
    conn.execute(
        """UPDATE companies SET remote_ok=1, flexible_ok=1, esg_items=?, esg_note=?, work_env_note=?
           WHERE user_id=?""",
        (json.dumps(["장애인 표준사업장", "장애인 인식개선 교육"], ensure_ascii=False),
         "매년 전 직원 대상 장애인 인식개선 교육을 진행하며, 장애인 표준사업장 인증을 유지하고 있습니다.",
         "주 2회 재택근무, 코어타임 11시~16시 유연근무제 운영 중입니다.",
         uid["comp1"]),
    )
    conn.commit()

    dt = {
        r["name"]: r["id"]
        for r in conn.execute("SELECT id, name FROM disability_types").fetchall()
    }
    seeker_profiles = [
        (uid["seeker1"], dt["시각"], "중증", "여", 2000, "2000-01-15",
         _r_busan,
         "고졸", "", "", 1, "", "", "꼼꼼한 문서 작업이 강점입니다. 스크린리더 사용에 능숙합니다.",
         "사무보조", "재택",
         "대중교통", 60,
         json.dumps(["문자"], ensure_ascii=False),
         json.dumps(["화면낭독기"], ensure_ascii=False),
         6, "오전", "2시간마다",
         json.dumps(["점자자료", "재택근무", "보조기기지원"], ensure_ascii=False)),
        (uid["seeker2"], dt["지체"], "경증", "남", 1998, "1998-07-22",
         _r_seoul_gangnam,
         "대졸", "한국대학교", "컴퓨터공학", 3, "테크컴퍼니", "프론트엔드 개발자",
         "웹 접근성 마크업 경험 3년차 개발자입니다.",
         "웹개발", "무관",
         "자차", 45,
         json.dumps(["음성"], ensure_ascii=False),
         json.dumps([], ensure_ascii=False),
         8, "풀타임", "불필요",
         json.dumps(["휠체어접근", "엘리베이터", "주차지원"], ensure_ascii=False)),
    ]
    for p in seeker_profiles:
        conn.execute(
            """INSERT OR IGNORE INTO seeker_profiles
               (user_id, disability_type_id, severity, gender, birth_year, birth_date, region_id,
                education_level, school_name, major, career_years,
                recent_company, recent_job_title, experience_summary,
                desired_job, work_pref,
                mobility_type, commute_max_minutes,
                communication_pref, assistive_tech,
                daily_work_hours, preferred_time, rest_frequency,
                accommodation_needs,
                consent_sensitive, consented_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,datetime('now','localtime'))""",
            p,
        )

    seeker_certs = [
        (uid["seeker1"], "컴퓨터활용능력 2급", "2020-06", "대한상공회의소"),
        (uid["seeker1"], "ITQ OA마스터", "2021-03", "한국생산성본부"),
        (uid["seeker2"], "정보처리기사", "2019-11", "한국산업인력공단"),
        (uid["seeker2"], "SQLD", "2020-09", "한국데이터산업진흥원"),
        (uid["seeker2"], "웹접근성 전문가", "2022-05", "한국웹접근성인증평가원"),
    ]
    for cert in seeker_certs:
        conn.execute(
            "INSERT INTO seeker_certifications (user_id, cert_name, cert_date, issuing_org) VALUES (?,?,?,?)",
            cert,
        )

    _intro_presets = [
        ("성장과정", "본인의 성장 배경과 가치관을 소개해 주세요"),
        ("지원동기", "이 분야/직무에 관심을 갖게 된 계기를 알려주세요"),
        ("직무역량 및 경험", "관련 경험, 프로젝트, 보유 역량을 구체적으로 작성해 주세요"),
        ("성격의 장단점", "자신의 성격에서 업무에 도움이 되는 점을 중심으로 작성해 주세요"),
        ("입사 후 포부", "입사 후 이루고 싶은 목표를 구체적으로 작성해 주세요"),
        ("프로젝트 경험", "참여한 프로젝트의 역할과 성과를 알려주세요"),
        ("근무 시 참고사항", "업무 수행 시 필요한 배려나 환경을 자유롭게 작성해 주세요"),
    ]
    for idx, (title, desc) in enumerate(_intro_presets):
        conn.execute(
            "INSERT OR IGNORE INTO self_intro_presets (title, description, sort_order) VALUES (?,?,?)",
            (title, desc, idx),
        )

    cid = {
        r["company_name"]: r["id"]
        for r in conn.execute("SELECT id, company_name FROM companies").fetchall()
    }

    _default_stages = [
        ("reviewing", "검토중"), ("shortlisted", "서류합격"),
        ("interview", "면접"), ("offer", "제의"),
    ]
    for company_name, company_id in cid.items():
        for sort_order, (stage_key, label) in enumerate(_default_stages, 1):
            conn.execute(
                "INSERT OR IGNORE INTO company_pipeline_stages (company_id, stage_key, label, sort_order) VALUES (?,?,?,?)",
                (company_id, stage_key, label, sort_order),
            )

    cat = {
        r["minor_code"]: r["id"]
        for r in conn.execute("SELECT id, minor_code FROM job_categories").fetchall()
    }

    _job_sql = """INSERT INTO job_postings
       (company_id, title, region_id, employment_type, remote_available,
        work_start_time, work_end_time, work_days, flexible_hours,
        accommodations_provided, accommodations_note,
        preferred_disability, preferred_severity, min_work_hours,
        benefits, qualifications,
        tasks, tools, experience_level, education,
        hiring_process, headcount,
        salary, deadline, description, status, category_id)
       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""

    # 한빛테크
    _c1 = cid["한빛테크"]
    for j in [
        (_c1, "사무지원 담당자", _r_busan, "정규직", 1,
         "09:00", "18:00", "월~금", 1,
         json.dumps(["재택근무", "보조기기지원", "유연근무"], ensure_ascii=False),
         "스크린리더 지원 문서 양식 제공",
         json.dumps([], ensure_ascii=False), "무관", 8,
         "4대보험, 유연근무제, 스크린리더 지원",
         "컴퓨터활용능력 2급 이상 우대",
         "고객 정보(이름·연락처·주소·구매이력) CRM/엑셀 입력\n설문지 응답 코딩 (리커트 척도 -> 숫자 변환)\n명함 스캔 후 텍스트 추출·입력\n오타·중복 데이터 검수",
         "Microsoft Excel, Google Sheets, HWP, Salesforce/더존 iCUBE",
         "무관", "고졸 이상",
         "서류전형,면접,최종합격", "1명",
         "월 210만원", dl(29),
         "고객 DB·설문 응답·명함 등 정형 데이터를 CRM/엑셀에 입력하고 오류를 검수하는 업무입니다.",
         "open", cat.get("ADM-1")),
        (_c1, "AI 이미지 데이터 라벨러 (자율주행)", _r_pangyo, "정규직", 0,
         "09:00", "18:00", "월~금", 0,
         json.dumps(["보조기기지원", "휴게공간"], ensure_ascii=False),
         "듀얼 모니터, 고DPI 마우스, 50분 작업·10분 휴식 보장",
         json.dumps(["자폐성", "지적"], ensure_ascii=False), "무관", 8,
         "4대보험, 휴게공간, 간식",
         "색각 이상 없음, 마우스 조작 가능",
         "바운딩박스: 객체(차량·보행자·신호등) 사각형 표시\n폴리곤: 비정형 객체 외곽선 표시\n동료 교차 검수 (QC 라운드, 10~20% 샘플)\n가이드라인 개선 제안",
         "CVAT, Label Studio, Crowdworks",
         "무관", "학력무관",
         "서류전형,실무면접,최종합격", "2명",
         "월 220~270만원", dl(121),
         "자율주행 AI 학습용 이미지에 어노테이션을 수행하는 업무입니다.",
         "open", cat.get("DEV-3A")),
        (_c1, "AI 의료 이미지 라벨러 (X-ray·MRI)", _r_pangyo, "계약직", 0,
         "09:00", "18:00", "월~금", 0,
         json.dumps(["보조기기지원"], ensure_ascii=False),
         "DICOM 뷰어 전용 모니터, 의료 도메인 교육 2주 제공",
         json.dumps(["자폐성"], ensure_ascii=False), "무관", 8,
         "4대보험, 전문 교육 제공",
         "",
         "세그멘테이션 어노테이션 (픽셀 단위 병변 분류)\n의료 도메인 교육 2주 이수 후 작업 시작\nQC 매니저 샘플 검수 대응",
         "Label Studio, CVAT, DICOM 뷰어",
         "무관", "학력무관",
         "서류전형,면접,최종합격", "1명",
         "월 250~300만원", dl(121),
         "의료 AI 학습용 X-ray·MRI 이미지에 병변 부위를 표시하는 업무입니다.",
         "open", cat.get("DEV-3A")),
        (_c1, "소프트웨어 QA 테스터", _r_pangyo, "정규직", 0,
         "09:00", "18:00", "월~금", 0,
         json.dumps(["보조기기지원", "휴게공간"], ensure_ascii=False),
         "테스트 기기(Android·iOS) 제공, ISTQB 응시비 지원, 회의 자막 지원",
         json.dumps(["자폐성", "청각"], ensure_ascii=False), "무관", 8,
         "4대보험, 자격증 응시비 지원, 장비 지원",
         "ISTQB CTFL 우대, IT 기본 소양",
         "기능 테스트 실행 (로그인·결제·폼 제출 시나리오)\nJira 버그 리포트 작성 (재현 절차·스크린샷·환경 정보)\n회귀 테스트 (이전 수정 확인)\n모바일 테스트 (Android·iOS 실기기)\n탐색적 테스트 (시나리오 외 자유 탐색)",
         "TestRail, Jira, Chrome DevTools, Postman",
         "무관", "학력무관",
         "서류전형,실무면접,최종합격", "2명",
         "월 217~267만원", dl(90),
         "웹·앱 서비스의 기능을 테스트하고 버그를 발견·보고하는 업무입니다.",
         "open", cat.get("DEV-2")),
        (_c1, "데이터 라벨링 담당자 (텍스트 NLP)", _r_busan, "계약직", 0,
         "09:00", "18:00", "월~금", 1,
         json.dumps(["휠체어접근", "주차지원", "유연근무"], ensure_ascii=False),
         "사무실 휠체어 접근, 장애인 전용 주차, 시차출퇴근",
         json.dumps(["지체", "뇌병변"], ensure_ascii=False), "무관", 8,
         "4대보험, 시차출퇴근",
         "",
         "문장 감성 분류 (긍정/부정/중립)\n개체명 인식 (NER: 사람·장소·기관 태깅)\n챗봇 대화 데이터 품질 검수",
         "Crowdworks, Selectstar, Label Studio",
         "무관", "학력무관",
         "서류전형,면접,최종합격", "2명",
         "월 200~250만원", dl(14),
         "AI 학습용 텍스트 데이터를 분류·태깅하는 업무입니다.",
         "open", cat.get("DEV-3A")),
        (_c1, "데이터 정제 담당 (Excel·Python)", _r_pangyo, "정규직", 1,
         "09:00", "18:00", "월~금", 0,
         json.dumps(["보조기기지원"], ensure_ascii=False),
         "개발 워크스테이션, Python 교육 프로그램 제공",
         json.dumps([], ensure_ascii=False), "무관", 8,
         "4대보험, 교육비 지원",
         "Excel 중급 이상, Python 기초 우대",
         "결측값 처리 (삭제·대체·플래그)\n중복 행 제거 (VLOOKUP / pandas drop_duplicates)\n이상값 탐지·처리\n데이터 형식 표준화 (날짜·전화번호·주소 포맷 통일)",
         "Excel, Python + pandas, OpenRefine, Jupyter Notebook",
         "무관", "학력무관",
         "서류전형,실무면접,최종합격", "1명",
         "월 200~333만원", dl(75),
         "원본 데이터셋의 오류를 찾아 정제하는 업무입니다.",
         "open", cat.get("DEV-3A")),
    ]:
        conn.execute(_job_sql, j)

    # 클로버커머스
    _c2 = cid["클로버커머스"]
    for j in [
        (_c2, "채팅 CS 상담원 (카카오채널)", _r_seoul_gangnam, "정규직", 1,
         "09:00", "18:00", "월~금", 1,
         json.dumps(["보조기기지원", "유연근무"], ensure_ascii=False),
         "채팅 전용(음성통화 없음), 소음 차단 헤드셋, 모니터 확대기",
         json.dumps(["청각"], ensure_ascii=False), "무관", 8,
         "4대보험, 성과급, 장비 지원",
         "타이핑 분당 250타 이상",
         "FAQ 스크립트 조회 후 채팅 답변\n챗봇 미처리 건 수동 이관\n상담 내용 CRM 기록\n복잡 민원 이메일/전화팀 이관",
         "카카오 비즈니스, 네이버 스마트스토어, 채널톡(Channel.io), Zendesk Chat",
         "무관", "고졸 이상",
         "서류전형,면접,최종합격", "2명",
         "월 209~251만원", dl(49),
         "카카오채널·네이버톡톡으로 인입되는 고객 문의를 실시간 채팅으로 응대하는 업무입니다.",
         "open", cat.get("CSR-1")),
        (_c2, "온라인 리뷰 모니터링 (4h 파트타임)", _r_seoul_gangnam, "계약직", 1,
         "09:00", "13:00", "월~금", 1,
         json.dumps(["보조기기지원", "유연근무"], ensure_ascii=False),
         "듀얼 모니터, 화면 확대 소프트웨어",
         json.dumps([], ensure_ascii=False), "무관", 4,
         "4대보험(비례)",
         "",
         "네이버 쇼핑·쿠팡·구글플레이 리뷰 수집\n긍정/부정/중립 분류 후 스프레드시트 기록\n악성 리뷰 캡처·즉시 보고",
         "Excel/Google Sheets, 네이버 쇼핑, 쿠팡, Lightshot",
         "무관", "학력무관",
         "서류전형,면접,최종합격", "1명",
         "월 103~115만원 (4h)", dl(60),
         "각종 온라인 플랫폼의 리뷰를 수집·분류하는 업무입니다.",
         "open", cat.get("CSR-1")),
        (_c2, "상품 사진 리터칭 (누끼·색보정)", _r_seoul_gangnam, "정규직", 0,
         "09:00", "18:00", "월~금", 0,
         json.dumps(["보조기기지원"], ensure_ascii=False),
         "고해상도 모니터, Wacom 타블렛, Photoshop 라이선스",
         json.dumps(["지체", "뇌병변"], ensure_ascii=False), "경증", 8,
         "4대보험, Adobe CC 라이선스",
         "Photoshop 기본 이상",
         "상품 사진 배경 제거 (누끼 작업)\n색보정 (밝기·채도·화이트밸런스)\n규격 리사이징 (1000x1000px 등)\n워터마크 삽입, 배치 처리",
         "Adobe Photoshop (배치 액션), remove.bg, Lightroom Classic",
         "무관", "학력무관",
         "서류전형,포트폴리오심사,면접,최종합격", "1명",
         "월 230~334만원", dl(90),
         "쇼핑몰 상품 사진을 편집·보정하는 업무입니다.",
         "open", cat.get("CRE-2")),
        (_c2, "SNS 채널 관리자", _r_seoul_gangnam, "정규직", 1,
         "09:00", "18:00", "월~금", 1,
         json.dumps(["보조기기지원", "유연근무"], ensure_ascii=False),
         "Canva Pro 라이선스, Notion 콘텐츠 캘린더",
         json.dumps([], ensure_ascii=False), "무관", 8,
         "4대보험, 도구 라이선스, 성과급",
         "SNS 운영 경험 우대",
         "인스타그램 피드/릴스 예약 업로드 (Meta Business Suite)\n네이버 블로그 포스팅 편집·발행\n유튜브 영상 썸네일·태그·설명 작성\n댓글·DM 분류 및 답변\n인게이지먼트 지표(좋아요·저장·도달) 기록",
         "Meta Business Suite, Canva, Notion, YouTube Studio",
         "경력 1년 이상", "학력무관",
         "서류전형,실무면접,임원면접,최종합격", "1명",
         "월 220~300만원", dl(60),
         "자사 SNS 채널의 콘텐츠 업로드·댓글 관리를 담당합니다.",
         "open", cat.get("MKT-4")),
        (_c2, "경쟁사 시장조사 담당 (4h 가능)", _r_seoul_gangnam, "계약직", 1,
         "09:00", "13:00", "월~금", 1,
         json.dumps(["보조기기지원", "유연근무"], ensure_ascii=False),
         "듀얼 모니터, 체크리스트 매뉴얼 제공",
         json.dumps(["지적"], ensure_ascii=False), "경증", 4,
         "4대보험",
         "컴퓨터활용능력 2급 우대",
         "경쟁사 3~10개 사이트·SNS 가격 변동 확인\n네이버 쇼핑·쿠팡 가격 비교 데이터 수집\n경쟁사 리뷰·별점 분석\n주간 벤치마킹 보고서 초안 작성",
         "Excel/Google Sheets, 네이버 쇼핑, 쿠팡, 아이템스카우트, Notion",
         "무관", "학력무관",
         "서류전형,면접,최종합격", "1명",
         "월 210~240만원", dl(44),
         "경쟁사의 가격·프로모션 변동을 정기 추적하는 업무입니다.",
         "open", cat.get("MKT-4")),
    ]:
        conn.execute(_job_sql, j)

    # 넥스트미디어
    _c3 = cid["넥스트미디어"]
    for j in [
        (_c3, "유튜브 영상 편집자 (Vrew·프리미어)", _r_pangyo, "정규직", 0,
         "09:00", "18:00", "월~금", 0,
         json.dumps(["보조기기지원"], ensure_ascii=False),
         "고성능 편집 PC(RTX 4070+32GB), 듀얼 4K 모니터",
         json.dumps(["청각"], ensure_ascii=False), "무관", 8,
         "4대보험, 장비 지원, 자기개발비",
         "포트폴리오 필수, Vrew/CapCut 경험",
         "원본 영상 컷 편집 (불필요 장면 삭제·순서 재배치)\nVrew AI 자동자막 생성 후 수동 교정\n유튜브 썸네일 제작 (Canva/Photoshop)\nShorts/릴스용 세로형 포맷 변환\n배경음악·효과음 삽입 및 최종 렌더링",
         "Vrew, CapCut, Adobe Premiere Pro, After Effects, YouTube Studio",
         "무관", "전문대졸 이상",
         "서류전형,포트폴리오심사,실무면접,최종합격", "1명",
         "월 272~350만원", dl(75),
         "유튜브·SNS용 영상 후반 작업을 담당합니다.",
         "open", cat.get("CRE-2")),
        (_c3, "한국어 교정·교열 담당", _r_pangyo, "계약직", 1,
         "09:00", "18:00", "월~금", 1,
         json.dumps(["보조기기지원", "유연근무", "재택근무"], ensure_ascii=False),
         "대형 모니터, 맞춤법 검사 도구 라이선스",
         json.dumps(["청각", "지체"], ensure_ascii=False), "무관", 8,
         "4대보험, 도서 구입비",
         "국어국문 관련 전공 우대",
         "맞춤법·띄어쓰기·외래어 표기 검토\n문체 일관성 확인 (높임말 통일 등)\nHWP/Word 변경 추적으로 수정 표시\n교정 의견 코멘트 작성",
         "HWP, Microsoft Word, 부산대 맞춤법 검사기, Notion",
         "무관", "학력무관",
         "서류전형,면접,최종합격", "1명",
         "월 230~314만원", dl(49),
         "출판물·웹페이지·홍보물의 맞춤법·문체를 검토하는 업무입니다.",
         "open", cat.get("CRE-2")),
        (_c3, "EN-KR 기술문서 번역가 (SDL Trados)", _r_pangyo, "정규직", 1,
         "09:00", "18:00", "월~금", 1,
         json.dumps(["보조기기지원", "유연근무", "휴게공간"], ensure_ascii=False),
         "SDL Trados 라이선스, 용어집 DB, 집중 작업실",
         json.dumps(["청각", "지체"], ensure_ascii=False), "무관", 8,
         "4대보험, 도구 라이선스, 도서구입비",
         "TOEIC 850점 이상, CAT 도구 경험 필수",
         "SDL Trados/memoQ CAT 도구를 활용한 세그먼트 단위 번역\nTM(번역 메모리)·용어집 관리 및 업데이트\n초벌 번역 완성 후 자가 교정 (QA 체크 도구 실행)",
         "SDL Trados Studio, memoQ, DeepL Pro, Microsoft Word, Adobe Acrobat",
         "경력 1년 이상", "전문대졸 이상",
         "서류전형,실무면접,임원면접,최종합격", "1명",
         "월 270~400만원", dl(90),
         "IT 기술문서·매뉴얼을 영어에서 한국어로 번역하는 업무입니다.",
         "open", cat.get("SPT-1")),
        (_c3, "문서 스캔·파일링 담당자 (4h)", _r_pangyo, "계약직", 0,
         "09:00", "13:00", "월~금", 0,
         json.dumps(["휠체어접근", "보조기기지원"], ensure_ascii=False),
         "높이조절 책상, 스캐너 전용 데스크",
         json.dumps(["지체"], ensure_ascii=False), "경증", 4,
         "4대보험(비례), 중식 제공",
         "",
         "Canon/Fujitsu 업무용 스캐너로 서류 투입·품질 확인\nAdobe Acrobat OCR 처리\n파일명 규칙에 따라 rename 및 폴더 분류\n손상 페이지 재스캔",
         "Canon/Fujitsu 스캐너, Adobe Acrobat, Google Drive",
         "무관", "학력무관",
         "서류전형,면접,최종합격", "1명",
         "월 103~110만원 (4h)", dl(44),
         "종이 서류를 스캐너로 디지털화하고 PDF로 분류·보관하는 업무입니다.",
         "open", cat.get("ADM-1")),
    ]:
        conn.execute(_job_sql, j)

    # 세종파트너스
    _c4 = cid["세종파트너스"]
    for j in [
        (_c4, "경비 영수증 정리 담당", _r_seoul_jongno, "정규직", 0,
         "09:00", "18:00", "월~금", 0,
         json.dumps(["보조기기지원"], ensure_ascii=False),
         "더존 ERP 교육 제공, 대형 모니터 지원",
         json.dumps(["지적"], ensure_ascii=False), "경증", 8,
         "4대보험, 더존 ERP 교육 지원",
         "전산회계 2급 우대",
         "법인카드 내역 은행 앱에서 다운로드\n임직원 영수증 스캔·수거\n카드 내역 vs 영수증 1:1 대조 (VLOOKUP)\n정산 완료 건 더존 Smart A 전표 입력",
         "더존 Smart A, Microsoft Excel, Adobe Acrobat",
         "무관", "고졸 이상",
         "서류전형,면접,최종합격", "1명",
         "월 209~251만원", dl(60),
         "법인카드 사용 내역과 영수증을 대조·정산하는 업무입니다.",
         "open", cat.get("ADM-1")),
        (_c4, "매입·매출 전표 입력 담당 (더존)", _r_seoul_jongno, "정규직", 0,
         "09:00", "18:00", "월~금", 0,
         json.dumps(["보조기기지원"], ensure_ascii=False),
         "더존 Smart A 교육 4주, 대형 모니터",
         json.dumps(["지적", "지체"], ensure_ascii=False), "경증", 8,
         "4대보험, 교육비 지원",
         "전산회계 2급 이상 우대",
         "세금계산서(전자·종이) 분류\n더존 Smart A 매입·매출 전표 입력 (공급가·부가세·거래처)\n홈택스 전자세금계산서 대조\n입력 오류 검토 (차변·대변 불일치 확인)",
         "더존 Smart A(iCUBE), 홈택스, Microsoft Excel",
         "무관", "고졸 이상",
         "서류전형,면접,최종합격", "1명",
         "월 230~300만원", dl(75),
         "세금계산서를 분류하고 회계 프로그램에 전표를 입력하는 업무입니다.",
         "open", cat.get("ACC-1")),
        (_c4, "CCTV 원격 관제사 (클라이언트 빌딩)", _r_seoul_jongno, "정규직", 0,
         "00:00", "08:00", "3교대", 0,
         json.dumps(["휴게공간"], ensure_ascii=False),
         "wone 관제 거점 근무, 16채널 모니터월, 조이스틱, 야간수당",
         json.dumps(["자폐성"], ensure_ascii=False), "무관", 8,
         "4대보험, 야간수당 +30%, 교대수당",
         "CCTV관제사 2급 우대",
         "담당 클라이언트 3~5개 사업장 VMS 채널 실시간 감시\n이상 탐지 시: 영상 캡처 -> 클라이언트 통보 -> 인시던트 기록\n필요 시 경찰·소방 신고 대행\n1시간마다 화질·접속 상태 점검\n일별·주별 감시 리포트 작성",
         "Milestone XProtect, IDIS Center, Genetec, VPN",
         "무관", "고졸 이상",
         "서류전형,면접,최종합격", "2명",
         "월 210~300만원 (야간 +30%)", dl(121),
         "클라이언트 기업 사업장의 CCTV를 wone 관제 거점에서 원격 감시하는 업무입니다.",
         "open", cat.get("MON-2")),
        (_c4, "서버·네트워크 모니터링 (NOC 1차 대응)", _r_seoul_jongno, "정규직", 0,
         "00:00", "08:00", "3교대", 0,
         json.dumps(["보조기기지원", "휴게공간"], ensure_ascii=False),
         "wone 관제 거점 근무, Zabbix/Grafana 대시보드 전용 모니터, Slack 알람봇",
         json.dumps(["자폐성", "지체"], ensure_ascii=False), "무관", 8,
         "4대보험, 야간수당, 자격증 지원",
         "",
         "Zabbix/Grafana 대시보드 30분 1회 순환 확인 (녹색->황색->적색)\nCritical 알람: 3분 이내 엔지니어 Slack + 전화 통보\nWarning 알람: Jira SM 티켓 생성 후 이메일 통보\n인시던트 기록 (발생시각·장비명·알람 내용·조치자)\n교대 종료 시 당직 보고서 작성",
         "Zabbix, Grafana, Jira Service Management, Slack",
         "무관", "학력무관",
         "서류전형,실무면접,최종합격", "1명",
         "월 210~320만원", dl(121),
         "서버·네트워크 장비의 상태 경보를 감시하고 담당 엔지니어에게 에스컬레이션하는 업무입니다.",
         "open", cat.get("MON-2")),
        (_c4, "방재 관제사 (화재·가스·출입)", _r_seoul_jongno, "정규직", 0,
         "00:00", "08:00", "3교대", 0,
         json.dumps(["보조기기지원", "휴게공간"], ensure_ascii=False),
         "wone 관제 거점, 화재수신기 전용석, 시각 LED·진동 보조기기(청각장애 시)",
         json.dumps([], ensure_ascii=False), "무관", 8,
         "4대보험, 자격수당 +10~30만, 야간수당",
         "소방안전관리자 2급 취득 지원",
         "화재수신기(P/R형)·가스감지기·출입통제(슈프리마 BioStar2) 패널 감시\n화재 경보 시: 해당 구역 CCTV 교차 확인 -> 실화 판단 -> 119 신고 + 대피 방송\n가스 경보 시: 환기 지시 -> 가스 차단 밸브 원격 제어\n2시간마다 수신기 패널 수동 점검·기록\n월 1회 소방훈련 참여",
         "화재수신기 제어 패널, 슈프리마 BioStar2, CCTV VMS",
         "무관", "학력무관",
         "서류전형,면접,최종합격", "1명",
         "월 220~330만원 (자격수당 +10~30만)", dl(121),
         "건물 내 화재·가스·출입 경보 시스템을 상시 감시하는 방재 관제 업무입니다.",
         "open", cat.get("MON-2")),
        (_c4, "우편·문서 처리 담당 (코워크스페이스)", _r_seoul_jongno, "정규직", 0,
         "09:00", "18:00", "월~금", 0,
         json.dumps(["휠체어접근", "장애인화장실", "엘리베이터"], ensure_ascii=False),
         "wone 코워크 근무, 복합기·제본기·코팅기 완비, 문서 보안 교육",
         json.dumps(["청각", "자폐성", "지적"], ensure_ascii=False), "경증", 8,
         "4대보험, 중식 제공",
         "HWP·MS Word 기본 조작",
         "내부 문서 분류 (부서별·수신인별)\n우편물 개봉·스캔·파일명 규칙에 따라 저장 (Google Drive/SharePoint)\n문서 인쇄 요청 처리 (양면·컬러·제본)\n발송 우편물 봉투 작성·등기 발송\n문서 보관 파일링 (물리 보관함·디지털 인덱스 동기화)",
         "복합기(Canon/Ricoh), Adobe Acrobat, Google Drive, 우체국 사전접수 앱",
         "무관", "학력무관",
         "서류전형,면접,최종합격", "1명",
         "월 209만원", dl(90),
         "wone 코워크스페이스 내 문서 물류를 담당합니다.",
         "open", cat.get("FAC-4")),
    ]:
        conn.execute(_job_sql, j)

    conn.commit()

    existing = conn.execute("SELECT COUNT(*) FROM candidacies").fetchone()[0]
    if existing == 0:
        job1 = conn.execute("SELECT id FROM job_postings ORDER BY id LIMIT 1").fetchone()["id"]
        cur = conn.execute(
            """INSERT INTO candidacies (job_id, seeker_user_id, source, status, cover_letter)
               VALUES (?,?,'direct','pending',?)""",
            (job1, uid["seeker1"], "사무지원 직무에 지원합니다. 문서 작업에 자신 있습니다."),
        )
        conn.execute(
            """INSERT INTO status_history (candidacy_id, from_status, to_status, actor_id, comment)
               VALUES (?,?,?,?,?)""",
            (cur.lastrowid, "", "pending", uid["seeker1"], "직접 지원"),
        )

    existing = conn.execute("SELECT COUNT(*) FROM notices").fetchone()[0]
    if existing == 0:
        notices = [
            ("시스템 정기 점검 안내 (10/5 새벽 2시~4시)",
             "안정적인 서비스 운영을 위해 아래와 같이 정기 점검을 진행합니다.\n\n"
             "일시: 2026년 10월 5일 02:00 ~ 04:00\n"
             "내용: 서버 및 데이터베이스 점검\n\n"
             "점검 시간 동안 일부 서비스 이용이 제한될 수 있으니 양해 부탁드립니다.",
             "all", 1),
            ("하반기 장애인 채용 박람회 참가 기업 모집",
             "wone과 함께하는 하반기 장애인 채용 박람회에 참가하실 기업을 모집합니다.\n\n"
             "모집 기간: 10월 1일 ~ 10월 20일\n"
             "참가 대상: 장애인 고용에 관심 있는 모든 기업\n"
             "신청 방법: 기업 대시보드 > 문의하기를 통해 접수",
             "company", 0),
            ("이력서 음성 입력(STT) 기능 오픈 안내",
             "이력서 작성 시 음성으로 내용을 입력할 수 있는 기능이 추가되었습니다.\n"
             "이력서 작성 화면의 마이크 아이콘을 눌러 이용해 보세요.",
             "seeker", 0),
        ]
        for title, content, audience, pinned in notices:
            conn.execute(
                "INSERT INTO notices (title, content, audience, pinned, author_id) VALUES (?,?,?,?,?)",
                (title, content, audience, pinned, uid["op1"]),
            )

    conn.commit()
    conn.close()
    print("DB initialized (schema v3)")


def migrate():
    conn = get_sqlite()
    try:
        conn.execute("SELECT 1 FROM users LIMIT 1")
    except Exception:
        conn.close()
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
                last_notified_at TEXT,
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
        "manager_reassignment_log": """
            CREATE TABLE IF NOT EXISTS manager_reassignment_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seeker_user_id INTEGER NOT NULL,
                from_manager_id INTEGER,
                to_manager_id INTEGER,
                reason TEXT NOT NULL DEFAULT '',
                reassigned_by INTEGER NOT NULL,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );
        """,
        "inquiries": """
            CREATE TABLE IF NOT EXISTS inquiries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                category TEXT NOT NULL DEFAULT '',
                subject TEXT NOT NULL,
                content TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                answer TEXT NOT NULL DEFAULT '',
                answered_by INTEGER,
                answered_at TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_inquiries_user ON inquiries(user_id);
            CREATE INDEX IF NOT EXISTS idx_inquiries_status ON inquiries(status);
        """,
        "password_resets": """
            CREATE TABLE IF NOT EXISTS password_resets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT UNIQUE NOT NULL,
                expires_at TEXT NOT NULL,
                used_at TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_password_resets_user ON password_resets(user_id);
        """,
        "ref_certs": """
            CREATE TABLE IF NOT EXISTS ref_certs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                org TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_ref_certs_name ON ref_certs(name);
        """,
        "ref_schools": """
            CREATE TABLE IF NOT EXISTS ref_schools (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                level TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_ref_schools_name ON ref_schools(name);
        """,
        "notices": """
            CREATE TABLE IF NOT EXISTS notices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                audience TEXT NOT NULL DEFAULT 'all',
                pinned INTEGER NOT NULL DEFAULT 0,
                views INTEGER NOT NULL DEFAULT 0,
                author_id INTEGER NOT NULL,
                created_at TEXT DEFAULT (datetime('now','localtime')),
                updated_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_notices_audience ON notices(audience, pinned);
        """,
        "consult_requests": """
            CREATE TABLE IF NOT EXISTS consult_requests (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        seeker_user_id INTEGER NOT NULL,
                        category TEXT NOT NULL DEFAULT 'job',
                        content TEXT NOT NULL DEFAULT '',
                        method TEXT NOT NULL DEFAULT 'phone',
                        preferred_time TEXT NOT NULL DEFAULT '',
                        status TEXT NOT NULL DEFAULT 'pending',
                        manager_user_id INTEGER,
                        session_id INTEGER,
                        reply TEXT NOT NULL DEFAULT '',
                        created_at TEXT DEFAULT (datetime('now','localtime')),
                        handled_at TEXT
                    );
                    CREATE INDEX IF NOT EXISTS idx_consult_req_seeker ON consult_requests(seeker_user_id);
                    CREATE INDEX IF NOT EXISTS idx_consult_req_status ON consult_requests(status);
        """,
        "company_duties": """
            CREATE TABLE IF NOT EXISTS company_duties (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        company_id INTEGER NOT NULL,
                        category_id INTEGER,
                        title TEXT NOT NULL,
                        tasks TEXT NOT NULL DEFAULT '',
                        tools TEXT NOT NULL DEFAULT '',
                        difficulty TEXT NOT NULL DEFAULT 'mid',
                        remote_ok INTEGER NOT NULL DEFAULT 1,
                        fit TEXT NOT NULL DEFAULT '{}',
                        note TEXT NOT NULL DEFAULT '',
                        analysis_status TEXT NOT NULL DEFAULT 'none',
                        analysis_request TEXT NOT NULL DEFAULT '',
                        analysis_note TEXT NOT NULL DEFAULT '',
                        analyzed_by INTEGER,
                        analyzed_at TEXT,
                        created_at TEXT DEFAULT (datetime('now','localtime')),
                        updated_at TEXT
                    );
                    CREATE INDEX IF NOT EXISTS idx_company_duties_company ON company_duties(company_id);
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
        ("users", "email", "ALTER TABLE users ADD COLUMN email TEXT DEFAULT ''"),
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
        ("users", "accessibility_settings", "ALTER TABLE users ADD COLUMN accessibility_settings TEXT NOT NULL DEFAULT '{}'"),
        ("users", "must_change_password", "ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0"),
        ("companies", "reverify", "ALTER TABLE companies ADD COLUMN reverify INTEGER NOT NULL DEFAULT 0"),
        ("users", "notify_settings", "ALTER TABLE users ADD COLUMN notify_settings TEXT NOT NULL DEFAULT '{}'"),
        ("saved_searches", "last_notified_at", "ALTER TABLE saved_searches ADD COLUMN last_notified_at TEXT"),
        ("notifications", "kind", "ALTER TABLE notifications ADD COLUMN kind TEXT NOT NULL DEFAULT 'system'"),
        ("seeker_profiles", "target_categories", "ALTER TABLE seeker_profiles ADD COLUMN target_categories TEXT NOT NULL DEFAULT '[]'"),
        ("seeker_profiles", "match_note", "ALTER TABLE seeker_profiles ADD COLUMN match_note TEXT NOT NULL DEFAULT ''"),
        ("seeker_profiles", "match_updated_at", "ALTER TABLE seeker_profiles ADD COLUMN match_updated_at TEXT"),
        ("seeker_profiles", "match_updated_by", "ALTER TABLE seeker_profiles ADD COLUMN match_updated_by INTEGER"),
        ("companies", "esg_items", "ALTER TABLE companies ADD COLUMN esg_items TEXT NOT NULL DEFAULT '[]'"),
        ("companies", "esg_note", "ALTER TABLE companies ADD COLUMN esg_note TEXT NOT NULL DEFAULT ''"),
        ("companies", "remote_ok", "ALTER TABLE companies ADD COLUMN remote_ok INTEGER NOT NULL DEFAULT 0"),
        ("companies", "flexible_ok", "ALTER TABLE companies ADD COLUMN flexible_ok INTEGER NOT NULL DEFAULT 0"),
        ("companies", "shared_office_ok", "ALTER TABLE companies ADD COLUMN shared_office_ok INTEGER NOT NULL DEFAULT 0"),
        ("companies", "work_env_note", "ALTER TABLE companies ADD COLUMN work_env_note TEXT NOT NULL DEFAULT ''"),
    ]
    _col_cache = {}
    for tbl, col, ddl in _COLUMN_MIGRATIONS:
        if tbl not in _col_cache:
            _col_cache[tbl] = {row[1] for row in conn.execute(f"PRAGMA table_info({tbl})").fetchall()}
        if col not in _col_cache[tbl]:
            conn.execute(ddl)
            conn.commit()

    # 구 스키마의 placements.status='ended' 값을 변환함
    conn.execute("UPDATE placements SET status='departed' WHERE status='ended'")
    conn.commit()

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

    _certs_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "certs.json")
    if os.path.exists(_certs_path):
        with open(_certs_path, encoding="utf-8") as f:
            _certs = json.load(f)
        # certs.json 갱신으로 건수가 달라진 경우에만 다시 적재함
        if conn.execute("SELECT COUNT(*) FROM ref_certs").fetchone()[0] != len(_certs):
            conn.execute("DELETE FROM ref_certs")
            conn.executemany(
                "INSERT INTO ref_certs (name, org) VALUES (?,?)",
                [(c["name"], c.get("org", "")) for c in _certs],
            )
            conn.commit()

    if conn.execute("SELECT COUNT(*) FROM ref_schools").fetchone()[0] == 0:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "schools.json")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                schools = json.load(f)
            conn.executemany(
                "INSERT INTO ref_schools (name, level) VALUES (?,?)",
                [(s["name"], s.get("level", "")) for s in schools],
            )
            conn.commit()

    conn.close()


if __name__ == "__main__":
    conn = get_sqlite()
    try:
        cnt = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    except Exception:
        cnt = 0
    conn.close()
    # init()은 전체 테이블을 DROP하므로 운영 DB에서 실수로 실행되지 않도록 막음
    if cnt and "--force" not in sys.argv:
        print(f"users 테이블에 {cnt}건이 있습니다. 전체 초기화하려면 --force 를 붙이세요.")
        sys.exit(1)
    init()

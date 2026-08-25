def calc_profile_completeness(conn, uid: int) -> dict:
    profile = conn.execute(
        "SELECT * FROM seeker_profiles WHERE user_id=?", (uid,)
    ).fetchone()
    if not profile:
        return {"percent": 0, "missing": ["프로필 미작성"], "has_required": False}

    required_fields = {
        "disability_type_id": "장애유형",
        "severity": "장애정도",
        "accommodation_needs": "편의제공 필요사항",
    }
    optional_fields = {
        "gender": "성별",
        "birth_year": "출생연도",
        "region_id": "지역",
        "education_level": "최종학력",
        "desired_job": "희망직무",
        "career_years": "경력",
        "resume_path": "이력서",
        "consent_sensitive": "민감정보 동의",
    }

    filled = 0
    total = len(required_fields) + len(optional_fields)
    missing = []
    has_required = True

    for field, label in required_fields.items():
        val = profile[field]
        if field == "accommodation_needs":
            import json
            try:
                parsed = json.loads(val) if val else []
            except (json.JSONDecodeError, TypeError):
                parsed = []
            if parsed:
                filled += 1
            else:
                missing.append(label)
                has_required = False
        elif val:
            filled += 1
        else:
            missing.append(label)
            has_required = False

    for field, label in optional_fields.items():
        val = profile[field]
        if val:
            filled += 1
        else:
            missing.append(label)

    percent = round(filled / total * 100) if total > 0 else 0
    return {"percent": percent, "missing": missing, "has_required": has_required}


def get_recommended_jobs(conn, uid: int, limit: int = 5) -> list:
    import json

    profile = conn.execute(
        "SELECT sp.disability_type_id, sp.accommodation_needs, dt.name as disability_name "
        "FROM seeker_profiles sp "
        "LEFT JOIN disability_types dt ON sp.disability_type_id=dt.id "
        "WHERE sp.user_id=?",
        (uid,),
    ).fetchone()
    if not profile:
        return []

    seeker_needs = []
    try:
        seeker_needs = json.loads(profile["accommodation_needs"]) if profile["accommodation_needs"] else []
    except (json.JSONDecodeError, TypeError):
        pass

    disability_name = profile["disability_name"] or ""

    jobs = conn.execute(
        """SELECT jp.*, c.company_name,
                  jc.minor_name_ko AS category_name,
                  r.sido AS region_sido, r.sigungu AS region_sigungu
           FROM job_postings jp
           JOIN companies c ON jp.company_id=c.id
           LEFT JOIN job_categories jc ON jp.category_id=jc.id
           LEFT JOIN regions r ON jp.region_id=r.id
           WHERE jp.status='open'
             AND jp.id NOT IN (SELECT job_id FROM candidacies WHERE seeker_user_id=?)
           ORDER BY jp.created_at DESC""",
        (uid,),
    ).fetchall()

    scored = []
    for job in jobs:
        try:
            pref_disability = json.loads(job["preferred_disability"]) if job["preferred_disability"] else []
        except (json.JSONDecodeError, TypeError):
            pref_disability = []

        if pref_disability and disability_name not in pref_disability:
            continue  # 장애유형 불일치 건 제외

        try:
            job_accommodations = json.loads(job["accommodations_provided"]) if job["accommodations_provided"] else []
        except (json.JSONDecodeError, TypeError):
            job_accommodations = []

        if seeker_needs:
            matched = [n for n in seeker_needs if n in job_accommodations]
            match_count = len(matched)
            match_score = round(match_count / len(seeker_needs) * 100)
        else:
            match_count = 0
            match_score = 50  # 편의지원 미지정시 기본점수

        scored.append({
            "job": job,
            "match_score": match_score,
            "match_count": match_count,
            "total_needs": len(seeker_needs),
        })

    scored.sort(key=lambda x: (-x["match_score"], x["job"]["id"]))
    return scored[:limit]


def get_seeker_dashboard(conn, uid: int) -> dict:
    apps = conn.execute("""
        SELECT c.*, jp.title as job_title, co.company_name
        FROM candidacies c
        JOIN job_postings jp ON c.job_id=jp.id
        JOIN companies co ON jp.company_id=co.id
        WHERE c.seeker_user_id=?
        ORDER BY c.created_at DESC LIMIT 5
    """, (uid,)).fetchall()
    app_count = conn.execute(
        "SELECT COUNT(*) FROM candidacies WHERE seeker_user_id=?", (uid,)
    ).fetchone()[0]
    proposals = conn.execute("""
        SELECT COUNT(*) FROM candidacies
        WHERE seeker_user_id=? AND source='operator_matched' AND match_stage='proposed'
    """, (uid,)).fetchone()[0]
    open_jobs = conn.execute(
        "SELECT COUNT(*) FROM job_postings WHERE status='open'"
    ).fetchone()[0]
    profile = conn.execute(
        "SELECT id FROM seeker_profiles WHERE user_id=?", (uid,)
    ).fetchone()
    bookmark_count = conn.execute(
        "SELECT COUNT(*) FROM bookmarks WHERE user_id=?", (uid,)
    ).fetchone()[0]
    completeness = calc_profile_completeness(conn, uid)
    recommended = get_recommended_jobs(conn, uid)
    return dict(apps=apps, app_count=app_count, proposals=proposals,
                open_jobs=open_jobs, has_profile=profile is not None,
                bookmark_count=bookmark_count, profile_completeness=completeness,
                recommended=recommended)


def get_company_dashboard(conn, uid: int) -> dict:
    company = conn.execute(
        "SELECT * FROM companies WHERE user_id=?", (uid,)
    ).fetchone()
    if company:
        cid = company["id"]
        _filter = "AND (c.source='direct' OR c.match_stage='submitted')"
        job_count = conn.execute(
            "SELECT COUNT(*) FROM job_postings WHERE company_id=?", (cid,)
        ).fetchone()[0]
        open_count = conn.execute(
            "SELECT COUNT(*) FROM job_postings WHERE company_id=? AND status='open'",
            (cid,)
        ).fetchone()[0]
        total_applicants = conn.execute(f"""
            SELECT COUNT(*) FROM candidacies c
            JOIN job_postings jp ON c.job_id=jp.id
            WHERE jp.company_id=? {_filter}
        """, (cid,)).fetchone()[0]
        pending_apps = conn.execute(f"""
            SELECT COUNT(*) FROM candidacies c
            JOIN job_postings jp ON c.job_id=jp.id
            WHERE jp.company_id=? AND c.status='pending' {_filter}
        """, (cid,)).fetchone()[0]
        new_apps_this_week = conn.execute(f"""
            SELECT COUNT(*) FROM candidacies c
            JOIN job_postings jp ON c.job_id=jp.id
            WHERE jp.company_id=? {_filter}
              AND c.created_at >= datetime('now','localtime','-7 days')
        """, (cid,)).fetchone()[0]
        hired_count = conn.execute(f"""
            SELECT COUNT(*) FROM candidacies c
            JOIN job_postings jp ON c.job_id=jp.id
            WHERE jp.company_id=? AND c.status='hired' {_filter}
        """, (cid,)).fetchone()[0]
        interview_count = conn.execute(f"""
            SELECT COUNT(*) FROM candidacies c
            JOIN job_postings jp ON c.job_id=jp.id
            WHERE jp.company_id=? AND c.status='interview' {_filter}
        """, (cid,)).fetchone()[0]

        pipeline_rows = conn.execute(f"""
            SELECT c.status, COUNT(*) as cnt FROM candidacies c
            JOIN job_postings jp ON c.job_id=jp.id
            WHERE jp.company_id=? {_filter}
            GROUP BY c.status
        """, (cid,)).fetchall()
        pipeline = {r["status"]: r["cnt"] for r in pipeline_rows}

        recent_apps = conn.execute(f"""
            SELECT c.*, jp.title as job_title, u.name as seeker_name
            FROM candidacies c
            JOIN job_postings jp ON c.job_id=jp.id
            JOIN users u ON c.seeker_user_id=u.id
            WHERE jp.company_id=? {_filter}
            ORDER BY c.created_at DESC LIMIT 5
        """, (cid,)).fetchall()
        return dict(company=company, job_count=job_count, open_count=open_count,
                    total_applicants=total_applicants, pending_apps=pending_apps,
                    new_apps_this_week=new_apps_this_week, hired_count=hired_count,
                    interview_count=interview_count, pipeline=pipeline,
                    recent_apps=recent_apps)
    else:
        return dict(company=None, job_count=0, open_count=0,
                    total_applicants=0, pending_apps=0, new_apps_this_week=0,
                    hired_count=0, interview_count=0, pipeline={},
                    recent_apps=[])


def get_operator_dashboard(conn) -> dict:
    seeker_count = conn.execute(
        "SELECT COUNT(*) FROM users WHERE role='seeker'"
    ).fetchone()[0]
    company_count = conn.execute(
        "SELECT COUNT(*) FROM users WHERE role='company'"
    ).fetchone()[0]
    open_jobs = conn.execute(
        "SELECT COUNT(*) FROM job_postings WHERE status='open'"
    ).fetchone()[0]
    total_candidacies = conn.execute(
        "SELECT COUNT(*) FROM candidacies"
    ).fetchone()[0]
    pending_matches = conn.execute(
        "SELECT COUNT(*) FROM candidacies WHERE source='operator_matched' AND match_stage='proposed'"
    ).fetchone()[0]
    hired = conn.execute(
        "SELECT COUNT(*) FROM candidacies WHERE status='hired'"
    ).fetchone()[0]
    recent_candidacies = conn.execute("""
        SELECT c.*, jp.title as job_title, u.name as seeker_name, co.company_name
        FROM candidacies c
        JOIN job_postings jp ON c.job_id=jp.id
        JOIN users u ON c.seeker_user_id=u.id
        JOIN companies co ON jp.company_id=co.id
        ORDER BY c.updated_at DESC LIMIT 5
    """).fetchall()
    return dict(seeker_count=seeker_count, company_count=company_count,
                open_jobs=open_jobs, total_candidacies=total_candidacies,
                pending_matches=pending_matches, hired=hired,
                recent_candidacies=recent_candidacies)

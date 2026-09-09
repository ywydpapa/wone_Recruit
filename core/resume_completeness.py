import json


_WEIGHTS = {
    'desired_job': 10,
    'education': 15,
    'career': 15,
    'certification': 10,
    'language': 5,
    'intro': 20,
    'accommodation_needs': 10,
    'experience_summary': 10,
    'photo': 5,
}


def calc_completeness(conn, resume_id):
    detail = calc_completeness_detail(conn, resume_id)
    return detail['total'] if detail else 0


def calc_completeness_detail(conn, resume_id):
    resume = conn.execute("SELECT * FROM resumes WHERE id=?", (resume_id,)).fetchone()
    if not resume:
        return None

    filled = {}
    filled['desired_job'] = bool(resume['desired_job'])
    filled['experience_summary'] = bool(resume['experience_summary'])
    filled['photo'] = bool(resume['photo_path'])

    needs = resume['accommodation_needs']
    try:
        parsed = json.loads(needs) if needs else []
    except (json.JSONDecodeError, TypeError):
        parsed = []
    filled['accommodation_needs'] = len(parsed) > 0

    counts = {
        'education': conn.execute(
            "SELECT COUNT(*) FROM resume_educations WHERE resume_id=?", (resume_id,)
        ).fetchone()[0],
        'career': conn.execute(
            "SELECT COUNT(*) FROM resume_careers WHERE resume_id=?", (resume_id,)
        ).fetchone()[0],
        'certification': conn.execute(
            "SELECT COUNT(*) FROM resume_certifications WHERE resume_id=?", (resume_id,)
        ).fetchone()[0],
        'language': conn.execute(
            "SELECT COUNT(*) FROM resume_languages WHERE resume_id=?", (resume_id,)
        ).fetchone()[0],
        'intro': conn.execute(
            "SELECT COUNT(*) FROM resume_intros WHERE resume_id=?", (resume_id,)
        ).fetchone()[0],
    }
    for k, v in counts.items():
        filled[k] = v > 0

    total = sum(_WEIGHTS[k] for k, v in filled.items() if v)
    return {'sections': filled, 'total': total}

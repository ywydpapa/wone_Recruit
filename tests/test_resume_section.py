import json
import re

from tests.conftest import login
from tests.test_consult_requests import uid
from core.db import get_sqlite


def make_resume(user_id, name):
    conn = get_sqlite()
    cur = conn.execute("INSERT INTO resumes (user_id, name) VALUES (?,?)", (user_id, name))
    rid = cur.lastrowid
    conn.executemany(
        "INSERT INTO resume_careers (resume_id, sort_order, company_name, department, start_date, is_current) "
        "VALUES (?,?,?,?,?,?)",
        [(rid, 0, "한빛상사", "총무팀", "2021-03", 0), (rid, 1, "다온물류", "", "2023-05", 1)],
    )
    conn.execute(
        "INSERT INTO resume_certifications (resume_id, sort_order, cert_name, issuing_org, cert_date) VALUES (?,?,?,?,?)",
        (rid, 0, "컴퓨터활용능력 2급", "대한상공회의소", "2020-08"),
    )
    conn.commit()
    conn.close()
    return rid


def test_own_section(client):
    rid = make_resume(uid("seeker1"), "작년 이력서")
    login(client, "seeker1")
    r = client.get(f"/resumes/{rid}/sections/career")
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "작년 이력서"
    assert [x["car_company"] for x in data["rows"]] == ["한빛상사", "다온물류"]
    assert data["rows"][1]["car_current"] == 1
    cert = client.get(f"/resumes/{rid}/sections/cert").json()["rows"]
    assert cert == [{"cert_name": "컴퓨터활용능력 2급", "cert_org": "대한상공회의소", "cert_date": "2020-08"}]


def test_section_access(client):
    mine = make_resume(uid("seeker1"), "이력서")
    theirs = make_resume(uid("seeker2"), "남의 이력서")
    login(client, "seeker1")
    r = client.get(f"/resumes/{theirs}/sections/career")
    assert r.status_code == 404 and "한빛상사" not in r.text
    assert client.get(f"/resumes/{mine}/sections/intro").status_code == 400
    assert client.get(f"/resumes/{mine}/sections/resumes").status_code == 400
    client.get("/logout")
    login(client, "comp1")
    assert client.get(f"/resumes/{mine}/sections/career").status_code == 403


def test_edit_lists_only_own_others(client):
    me = uid("seeker1")
    cur = make_resume(me, "지금 이력서")
    make_resume(me, "예전 이력서")
    make_resume(uid("seeker2"), "남의 이력서")
    login(client, "seeker1")
    r = client.get(f"/resumes/{cur}/edit")
    assert r.status_code == 200
    m = re.search(r'<script id="otherResumes" type="application/json">(.*?)</script>', r.text)
    assert [x["name"] for x in json.loads(m[1])] == ["예전 이력서"]

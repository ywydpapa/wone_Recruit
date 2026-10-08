from tests.conftest import login
from tests.test_consult_requests import uid, assign, make_manager
from core.db import get_sqlite
from core.security import hash_password


def inbox(user_id):
    conn = get_sqlite()
    rows = conn.execute("SELECT * FROM messages WHERE user_id=?", (user_id,)).fetchall()
    conn.close()
    return rows


def send(client, to_id, body="안녕하세요"):
    return client.post("/api/messages/send", data={"to_id": to_id, "body": body})


def test_send_permissions(client):
    mgr = uid("counsel1")
    assign(mgr, uid("seeker1"), uid("op1"))
    other = make_manager("mgr_x")

    login(client, "seeker1")
    assert send(client, mgr, "면접 일정 문의").status_code == 200
    assert inbox(mgr)[0]["body"] == "면접 일정 문의"
    assert send(client, other).status_code == 403
    assert send(client, uid("seeker2")).status_code == 403
    assert send(client, uid("comp1")).status_code == 403
    assert send(client, uid("op1")).status_code == 200
    assert inbox(other) == []

    client.get("/logout")
    login(client, "counsel1")
    assert send(client, uid("seeker1")).status_code == 200
    assert send(client, uid("seeker2")).status_code == 403

    client.get("/logout")
    login(client, "comp1")
    assert send(client, uid("seeker1")).status_code == 403


def test_same_name_goes_to_id(client):
    mgr, seeker = uid("counsel1"), uid("seeker1")
    assign(mgr, seeker, uid("op1"))
    conn = get_sqlite()
    name = conn.execute("SELECT name FROM users WHERE id=?", (seeker,)).fetchone()["name"]
    twin = conn.execute(
        "INSERT INTO users (username, password, name, phone, role) VALUES (?,?,?,?,'seeker')",
        ("twin1", hash_password("admin1234"), name, "010-0000-0000"),
    ).lastrowid
    conn.commit()
    conn.close()

    login(client, "counsel1")
    assert send(client, seeker, "본인에게만").status_code == 200
    assert len(inbox(seeker)) == 1
    assert inbox(twin) == []


def test_bad_request(client):
    mgr = uid("counsel1")
    assign(mgr, uid("seeker1"), uid("op1"))
    login(client, "seeker1")
    assert send(client, 999999).status_code == 403
    assert send(client, mgr, "   ").status_code == 400
    assert send(client, mgr, "가" * 2001).status_code == 400
    assert client.post("/api/messages/send", data={"to_name": "매니저", "body": "x"}).status_code == 422


def test_my_manager(client):
    login(client, "seeker1")
    assert client.get("/api/messages/manager").status_code == 404
    mgr = uid("counsel1")
    assign(mgr, uid("seeker1"), uid("op1"))
    assert client.get("/api/messages/manager").json()["id"] == mgr
    r = client.get(f"/messages/{mgr}")
    assert f'name="to_id" value="{mgr}"' in r.text and 'name="csrf_token"' in r.text

    client.get("/logout")
    login(client, "counsel1")
    assert client.get("/api/messages/manager").status_code == 403

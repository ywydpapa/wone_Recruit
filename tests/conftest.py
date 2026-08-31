import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    monkeypatch.setenv("RECRUIT_DB_PATH", str(tmp_path / "test_recruit.db"))
    import init_db
    init_db.init()
    from fastapi.testclient import TestClient
    from main import app
    with TestClient(app) as c:
        yield c


def login(client, username, password="admin1234"):
    return client.post(
        "/login_check",
        data={"username": username, "password": password},
        follow_redirects=False,
    )

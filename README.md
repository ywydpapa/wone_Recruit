# wone_Recruit

장애인 친화 고용 플랫폼 **wone**의 채용관리 시스템 (채용 전 단계).

기업 회원가입·채용공고 등록, 구직자 프로필·지원, 플랫폼 운영자의 매칭 중개, 고용부담금 현황 분석을 담당한다. 채용 확정 이후의 근태·성과 관리는 [wone_ERP](https://github.com/ywydpapa/wone_ERP)가 담당한다.

> **설계 문서: [docs/plan.md](docs/plan.md)** — 프로젝트 전체 구조, 비즈니스 모델, DB 설계, 미결 사항

## Tech Stack

- Backend: FastAPI (Python)
- Frontend: Jinja2 + Bootstrap 5 + FontAwesome
- DB: SQLite (개발용) → PostgreSQL (프로덕션 예정)
- Auth: Session 기반 (Starlette SessionMiddleware)

## 실행 방법

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python init_db.py        # DB 초기화 (recruit.db 생성)
uvicorn main:app --reload
```

## 구조

```
main.py          # 앱 엔트리포인트
init_db.py       # DB 초기화 스크립트
core/            # 공통 모듈 (DB, 인증 등)
routers/         # auth, dashboard 등 라우터
templates/       # Jinja2 템플릿
static/          # CSS, JS, 이미지
docs/            # 설계 문서
```

## 현재 구현 상태

- 로그인 / 회원가입
- 대시보드 (실데이터 연동)

다음 단계는 [docs/plan.md의 12번 섹션](docs/plan.md) 참고

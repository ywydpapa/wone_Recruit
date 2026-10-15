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
cp .env.example .env     # 환경변수 설정 (아래 참고)
python init_db.py        # DB 초기화 (recruit.db 생성, 기존 데이터가 있으면 --force 필요)
bash scripts/fetch_assets.sh   # 음성/헤드마우스 자산 다운로드 (최초 1회)
uvicorn main:app --reload
```

음성 입력과 헤드마우스용 브라우저 라이브러리(`static/vendor/`)와 음성 모델은 용량 문제로 저장소에 들어가 있지 않습니다. 새 서버 배포 시 인터넷이 연결된 상태에서 `scripts/fetch_assets.sh`를 한 번 실행해 주세요. 용량은 약 2GB이며, 마이크 버튼 작동을 위해 필요합니다.

## 환경변수 설정

`.env.example`을 `.env`로 복사한 뒤 값을 입력합니다.
`SESSION_SECRET_KEY`는 필수이며, 아래 명령으로 생성할 수 있습니다.

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

운영 서버는 `ENVIRONMENT=production`으로 설정합니다. 이 경우 HTTPS가 적용되어 있어야 로그인이 유지됩니다.

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

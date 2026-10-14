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
uvicorn main:app --reload
```

## 환경변수 설정

`.env`는 비밀키 노출을 막기 위해 저장소에서 제외되어 있습니다. 저장소를 복제한 뒤 `.env.example`을 복사하여 서버별로 직접 작성해야 합니다.

- `SESSION_SECRET_KEY`: 필수 항목입니다. 설정하지 않으면 서버가 기동되지 않습니다. 로그인 세션 서명에 사용되며, 서버마다 별도로 생성하여 사용합니다. 타인에게 전달하지 않아야 합니다.
  ```bash
  python -c "import secrets; print(secrets.token_hex(32))"
  ```
- `ENVIRONMENT`: 운영 서버는 `production`으로 설정합니다. 이 경우 로그인 쿠키가 HTTPS에서만 전송되므로 도메인에 SSL 인증서를 먼저 적용해야 합니다. 적용하지 않으면 별도 오류 없이 로그인이 유지되지 않습니다.
- `BASE_URL`: 운영 도메인 주소를 입력합니다(예: `https://example.com`). 비밀번호 재설정 메일의 링크 주소로 사용됩니다.
- 그 외 메일, 사업자번호 조회, 음성 기능 항목은 선택 사항입니다. 설정하지 않으면 해당 기능만 제한되며 기본 기능은 정상 동작합니다.

호스팅 업체 관리 화면에서 환경변수를 입력하는 방식도 사용할 수 있으며, 이 경우 `.env` 파일은 작성하지 않아도 됩니다.

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

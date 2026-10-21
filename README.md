# wone_Recruit

장애인 친화 고용 플랫폼 wone의 채용관리 시스템입니다 (채용 전 단계).

기업 회원가입과 채용공고 등록, 구직자 프로필과 지원, 플랫폼 운영자의 매칭 중개, 고용부담금 현황 분석을 담당합니다.
채용 확정 이후의 근태와 성과 관리는 [wone_ERP](https://github.com/ywydpapa/wone_ERP)에서 담당합니다.

## 기술 스택

- Backend: FastAPI (Python)
- Frontend: Jinja2 + Bootstrap 5 + FontAwesome
- DB: SQLite (recruit.db, `RECRUIT_DB_PATH`로 경로 변경 가능)
- Auth: 세션 기반 (Starlette SessionMiddleware)

## 실행 방법

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env           # 환경변수 설정 (아래 참고)
python init_db.py              # DB 초기화 (recruit.db 생성)
bash scripts/fetch_assets.sh   # 음성/헤드마우스 자산 다운로드 (최초 1회)
uvicorn main:app --reload
```

- `init_db.py`는 기존 데이터가 있으면 실행되지 않습니다. `--force`는 전체 테이블을 삭제 후 재생성하므로 운영 서버에서는 사용하지 않도록 주의해 주십시오.
- 음성 입력과 헤드마우스용 브라우저 라이브러리(`static/vendor/`)와 음성 모델은 용량 문제로 저장소에서 제외했습니다. 신규 서버는 인터넷 연결 상태에서 `scripts/fetch_assets.sh`를 1회 실행합니다. 용량은 약 2GB이며, 마이크 버튼 작동에 필요합니다.

## 환경변수 설정

`.env.example`을 `.env`로 복사한 뒤 값을 입력합니다.

- `SESSION_SECRET_KEY`는 필수입니다. 아래 명령으로 생성합니다.
  ```bash
  python -c "import secrets; print(secrets.token_hex(32))"
  ```
- 운영 서버는 `ENVIRONMENT=production`으로 설정합니다. 이 경우 HTTPS가 적용되어 있어야 로그인이 유지됩니다.

## 배포 절차

```bash
git pull
pip install -r requirements.txt
```

이후 서버를 재시작합니다.

- 테이블과 컬럼 추가는 서버 기동 시 자동 반영되므로 별도 명령이 필요하지 않습니다.
- 반영 전 DB 백업을 권장합니다.

### 업로드 파일 이전 (최초 1회)

이력서와 사업자등록증은 권한자 외 열람을 막기 위해 웹 경로 밖(`var/uploads`)에 저장합니다.
기존 서버는 DB 백업 후 아래 스크립트로 기존 파일(`static/uploads`)을 이전합니다.

```bash
python scripts/move_uploads.py          # 이전 대상 확인 (변경 없음)
python scripts/move_uploads.py --apply  # 실제 이전
```

## 구조

```
main.py              # 앱 엔트리포인트, 미들웨어, 정적 파일 MIME 지정
init_db.py           # 스키마, 기초 데이터, 기동 시 컬럼 추가(migrate)
core/                # 공통 모듈
  db.py              # DB 연결
  deps.py            # 세션 확인, 권한, 템플릿 공통
  security.py        # 비밀번호 해시
  csrf.py            # CSRF 토큰
  rate_limit.py      # 로그인 시도 제한
  upload.py          # 업로드 저장, 비공개 파일 경로
  candidacy.py       # 지원 상태 전이
  matching.py        # 직무 역량 매칭
  levy.py            # 고용부담금 계산
  jobs.py            # 마감 공고 자동 종료 스케줄러
  mail.py            # 메일 발송
  bizno.py           # 사업자등록번호 확인
routers/             # 화면, API 라우터
  company/           # 기업 (공고, 지원자, 인재 검색, 추천, 면접 일정, 부담금, 채용 보고서)
  manager/           # 매니저 (담당 구직자, 상담, 매칭, 취업 연계)
  operator.py        # 운영자 (/op)
  seeker.py          # 구직자 (프로필, 지원)
  resume.py          # 이력서
  auth.py            # 로그인, 회원가입, 계정 잠금
  files.py           # 비공개 업로드 파일 권한 확인 후 제공
  accessibility.py   # 음성 인식(Whisper), 음성 안내
  nlu.py             # 음성 명령 의도 분석 (NLU_URL 서버 연동)
  messages.py, inquiry.py, notice.py, community.py, consult.py  # 메시지, 문의, 공지, 커뮤니티, 상담 신청
templates/           # Jinja2 템플릿, base.html에 공통 스크립트
static/js/           # 화면 스크립트
data/                # 자격증, 학교 검색용 데이터
scripts/             # 음성 자산 다운로드, 업로드 이전, 음성 점검
tests/               # pytest
var/                 # 비공개 업로드 파일 (저장소 제외)
```

### 화면 스크립트

| 파일 | 역할 |
|---|---|
| voice-parse.js | 인식된 문장을 명령 종류로 분류 |
| voice.js | 명령 실행, 받아쓰기, 브라우저 VAD, 음성 안내 재생 |
| seeker-voice.js | 구직자 화면 명령 |
| resume-voice.js | 이력서 항목 음성 입력 |
| company-voice.js | 기업 화면 명령 (지원자 선택 등) |
| a11y-widget.js | 접근성 설정 위젯 (고대비, 글자 크기 등) |
| headmouse.js | 헤드마우스 |
| ref-search.js | 자격증, 학교 검색 |
| offer-modal.js | 기업의 구직자 제안 창 |
| mypage-nav.js | 마이페이지 메뉴 폭 조절 |
| pw-field.js | 비밀번호 입력칸 표시 전환 |

음성 명령은 voice-parse.js의 `classify`에 분류를 추가한 뒤 voice.js 또는 화면별 스크립트에 연결합니다.

## 현재 구현 상태

- 기업: 회원가입, 기업 프로필, 채용공고 등록 및 연장, 지원자 관리, 인재 검색, 면접 일정, 채용 보고서, 고용부담금 계산
- 구직자: 프로필, 이력서, 공고 지원, 지원 현황
- 매니저: 담당 구직자, 상담 일정 및 기록, 매칭, 취업 연계
- 운영자: 기업 및 공고 승인, 매니저 배정, 문의 답변, 접속 기록
- 공통: 메시지, 알림, 문의, 공지, 커뮤니티
- 보안: CSRF, 로그인 시도 제한, 계정 잠금, 유휴 시간 자동 로그아웃, 비공개 파일 권한 확인
- 접근성: 음성 명령 및 안내, 헤드마우스, 고대비

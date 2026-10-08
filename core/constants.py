STATUS_LABELS = {
    "pending": "접수",
    "reviewing": "검토중",
    "shortlisted": "서류합격",
    "interview": "면접",
    "offer": "제의",
    "hired": "채용",
    "rejected": "불합격",
    "withdrawn": "지원취소",
}

MATCH_STAGE_LABELS = {
    "proposed": "제안됨",
    "seeker_confirmed": "구직자수락",
    "submitted": "기업전달",
}

JOB_STATUS_LABELS = {
    "pending_review": "검토 대기",
    "open": "공개",
    "rejected": "반려",
    "draft": "임시저장",
    "closed": "마감",
    "filled": "채용완료",
}

JOB_STATUS_BADGE = {
    "pending_review": "bg-info text-dark",
    "open": "bg-success",
    "rejected": "bg-danger",
    "draft": "bg-secondary",
    "closed": "bg-warning text-dark",
    "filled": "bg-info text-dark",
}


EMPLOYMENT_TYPES = ["정규직", "계약직", "인턴", "파견", "프리랜서"]

EDUCATION_LEVELS = ['고졸', '전문대졸', '대졸', '석사', '박사']

MOBILITY_TYPES = ['자차', '대중교통', '활동보조인', '전동휠체어', '도보', '기타']

COMMUTE_OPTIONS = [15, 30, 45, 60, 90, 120]

COMMUNICATION_OPTIONS = ['음성', '문자', '수어', '필담']

# 보조기기 (카테고리 -> [(이름, FA 아이콘)])
ASSISTIVE_DEVICES = {
    "시각": [
        ("화면낭독기", "fa-display"),
        ("화면확대기", "fa-magnifying-glass-plus"),
        ("점자디스플레이", "fa-braille"),
        ("독서확대기", "fa-book-open"),
    ],
    "청각": [
        ("보청기", "fa-ear-listen"),
        ("인공와우", "fa-circle-dot"),
        ("영상전화기", "fa-video"),
        ("진동알리미", "fa-bell"),
    ],
    "지체/뇌병변": [
        ("특수키보드", "fa-keyboard"),
        ("특수마우스", "fa-computer-mouse"),
        ("음성인식입력", "fa-microphone"),
        ("높이조절책상", "fa-table"),
    ],
    "언어": [
        ("AAC기기", "fa-tablet-screen-button"),
        ("의사소통보드", "fa-comment-dots"),
    ],
}

DAILY_HOURS_OPTIONS = [4, 6, 8]

PREFERRED_TIME_OPTIONS = ['오전', '오후', '풀타임', '유연']

REST_FREQUENCY_OPTIONS = ['불필요', '1시간마다', '2시간마다', '수시']

ACCOMMODATION_OPTIONS = [
    '휠체어접근', '장애인화장실', '엘리베이터', '보조기기지원',
    '수어통역', '점자자료', '유연근무', '재택근무',
    '활동보조인출입', '휴게공간', '주차지원',
]

# 장애유형 -> 보조기기/지원도구 아이콘 (FA6 Free solid)
DISABILITY_ICONS = {
    "지체": "fa-keyboard",
    "뇌병변": "fa-computer-mouse",
    "시각": "fa-display",
    "청각": "fa-ear-listen",
    "언어": "fa-tablet-screen-button",
    "안면": "fa-mask",
    "신장": "fa-syringe",
    "심장": "fa-stethoscope",
    "간": "fa-pills",
    "호흡기": "fa-mask-ventilator",
    "장루·요루": "fa-briefcase-medical",
    "뇌전증": "fa-id-card",
    "지적": "fa-book-open-reader",
    "자폐성": "fa-headphones",
    "정신": "fa-comments",
}

EDUCATION_LEVELS_DETAIL = [
    '고등학교', '전문대(2/3년)', '대학교(4년)', '대학원(석사)', '대학원(박사)',
]

GRADUATION_STATUS = ['졸업', '재학', '휴학', '중퇴', '수료', '졸업예정']

GPA_SCALES = ['4.0', '4.3', '4.5', '100']

CAREER_EMPLOYMENT_TYPES = ['정규직', '계약직', '인턴', '파견직', '프리랜서', '아르바이트']

CAREER_POSITIONS = [
    '인턴', '사원', '주임', '대리', '과장', '차장', '부장', '이사', '상무', '전무', '부사장', '사장',
    '선임', '책임', '수석', '연구원', '선임연구원', '책임연구원', '수석연구원',
    '팀원', '팀장', '파트장', '실장', '본부장', '센터장', '그룹장', '매니저', '프로', 'TL', 'PL', 'PM',
]

CAREER_DEPTS = [
    '인사', 'HR', 'HRD', '인사총무', '노무', '채용', '급여', '조직문화', '교육', '교육기획', 'LMS', '총무', '법무',
    '재무', '회계', '세무', '자금', '감사', 'IR', '경영지원', '기획', '전략기획', '경영기획', '사업기획', '상품기획',
    '영업', '국내영업', '해외영업', '기술영업', '영업관리', '영업지원', '마케팅', '홍보', '디자인',
    '구매', '구매전략', '외자구매', '내자구매', '자재', '프라이싱', 'SCM', '물류', '물류관리', '무역', '수출입',
    'CS', '고객지원', '콜센터', '사무지원', '시설관리',
    '개발', 'IT', '인프라', '클라우드', '정보보안', '정보보호', '데이터', 'AX', 'DX', 'ERP', '연구개발', 'R&D',
    '생산', '생산관리', '생산기술', '설비', '품질', '품질관리', '품질보증', '공정기술', '양산기술', '기반기술', '분석기술', '불량분석',
    'MLCC', 'PCB', 'Mask', 'Etching', 'NAND', 'eSSD',
    '안전', 'EHS', '보건', '산업안전', '산업위생', '환경',
]

LANGUAGE_LIST = ['영어', '일본어', '중국어', '스페인어', '독일어', '프랑스어', '러시아어', '베트남어', '한국수어']

LANGUAGE_LEVELS = ['네이티브', '비즈니스', '일상회화', '기초']

AWARD_CATEGORIES = ['수상', '봉사활동', '동아리', '대외활동', '교육이수', '기타']

PORTFOLIO_LINK_TYPES = ['GitHub', '블로그', '포트폴리오', '노션', '기타']

PURPOSE_LABELS = {
    "applicant_review": "지원자 검토",
    "talent_search": "인재 검색",
    "operator_view": "운영자 조회",
    "manager_view": "매니저 조회",
}

ROLE_LABELS = {
    "seeker": "구직자",
    "company": "기업",
    "operator": "운영자",
    "manager": "채용매니저",
}

COMPANY_APPROVAL_LABELS = {
    "pending": "대기",
    "approved": "승인",
    "rejected": "반려",
}

COMPANY_APPROVAL_BADGE = {
    "pending": "bg-warning text-dark",
    "approved": "bg-success",
    "rejected": "bg-danger",
}

FIT_BADGE_CLASS = {
    "추천": "bg-success",
    "조건부": "bg-warning text-dark",
}

COMMUNITY_CATEGORIES = [
    ("all", "전체"),
    ("general", "자유"),
    ("job", "취업"),
    ("qna", "Q&A"),
    ("tip", "꿀팁"),
    ("life", "일상"),
]

COMPANY_SIZES = [
    '소기업(50인미만)',
    '중소기업(50~299인)',
    '중견기업(300~999인)',
    '대기업(1000인이상)',
]

INDUSTRY_TYPES = [
    'IT/소프트웨어', '제조업', '유통/물류', '금융/보험',
    '건설/부동산', '교육', '의료/복지', '미디어/콘텐츠',
    '공공기관', '서비스업', '기타',
]

POST_CATEGORIES = {
    "general": ("자유", "secondary"),
    "notice": ("공지", "dark"),
    "qna": ("Q&A", "info"),
    "job": ("취업", "primary"),
    "life": ("일상", "success"),
    "tip": ("꿀팁", "warning"),
}

CONSULT_CATEGORIES = {
    "job": "취업 상담",
    "device": "보조장비",
    "work": "근무 중 어려움",
    "rights": "권익 보호",
    "etc": "기타",
}

CONSULT_METHODS = {"phone": "전화", "video": "화상", "in_person": "대면", "chat": "메시지"}

CONSULT_REQ_STATUS = {
    "pending": ("접수", "secondary"),
    "accepted": ("확인", "info"),
    "scheduled": ("일정 확정", "primary"),
    "done": ("완료", "success"),
    "cancelled": ("취소", "light"),
}

ESG_ITEMS = [
    "장애인 표준사업장", "장애인 고용 우수사업주", "연계고용 참여",
    "사회적기업 인증", "ESG 보고서 공개", "장애인 인식개선 교육",
]

DUTY_DIFFICULTY = {"low": "쉬움", "low-mid": "보통 이하", "mid": "보통", "mid-high": "보통 이상", "high": "어려움"}

# job_categories.fit_* 점수 0~3
FIT_TYPES = {
    "fit_physical_lower": "지체(하지)",
    "fit_physical_upper": "지체(상지)",
    "fit_hearing": "청각",
    "fit_visual_low": "시각(저시력)",
    "fit_intellectual": "지적",
    "fit_autism": "자폐성",
    "fit_mental": "정신",
    "fit_internal_organ": "내부기관",
    "fit_brain_lesion": "뇌병변",
}
FIT_LEVELS = {0: ("어려움", "danger"), 1: ("제한적", "warning"), 2: ("가능", "info"), 3: ("적합", "success")}

DUTY_ANALYSIS_STATUS = {"none": ("미요청", "light"), "requested": ("분석 대기", "warning"), "done": ("분석 완료", "success")}

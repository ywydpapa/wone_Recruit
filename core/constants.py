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

LANGUAGE_LIST = ['영어', '일본어', '중국어', '기타']

LANGUAGE_LEVELS = ['네이티브', '비즈니스', '일상회화', '기초']

AWARD_CATEGORIES = ['수상', '봉사활동', '동아리', '대외활동', '교육이수', '기타']

PORTFOLIO_LINK_TYPES = ['GitHub', '블로그', '포트폴리오', '노션', '기타']

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

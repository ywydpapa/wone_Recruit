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

ASSISTIVE_TECH_OPTIONS = [
    '스크린리더', '화면확대', '특수키보드', '음성인식',
    '보청기', '점자디스플레이', '기타',
]

DAILY_HOURS_OPTIONS = [4, 6, 8]

PREFERRED_TIME_OPTIONS = ['오전', '오후', '풀타임', '유연']

REST_FREQUENCY_OPTIONS = ['불필요', '1시간마다', '2시간마다', '수시']

ACCOMMODATION_OPTIONS = [
    '휠체어접근', '장애인화장실', '엘리베이터', '보조기기지원',
    '수어통역', '점자자료', '유연근무', '재택근무',
    '활동보조인출입', '휴게공간', '주차지원',
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

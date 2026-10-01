import re

# 모델이 숫자를 외국어식으로 읽으므로 TTS 전에 숫자/날짜를 한글로 변환함
DIGITS = "영일이삼사오육칠팔구"
NATIVE = ["", "한", "두", "세", "네", "다섯", "여섯", "일곱", "여덟", "아홉"]
NATIVE_TEN = ["", "열", "스물", "서른", "마흔", "쉰", "예순", "일흔", "여든", "아흔"]

# 모델이 잘못 읽는 단어를 보정함
WORDS = {"현황": "혀놩", "(주)": "주식회사 "}

# 영어 발음을 방지하기 위해 대문자 약어는 알파벳 이름으로 변환함
ABC = dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ", ["에이", "비", "씨", "디", "이", "에프", "지", "에이치", "아이", "제이", "케이", "엘", "엠", "엔", "오", "피", "큐", "알", "에스", "티", "유", "브이", "더블유", "엑스", "와이", "제트"]))

DATE_RE = re.compile(r"(?<!\d)((?:19|20)\d\d)([-./]?)(\d\d)\2(\d\d)(?!\d)")
NUMS_RE = re.compile(r"(?<![\d-])\d{2,4}(?:-\d{2,5}){2}(?![\d-])")
TIME_RE = re.compile(r"(?<!\d)(\d{1,2}):(\d\d)(?!\d)")
TIME_KO_RE = re.compile(r"(?<!\d)(\d{1,2})\s?시(?!간)(?:\s?(\d{1,2})\s?분)?")
UNITS = {"km": "킬로미터", "kg": "킬로그램", "cm": "센티미터", "mm": "밀리미터", "㎡": "제곱미터", "m²": "제곱미터"}
RANGE_RE = re.compile(r"(\d[\d,]*)\s*~\s*(\d[\d,]*)(\s?)(명|개월|개|건|장|곳|군데|권|통|마리|달|살|가지|시간|년|세|일|분|회|만\s?원|원|%)")
COUNTER_RE = re.compile(r"(?<!\d)(\d{1,2})\s?(명|개(?!월)|건|장(?!애)|곳|군데|권|통|마리|달(?!러)|살|가지|시간|번째|차례)")


def sino(n):
    if n == 0:
        return "영"
    parts = []
    for unit in ["", "만", "억", "조"]:
        g = n % 10000
        n //= 10000
        if g:
            s = ""
            for d, u in zip(f"{g:04d}", ["천", "백", "십", ""]):
                d = int(d)
                if d:
                    s += ("" if d == 1 and u else DIGITS[d]) + u
            if unit == "만" and g == 1:
                s = ""
            parts.append(s + unit)
        if not n:
            break
    return " ".join(reversed(parts))


def native(n):
    return "스무" if n == 20 else NATIVE_TEN[n // 10] + NATIVE[n % 10]


def read_date(m):
    y, mon, d = int(m[1]), int(m[3]), int(m[4])
    if not (1 <= mon <= 12 and 1 <= d <= 31):
        return m[0]
    mon_txt = {6: "유", 10: "시"}.get(mon, sino(mon))
    return f"{sino(y)} 년 {mon_txt} 월 {sino(d)} 일"


def read_nums(m):
    return ", ".join("".join("공" if c == "0" else DIGITS[int(c)] for c in g) for g in m[0].split("-"))


def read_time(m):
    h, mi = int(m[1]), int(m[2] or 0)
    if h > 24 or mi > 59:
        return m[0]
    hour = native(h) if 1 <= h <= 12 else sino(h)
    return f"{hour} 시" + (f" {sino(mi)} 분" if mi else "")


def read_counter(m):
    n, unit = int(m[1]), m[2]
    if not n:
        return m[0]
    if unit == "건" and n > 10:
        return f"{sino(n)} {unit}"
    if n == 1 and unit == "번째":
        return "첫 번째"
    return f"{native(n)} {unit}"


def read_num(m):
    tail = m.string[m.end():m.end() + 1]
    return sino(int(m[0])) + (" " if tail and not tail.isspace() and tail != "여" else "")


def read_mmdd(m):
    mon, d = int(m[1]), int(m[2])
    return f"{mon}월 {d}일" if 1 <= mon <= 12 and 1 <= d <= 31 else m[0]


def ko_text(text):
    for k, v in WORDS.items():
        text = text.replace(k, v)
    text = re.sub(r"(?<![A-Za-z])D-?[Dd]ay\b", "디데이", text)
    text = re.sub(r"(?<![A-Za-z])D-(\d+)", r"디 \1", text)
    text = re.sub(r"(?<![A-Za-z])([A-Z])&([A-Z])(?![A-Za-z])", lambda m: ABC[m[1]] + "앤" + ABC[m[2]], text)
    text = re.sub(r"(?<![A-Za-z])B(\d+)\s?층", r"지하 \1층", text)
    text = re.sub(r"(?<![A-Za-z])[A-Z](?=\d)", lambda m: ABC[m[0]] + " ", text)
    text = re.sub(r"(?<=\d)\s?(km|kg|cm|mm|㎡|m²)(?![A-Za-z])", lambda m: " " + UNITS[m[1]], text)
    text = re.sub(r"\(([월화수목금토일])\)", r" \1요일 ", text)
    text = re.sub(r"(?<!\d)0\d{8,10}(?!\d)", lambda m: "".join("공" if c == "0" else DIGITS[int(c)] for c in m[0]), text)
    text = re.sub(r"(?<![\d:])(\d{1,2}):(\d)(?![\d:])", r"\1 대 \2", text)
    # 범위 표현은 앞 숫자에도 단위를 붙임
    text = re.sub(r"(?:^|(?<=\s))~\s*(\d[\d/.:-]*)", r"\1까지", text)
    text = RANGE_RE.sub(r"\1\3\4에서 \2\3\4", text)
    text = re.sub(r"\s*~\s*(?=\d)", "에서 ", text)
    text = re.sub(r"(?<![\d/])(\d{1,2})/(\d{1,2})(?![\d/])", read_mmdd, text)
    text = re.sub(r"[\u00b7ㆍ/\u2026~]", ", ", text)
    text = re.sub(r"[※★☆●○■□▶►▷→←↑↓•]", " ", text)
    text = re.sub(r"(?<![A-Za-z])[A-Z]{2,5}(?![a-z])", lambda m: "".join(ABC[c] for c in m[0]), text)
    # 괄호, 대시는 쉼표로 바꿔 끊어 읽도록 함
    text = re.sub(r"\s*[()\[\]]\s*", ", ", re.sub(r"\s+[-\u2013]\s+", ", ", text))
    text = re.sub(r",(\s*,)+", ",", text).strip(", ")
    text = DATE_RE.sub(read_date, text)
    text = NUMS_RE.sub(read_nums, text)
    text = TIME_RE.sub(read_time, text)
    text = TIME_KO_RE.sub(read_time, text)
    text = re.sub(r"(?<=\d),(?=\d{3})", "", text)
    text = text.replace("%", " 퍼센트")
    text = re.sub(r"(\d+)\.(\d+)", lambda m: sino(int(m[1])) + " 점 " + "".join(DIGITS[int(c)] for c in m[2]), text)
    text = re.sub(r"(?<!\d)(6|10)\s?월", lambda m: {"6": "유", "10": "시"}[m[1]] + " 월", text)
    text = COUNTER_RE.sub(read_counter, text)
    text = re.sub(r"\d+", read_num, text)
    return re.sub(r"\s+", " ", text).strip()


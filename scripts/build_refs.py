import json
import os
import re
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")

PASSON_DIR = os.environ.get("PASSON_DIR", os.path.expanduser("~/Documents/passon-project"))
CODES_PATH = os.path.join(PASSON_DIR, "data/jd-analysis/license_codes/codes.json")
# passon에서 건별 검증한 자격 목록임 (2026-09-30)
VERIFIED_PATH = os.path.join(PASSON_DIR, "backups/verified_certs_20260930.json")

QNET_LIST_URL = "http://openapi.q-net.or.kr/api/service/rest/InquiryListNationalQualifcationSVC/getList"

NATL_LICENSE_SUFFIX_ORG = {
    "기능사": "한국산업인력공단",
    "산업기사": "한국산업인력공단",
    "기사": "한국산업인력공단",
    "기능장": "한국산업인력공단",
    "기술사": "한국산업인력공단",
}
# 대한상공회의소 주관이 확인된 자격만 등록함 (FLEX 등은 상명대 주관이므로 제외)
CCI_NAMES = {
    "컴퓨터활용능력", "워드프로세서", "유통관리사", "판매관리사", "무역영어",
    "비서", "한글속기", "전자상거래관리사", "전자상거래운용사", "전산회계운용사",
}

# 국제자격증 목록임 (insert_intl_certs.mjs 기준, 공급망/금융/IT 주요 자격 보강)
INTL_CERTS = [
    ("AWS Certified Cloud Practitioner (CLF-C02)", "AWS"),
    ("AWS Certified Solutions Architect - Associate (SAA-C03)", "AWS"),
    ("AWS Certified Developer - Associate (DVA-C02)", "AWS"),
    ("AWS Certified Solutions Architect - Professional (SAP-C02)", "AWS"),
    ("AWS Certified DevOps Engineer - Professional (DOP-C02)", "AWS"),
    ("Google Cloud Digital Leader", "Google Cloud"),
    ("Google Associate Cloud Engineer", "Google Cloud"),
    ("Google Professional Cloud Architect", "Google Cloud"),
    ("Microsoft Azure Fundamentals (AZ-900)", "Microsoft"),
    ("Microsoft Azure Administrator (AZ-104)", "Microsoft"),
    ("Microsoft Azure Solutions Architect Expert (AZ-305)", "Microsoft"),
    ("CompTIA Security+ (SY0-701)", "CompTIA"),
    ("CISSP", "ISC2"),
    ("Cisco CCNA (200-301)", "Cisco"),
    ("PMP (Project Management Professional)", "PMI"),
    ("CAPM (Certified Associate in Project Management)", "PMI"),
    ("CPIM (Certified in Planning and Inventory Management)", "ASCM(APICS)"),
    ("CSCP (Certified Supply Chain Professional)", "ASCM(APICS)"),
    ("CLTD (Certified in Logistics, Transportation and Distribution)", "ASCM(APICS)"),
    ("Six Sigma Green Belt (ASQ CSSGB)", "ASQ"),
    ("Six Sigma Black Belt (ASQ CSSBB)", "ASQ"),
    ("CFA", "CFA Institute"),
    ("CFA Level 1", "CFA Institute"),
    ("CFA Level 2", "CFA Institute"),
    ("CFA Level 3", "CFA Institute"),
    ("FRM", "GARP"),
    ("FRM Part 1", "GARP"),
    ("FRM Part 2", "GARP"),
    ("USCPA (미국공인회계사)", "AICPA"),
    ("ACCA (영국공인회계사)", "ACCA"),
    ("CIA (국제공인내부감사사)", "IIA"),
    ("SHRM-SCP", "SHRM"),
    ("SHRM-CP", "SHRM"),
    ("PHR (Professional in Human Resources)", "HRCI"),
    ("SPHR (Senior Professional in Human Resources)", "HRCI"),
    ("LEED AP (Leadership in Energy and Environmental Design)", "USGBC"),
    ("CISA (국제공인정보시스템감사사)", "ISACA"),
    ("CISM (국제공인정보보안관리자)", "ISACA"),
    ("Oracle OCP (Database Administration)", "Oracle"),
    ("ITIL 4 Foundation", "PeopleCert"),
    ("CPSM", "ISM"),
    ("CPSM (Certified Professional in Supply Management)", "ISM"),
    ("CSM (Certified ScrumMaster)", "Scrum Alliance"),
    ("LPIC-1 (Linux Administrator)", "LPI"),
]

# 장애인 구직자가 많이 보유한 자격/어학 중 국가자격면허코드에 없는 항목을 수동 추가함
MANUAL_CERTS = [
    ("요양보호사", "시도지사"),
    ("사회복지사 1급", "한국산업인력공단"),
    ("사회복지사 2급", "한국사회복지사협회"),
    ("보육교사 2급", "한국보육진흥원"),
    ("바리스타", "한국커피협회"),
    ("텔레마케팅관리사", "한국산업인력공단"),
    ("유통관리사 1급", "대한상공회의소"),
    ("유통관리사 2급", "대한상공회의소"),
    ("물류관리사", "한국산업인력공단"),
    ("무역영어 1급", "대한상공회의소"),
    ("사회조사분석사 2급", "한국산업인력공단"),
    ("직업상담사 2급", "한국산업인력공단"),
    ("재경관리사", "삼일회계법인"),
    ("전산세무 2급", "한국세무사회"),
    ("전산회계 1급", "한국세무사회"),
    ("전산회계 2급", "한국세무사회"),
    ("TOEIC", "YBM"),
    ("TOEIC Speaking", "YBM"),
    ("OPIc", "한국외국어평가원"),
    ("TOEFL", "ETS"),
    ("TEPS", "서울대학교TEPS관리위원회"),
    ("JLPT", "일본국제교류기금"),
    ("HSK", "중국국가한판"),
    ("한국사능력검정시험", "국사편찬위원회"),
    ("KBS한국어능력시험", "한국방송공사"),
    ("한국실용글쓰기검정", "한국국어능력평가협회"),
    ("컴퓨터활용능력", "대한상공회의소"),
    ("워드프로세서", "대한상공회의소"),
    ("ITQ", "한국생산성본부"),
    ("GTQ", "한국생산성본부"),
    ("MOS", "마이크로소프트"),
    ("리눅스마스터 2급", "한국정보통신진흥협회"),
    ("네트워크관리사 2급", "한국정보통신자격협회"),
    ("PC정비사 2급", "한국정보통신자격협회"),
    ("운전면허 1종 보통", "도로교통공단"),
    ("운전면허 2종 보통", "도로교통공단"),
    ("평생교육사 2급", "국가평생교육진흥원"),
    ("한국어교원 2급", "국립국어원"),
]

UNIV_PK = "15107736"
UNIV_SVC_TABLE = "tn_pubr_public_univ_info_svc"
UNIV_COLS = [
    "SCHL_NM", "SCHL_ENG_NM", "MAINBRANCH_NM", "UNIV_SE_NM", "SCHL_SE_NM",
    "FNDN_FORM_SE_NM", "CTPV_CD", "CTPV_NM", "LCTN_ROAD_NM_ADDR", "LCTN_LOTNO_ADDR",
    "STR_NM_ZIP", "LCTN_ZIP", "HMPG_ADDR", "RPRS_TEL_NO", "RPRS_FXNO",
    "FNDN_YMD", "CRTR_YR", "CRTR_YMD",
]
UNIV_LEVEL_MAP = {"대학": "대학교(4년)", "전문대학": "전문대(2/3년)"}

HS_PK = "15021148"
HS_SVC_TABLE = "tn_pubr_public_elesch_mskul_lc_svc"
HS_COLS = [
    "SCHOOL_ID", "SCHOOL_NM", "SCHOOL_SE", "FOND_DATE", "FOND_TYPE", "BNHH_SE",
    "OPER_STTUS", "LNMADR", "RDNMADR", "CDDC_CODE", "CDDC_NM", "EDC_SPORT",
    "EDC_SPORT_NM", "CREAT_DATE", "CHANGE_DATE", "LATITUDE", "LONGITUDE", "REFERENCE_DATE",
]


def strip_paren(name):
    return re.sub(r"\([^)]*\)", "", name).strip()


# Q넷 목록과 비교하기 위해 등급 표기를 유지함
def norm_qnet(name):
    return name.replace("(", "").replace(")", "").replace(" ", "").strip()


# DATA_GO_KR_SERVICE_KEY가 필요함
def fetch_qnet_names():
    key = os.environ.get("DATA_GO_KR_SERVICE_KEY", "")
    if not key:
        return []
    qs = urllib.parse.urlencode({"serviceKey": key, "numOfRows": "2000", "pageNo": "1"})
    req = urllib.request.Request(QNET_LIST_URL + "?" + qs, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as res:
        xml = res.read().decode("utf-8")
    return re.findall(r"<jmfldnm>(.*?)</jmfldnm>", xml)


def cert_org(name, qnet_names):
    base = strip_paren(name)
    if prefix_org(base):
        return prefix_org(base)
    for suf, org in NATL_LICENSE_SUFFIX_ORG.items():
        if base.endswith(suf):
            return org
    if base in CCI_NAMES:
        return "대한상공회의소"
    if norm_qnet(name) in qnet_names:
        return "한국산업인력공단"
    return ""


# 괄호 안 N급만 괄호를 제거함. 제N급, N종, 분야 표기는 유지함
def normalize_grade(name):
    name = re.sub(r"^(\d+)급\s+(.+)$", r"\2 \1급", name)
    return re.sub(r"\s*\((\d+)급\)", r" \1급", name)


def cert_key(name):
    return re.sub(r"[\s()\u00b7]", "", name)


# 등급 분리 이후에도 유지해야 하는 구제도 명칭임. 등급 없는 표기 자체가 별도 자격임
# 명칭이 변경된 자격임. 구 명칭은 신 명칭으로 통합함 (2024-05 문화재 -> 국가유산)
CERT_RENAMED = {"문화재수리": "국가유산수리", "보험중계사": "보험중개사"}

# 신규 발급이 종료되었거나 명칭이 변경된 자격임. 보유자가 이력서에 기재할 수 있도록 유지하고 (구) 표기를 붙임
OLD_CERT_PREFIXES = (
    "손해사정사(제", "방화관리자", "전통식품명인", "항만하역교통안전관리자", "선박교통안전관리자",
    "산림토목기술자", "영림기술자", "보육사", "증권분석사", "산업위생지도사", "의무기록사",
    "사회교육전문요원", "접객종사원", "관광숙박업지배인", "생활체육지도자", "경기지도자", "정신보건",
    "특수급무선통신사", "위생사 1급", "위생사 2급", "위생시험사", "투자상담사", "선물중개사",
    "한약조제사", "사회복지사 3급", "건축사(예비)", "MCSE",
)

TIDY_KEEP_BARE = {"정신보건사회복지사", "위생사"}

# passon 검증(2026-09-30)에서 폐지/통합 또는 원본 중복으로 판정된 자격임
CERT_DROP = {
    "일반경비지도사", "기계경비지도사", "일반행정사", "외국어번역행정사", "해사행정사",
    "전기기기산업기사", "목재창호기능사", "공구제작기능사보", "사출금형기능사보", "프레스금형기능사보",
    "메카트로닉스기능사", "메카트로닉스산업기사", "제판기사", "전자회로설계산업기사",
    "아스팔트피니셔운전기능사", "모터그레이더운전기능사", "농림토양평가관리기사", "농림토양평가관리산업기사",
    "목질재료기능사", "한복산업기사", "어병기사", "철도동력차전기정비산업기사", "철도동력차기관정비산업기사",
    "객화차정비산업기사", "광산차량기계운전기능사", "광산보안기능사(화약분야)", "광산환경기능사",
}

# 접미사 규칙보다 우선 적용함. 기사/기능사로 끝나더라도 산업인력공단 소관이 아닌 국가기술자격이 있음
ORG_BY_PREFIX = {
    "요양보호사": "한국보건의료인국가시험원",
    "간호조무사": "한국보건의료인국가시험원",
    "원자력기사": "한국원자력안전기술원",
    "원자력발전기술사": "한국원자력안전기술원",
    "방사선관리기술사": "한국원자력안전기술원",
    "방사선취급": "한국원자력안전기술원",
    "방사성동위원소": "한국원자력안전기술원",
    "핵연료물질": "한국원자력안전기술원",
    "핵원료물질": "한국원자력안전기술원",
    "원자로조종": "한국원자력안전기술원",
    "서비스경험디자인기사": "한국디자인진흥원",
    "KBS한국어": "KBS한국어진흥원",
    "국가유산수리": "한국산업인력공단",
    "매경부동산자산관리사": "한국부동산자산관리사협회",
    "세무회계": "한국세무사회",
    "청소년상담사": "한국산업인력공단",
    "청소년지도사": "한국산업인력공단",
    "경비지도사": "한국산업인력공단",
    "행정사": "한국산업인력공단",
    "정보보안": "한국방송통신전파진흥원",
    "빅데이터분석기사": "한국데이터산업진흥원",
    "정보통신": "한국방송통신전파진흥원",
    "무선설비": "한국방송통신전파진흥원",
    "방송통신": "한국방송통신전파진흥원",
    "전파전자통신": "한국방송통신전파진흥원",
    "통신선로": "한국방송통신전파진흥원",
    "통신기기": "한국방송통신전파진흥원",
    "통신설비기능장": "한국방송통신전파진흥원",
    "아마추어무선기사": "한국방송통신전파진흥원",
    "항공무선통신사": "한국방송통신전파진흥원",
    "해상무선통신사": "한국방송통신전파진흥원",
    "육상무선통신사": "한국방송통신전파진흥원",
    "제한무선통신사": "한국방송통신전파진흥원",
    "무선통신사": "한국방송통신전파진흥원",
    "광산보안": "한국광해광업공단",
    "광해방지": "한국광해광업공단",
    "자원관리기술사": "한국광해광업공단",
    "시추기능사": "한국광해광업공단",
    "영사": "영화진흥위원회",
    "게임기획전문가": "한국콘텐츠진흥원",
    "게임그래픽전문가": "한국콘텐츠진흥원",
    "게임프로그래밍전문가": "한국콘텐츠진흥원",
}


# 국가자격코드에 기관 정보가 없던 자격임(교원, 해기사, 의료면허 등). 출처 조사 결과를 반영함 (2026-09-30)
with open(os.path.join(ROOT, "scripts", "cert_org_fill.json"), encoding="utf-8") as f:
    ORG_FILL = json.load(f)


def fill_org(name):
    if name in ORG_FILL["exact"]:
        return ORG_FILL["exact"][name]
    for pre, org in ORG_FILL["prefix"].items():
        if name.startswith(pre):
            return org
    return ""


def prefix_org(name):
    for pre, org in ORG_BY_PREFIX.items():
        if name.startswith(pre):
            return org
    return ""


def tidy_certs(certs):
    normalized = []
    for c in certs:
        if not c["name"].strip() or c["name"] in CERT_DROP:
            continue
        name = normalize_grade(c["name"])
        for old, new in CERT_RENAMED.items():
            if name.startswith(old):
                name = new + name[len(old):]
        org = prefix_org(name) or c["org"] or fill_org(name)
        normalized.append({"name": name, "org": org})

    by_key = {}
    order = []
    for c in normalized:
        key = cert_key(c["name"])
        if key not in by_key:
            by_key[key] = c
            order.append(key)
        elif not by_key[key]["org"] and c["org"]:
            by_key[key] = c
    deduped = [by_key[k] for k in order]

    graded_bases = set()
    for c in deduped:
        m = re.match(r"^(.+) \d+급$", c["name"])
        if m:
            graded_bases.add(m.group(1))

    result = [
        c for c in deduped
        if c["name"] not in graded_bases or c["name"] in TIDY_KEEP_BARE
    ]
    for c in result:
        if c["name"].startswith(OLD_CERT_PREFIXES) and not c["name"].endswith("(구)"):
            c["name"] += " (구)"
    return result


# 검증 목록 중 wone에 다른 표기로 이미 등록된 항목임. 면허시험 표기는 시험명이므로 별도로 제외함
VERIFIED_SKIP = {
    "GTQ(그래픽스기술자격)", "정보기술자격(ITQ)", "HSK IBT", "HSK PBT", "JLPT 일본어능력시험",
    "TOEFL iBT", "한국실용글쓰기", "국가유산수리기능자", "국가유산수리기술자", "산업보건지도사", "세무회계",
}


def clean_org(org):
    org = org or ""
    if org.startswith("KCA"):
        return "한국방송통신전파진흥원"
    if org == "한국보건의료인국가시험":
        return "한국보건의료인국가시험원"
    org = re.sub(r"\((사|사단|재|주)\)|사단법인|재단법인|주식회사", "", org)
    org = re.sub(r"\((KPC|KAIT|ACIIA)\)", "", org)
    m = re.match(r"^([A-Za-z0-9 .&-]+?) \(([A-Za-z0-9 .,&'-]+)\)$", org.strip())
    if m:
        head, inner = m.groups()
        org = head if head.replace(" ", "").isupper() else inner
    return re.sub(r"\s+", " ", org).strip()


def merge_verified(certs):
    with open(VERIFIED_PATH, encoding="utf-8") as f:
        verified = json.load(f)
    by_key = {cert_key(normalize_grade(c["name"])): c for c in certs}
    for v in verified:
        if v["name"] in VERIFIED_SKIP or v["name"].split("(")[0].endswith("면허시험"):
            continue
        name = normalize_grade(re.sub(r"(\S)(\d+급)$", r"\1 \2", v["name"]))
        org = clean_org(v["agency"])
        cur = by_key.get(cert_key(name))
        if cur is None:
            c = {"name": name, "org": org}
            certs.append(c)
            by_key[cert_key(name)] = c
        elif not cur["org"]:
            cur["org"] = org
    return certs


def build_certs():
    with open(CODES_PATH, encoding="utf-8") as f:
        codes = json.load(f)
    qnet_raw = fetch_qnet_names()
    qnet_names = {norm_qnet(n) for n in qnet_raw}

    certs = []
    seen = set()
    for row in codes:
        name = row[1]
        if name in seen:
            continue
        seen.add(name)
        certs.append({"name": name, "org": cert_org(name, qnet_names)})
    for name, org in MANUAL_CERTS:
        if name in seen:
            continue
        seen.add(name)
        certs.append({"name": name, "org": org})

    # Q넷 목록에는 있으나 위 국가자격코드/수동목록에 없는 자격임 (신설/개편 종목)
    seen_norm = {norm_qnet(n) for n in seen}
    for name in qnet_raw:
        if norm_qnet(name) in seen_norm:
            continue
        seen.add(name)
        seen_norm.add(norm_qnet(name))
        certs.append({"name": name, "org": "한국산업인력공단"})

    for name, org in INTL_CERTS:
        if name in seen:
            continue
        seen.add(name)
        certs.append({"name": name, "org": org})

    return tidy_certs(merge_verified(certs))


# data.go.kr 표준데이터 상세페이지의 파일 다운로드 버튼이 호출하는 내부 API임. 인증키는 필요하지 않음
def fetch_std_data(pk, svc_table, cols, total_count):
    params = [
        ("publicDataPk", pk),
        ("svcTableNm", svc_table),
        ("totalCount", str(total_count)),
        ("perPage", str(total_count)),
        ("page", "1"),
    ]
    for c in cols:
        params.append(("colNmList", c))
    qs = urllib.parse.urlencode(params)
    req = urllib.request.Request(
        "https://www.data.go.kr/download/standard.json?" + qs,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(req, timeout=60) as res:
        return json.load(res)


def fetch_header(pk):
    req = urllib.request.Request(
        f"https://www.data.go.kr/download/columList.json?pk={pk}&ext=CSV",
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.load(res)


def build_schools():
    schools = []
    seen = set()

    univ_header = fetch_header(UNIV_PK)
    univ_rows = fetch_std_data(UNIV_PK, UNIV_SVC_TABLE, UNIV_COLS, univ_header["totalCount"])
    for row in univ_rows:
        level = UNIV_LEVEL_MAP.get(row["UNIV_SE_NM"])
        if not level:
            continue
        name = row["SCHL_NM"].strip()
        key = (name, level)
        if not name or key in seen:
            continue
        seen.add(key)
        schools.append({"name": name, "level": level})

    hs_header = fetch_header(HS_PK)
    hs_rows = fetch_std_data(HS_PK, HS_SVC_TABLE, HS_COLS, hs_header["totalCount"])
    for row in hs_rows:
        if row["SCHOOL_SE"] != "고등학교" or row["OPER_STTUS"] != "운영":
            continue
        name = row["SCHOOL_NM"].strip()
        key = (name, "고등학교")
        if not name or key in seen:
            continue
        seen.add(key)
        schools.append({"name": name, "level": "고등학교"})

    return schools


def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    certs = build_certs()
    with open(os.path.join(DATA_DIR, "certs.json"), "w", encoding="utf-8") as f:
        json.dump(certs, f, ensure_ascii=False, indent=2)
    print(f"certs.json: {len(certs)}건")

    schools = build_schools()
    with open(os.path.join(DATA_DIR, "schools.json"), "w", encoding="utf-8") as f:
        json.dump(schools, f, ensure_ascii=False, indent=2)
    print(f"schools.json: {len(schools)}건")


if __name__ == "__main__":
    main()

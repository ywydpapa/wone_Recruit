const test = require('node:test');
const assert = require('node:assert');
const V = require('../../static/js/voice-parse.js');

const today = new Date(2026, 8, 28);

test('호출어 미인식', () => {
    assert.strictEqual(V.stripWake('하이 리크루트 지원 현황 열어줘'), null);
    assert.strictEqual(V.stripWake('오늘 점심 뭐 먹지'), null);
});

test('금액', () => {
    assert.strictEqual(V.money('3만원'), 30000);
    assert.strictEqual(V.money('삼만원'), 30000);
    assert.strictEqual(V.money('3만 5천원'), 35000);
    assert.strictEqual(V.money('35,000원'), 35000);
    assert.strictEqual(V.money('만 이천'), 12000);
    assert.strictEqual(V.money('십만'), 100000);
    assert.strictEqual(V.money('백오십만'), 1500000);
    assert.strictEqual(V.money('1억 2천만'), 120000000);
    assert.strictEqual(V.money('스타벅스'), null);
    assert.strictEqual(V.money(''), null);
});

test('날짜', () => {
    assert.strictEqual(V.date('오늘', today), '2026-09-28');
    assert.strictEqual(V.date('어제로', today), '2026-09-27');
    assert.strictEqual(V.date('그저께', today), '2026-09-26');
    assert.strictEqual(V.date('9월 3일', today), '2026-09-03');
    assert.strictEqual(V.date('3일', today), '2026-09-03');
    assert.strictEqual(V.date('구월 십일일', today), '2026-09-11');
    assert.strictEqual(V.date('2월 30일', today), null);
    assert.strictEqual(V.date('내일', today), null);
    assert.strictEqual(V.dateText('2026-09-03'), '9월 3일');
});

test('매칭', () => {
    const menus = ['지원자 관리', '공고 검색', '지원 현황', '공고 관리'];
    assert.deepStrictEqual(V.match('지원자', menus), [0]);
    assert.deepStrictEqual(V.match('관리', menus), [0, 3]);
    assert.deepStrictEqual(V.match('지원 현황', menus, true), [2]);
    assert.deepStrictEqual(V.match('지원', menus, true), []);
    assert.deepStrictEqual(V.match('회의 비', ['소모품', '회의비']), [1]);
});

test('예 아니오', () => {
    assert.strictEqual(V.yesno('네 맞아요'), 'yes');
    assert.strictEqual(V.yesno('제출'), 'yes');
    assert.strictEqual(V.yesno('아니요'), 'no');
    assert.strictEqual(V.yesno('글쎄'), null);
});

test('명령 분류', () => {
    assert.deepStrictEqual(V.classify('그만'), { kind: 'stop' });
    assert.deepStrictEqual(V.classify('취소'), { kind: 'cancel' });
    assert.deepStrictEqual(V.classify('지금 어디야?'), { kind: 'where' });
    assert.deepStrictEqual(V.classify('화면 읽어줘'), { kind: 'read' });
    assert.deepStrictEqual(V.classify('공고 검색 열어줘'), { kind: 'nav', arg: '공고 검색' });
    assert.deepStrictEqual(V.classify('공고 검색로 가줘'), { kind: 'nav', arg: '공고 검색' });
    assert.deepStrictEqual(V.classify('임시저장 눌러줘'), { kind: 'click', arg: '임시저장' });
    assert.deepStrictEqual(V.classify('희망직무 사무보조'), { kind: 'any', arg: '희망직무 사무보조' });
});

test('라벨 값 분리', () => {
    const names = ['날짜', '금액', '희망직무', '근무지역', '메모'];
    assert.deepStrictEqual(V.splitLabel('희망직무는 사무보조', names), { idx: 2, value: '사무보조' });
    assert.deepStrictEqual(V.splitLabel('희망직무 디자인', names), { idx: 2, value: '디자인' });
    assert.deepStrictEqual(V.splitLabel('날짜 어제로 해줘', names), { idx: 0, value: '어제' });
    assert.strictEqual(V.splitLabel('지원 현황', names), null);
    assert.deepStrictEqual(V.splitLabel('메모', names), { idx: 4, value: '' });
});

test('호출어 인식', () => {
    assert.strictEqual(V.stripWake('하이원 지원 현황 열어줘'), '지원 현황 열어줘');
    assert.strictEqual(V.stripWake('하이 원, 공고 검색'), '공고 검색');
    assert.strictEqual(V.stripWake('Hi wone 지원 현황 열어줘'), '지원 현황 열어줘');
    assert.strictEqual(V.stripWake('High one 지원 현황 열어줘'), '지원 현황 열어줘');
    assert.strictEqual(V.stripWake('하이원'), '');
    assert.strictEqual(V.stripWake('오늘 점심 뭐 먹지'), null);
});

test('받아쓰기 명령', () => {
    assert.strictEqual(V.dictCmd('지우기'), 'undo');
    assert.strictEqual(V.dictCmd('방금거지워'), 'undo');
    assert.strictEqual(V.dictCmd('방금지워'), 'undo');
    assert.strictEqual(V.dictCmd('다음 칸으로'), 'next');
    assert.strictEqual(V.dictCmd('다음 칸'), 'next');
    assert.strictEqual(V.dictCmd('문장지우기'), 'sentence');
    assert.strictEqual(V.dictCmd('마지막 문장 지우기'), 'sentence');
    assert.strictEqual(V.dictCmd('전부지우기'), 'clear');
    assert.strictEqual(V.dictCmd('다 지우기'), 'clear');
    assert.strictEqual(V.dictCmd('줄바꿈'), 'newline');
    assert.strictEqual(V.dictCmd('엔터'), 'newline');
    assert.strictEqual(V.dictCmd('다음줄'), 'newline');
    assert.strictEqual(V.dictCmd('다시 읽어줘'), 'read');
    assert.strictEqual(V.dictCmd('읽어줘'), 'read');
    assert.strictEqual(V.dictCmd('전송'), 'send');
    assert.strictEqual(V.dictCmd('보내줘'), 'send');
    assert.strictEqual(V.dictCmd('보내기'), 'send');
    assert.strictEqual(V.dictCmd('제출'), 'send');
    assert.strictEqual(V.dictCmd('끝'), 'end');
    assert.strictEqual(V.dictCmd('받아쓰기끝'), 'end');
    assert.strictEqual(V.dictCmd('그만'), 'end');
    assert.strictEqual(V.dictCmd('멈춰'), 'end');
    assert.strictEqual(V.dictCmd('안녕하세요'), null);
});

test('문장부호 치환', () => {
    assert.strictEqual(V.punct('안녕 하세요 마침표 저는 학생 입니다'), '안녕 하세요. 저는 학생 입니다');
    assert.strictEqual(V.punct('정말요 물음표'), '정말요?');
    assert.strictEqual(V.punct('좋아요 느낌표 다음 문장 쉼표 이어서'), '좋아요! 다음 문장, 이어서');
    assert.strictEqual(V.punct('그냥 문장'), '그냥 문장');
});

test('마지막 문장 삭제', () => {
    assert.strictEqual(V.dropSentence('안녕하세요. 반갑습니다'), '안녕하세요.');
    assert.strictEqual(V.dropSentence('그냥한문장'), '');
    assert.strictEqual(V.dropSentence('첫줄\n둘째줄'), '첫줄\n');
    assert.strictEqual(V.dropSentence('안녕하세요. 반갑습니다   '), '안녕하세요.');
    assert.strictEqual(V.dropSentence('안녕하세요. 반갑습니다. '), '안녕하세요.');
});

test('헛소리 필터', () => {
    assert.strictEqual(V.isJunk('시청해 주셔서 감사합니다'), true);
    assert.strictEqual(V.isJunk('구독과 좋아요 부탁드려요'), true);
    assert.strictEqual(V.isJunk('좋아요와 구독 부탁드려요'), true);
    assert.strictEqual(V.isJunk('감사합니다'), false);
    assert.strictEqual(V.isJunk('네 알겠습니다'), false);
});

test('TTS 문장 분할', () => {
    assert.deepStrictEqual(V.sentences('안녕하세요. 반갑습니다!\n오늘은 맑아요'),
        ['안녕하세요.', '반갑습니다!', '오늘은 맑아요']);
    const long = 'ㄱ'.repeat(350) + '.';
    const parts = V.sentences(long);
    assert.strictEqual(parts.length, 2);
    assert.strictEqual(parts[0].length, 300);
    assert.strictEqual(parts[1].length, 51);
});

test('받아쓰기 분류', () => {
    assert.deepStrictEqual(V.classify('받아쓰기'), { kind: 'dictate', arg: '' });
    assert.deepStrictEqual(V.classify('메모 받아쓰기'), { kind: 'dictate', arg: '메모' });
});

test('연월', () => {
    assert.strictEqual(V.month('2020년 3월', today), '2020-03');
    assert.strictEqual(V.month('2020 3', today), '2020-03');
    assert.strictEqual(V.month('20년 3월', today), '2020-03');
    assert.strictEqual(V.month('40년 3월', today), '1940-03');
    assert.strictEqual(V.month('올해 3월', today), '2026-03');
    assert.strictEqual(V.month('작년 3월', today), '2025-03');
    assert.strictEqual(V.month('재작년 3월', today), '2024-03');
    assert.strictEqual(V.month('3월', today), '2026-03');
    assert.strictEqual(V.month('내일', today), null);
    assert.strictEqual(V.month('13월', today), null);
    assert.strictEqual(V.monthText('2020-03'), '2020년 3월');
});

test('행 접두어', () => {
    const sections = ['학력', '경력', '자격증', '어학', '수상/활동', '포트폴리오', '자기소개서'];
    assert.deepStrictEqual(V.rowPrefix('두 번째 경력 회사명 삼성전자', sections),
        { ord: 2, section: '경력', rest: '회사명 삼성전자' });
    assert.deepStrictEqual(V.rowPrefix('경력 2 회사명 삼성전자', sections),
        { ord: 2, section: '경력', rest: '회사명 삼성전자' });
    assert.deepStrictEqual(V.rowPrefix('첫번째 학력 학교명 서울대', sections),
        { ord: 1, section: '학력', rest: '학교명 서울대' });
    assert.deepStrictEqual(V.rowPrefix('3번째 경력 회사명 엘지', sections),
        { ord: 3, section: '경력', rest: '회사명 엘지' });
    assert.strictEqual(V.rowPrefix('회사명 삼성전자', sections), null);
    assert.strictEqual(V.rowPrefix('경력 회사명 삼성전자', sections), null);
});

test('이력서 경력 문장', () => {
    const r = V.resumeRow('car', '2019년 3월부터 2022년 2월까지 한빛테크에서 사무보조', today);
    assert.deepStrictEqual(r, { start: '2019-03', end: '2022-02', current: false, company: '한빛테크', dept: '', position: '', emp: '', desc: '사무보조' });
    const r2 = V.resumeRow('car', '21년 5월부터 현재까지 주식회사 다온에서 총무팀 대리로 정규직 근무하고 있어요.', today);
    assert.strictEqual(r2.start, '2021-05');
    assert.strictEqual(r2.end, '');
    assert.strictEqual(r2.current, true);
    assert.strictEqual(r2.company, '주식회사 다온');
    assert.strictEqual(r2.dept, '총무팀');
    assert.strictEqual(r2.position, '대리');
    assert.strictEqual(r2.emp, '정규직');
    const r3 = V.resumeRow('car', '이천이십년 삼월부터 이천이십일년 이월까지 물류센터에서 상품 포장 업무를 했습니다', today);
    assert.strictEqual(r3.start, '2020-03');
    assert.strictEqual(r3.end, '2021-02');
    assert.strictEqual(r3.company, '물류센터');
    assert.strictEqual(r3.desc, '상품 포장 업무');
    assert.strictEqual(V.resumeRow('car', '2018.4 ~ 2019.12 모바일앱 개발', today).desc, '개발');
});

test('이력서 학력 문장', () => {
    const r = V.resumeRow('edu', '2015년 3월부터 2019년 2월까지 한빛대학교 경영학과 졸업했어요', today);
    assert.deepStrictEqual(r, { start: '2015-03', end: '2019-02', school: '한빛대학교', major: '경영학과', level: '대학교(4년)', status: '졸업' });
    const r2 = V.resumeRow('edu', '2016년 한빛고등학교 졸업', today);
    assert.strictEqual(r2.start, '2016-03');
    assert.strictEqual(r2.school, '한빛고등학교');
    assert.strictEqual(r2.level, '고등학교');
    assert.strictEqual(r2.major, '');
    const r3 = V.resumeRow('edu', '한빛대학원 사회복지학 전공 재학중', today);
    assert.strictEqual(r3.major, '사회복지학');
    assert.strictEqual(r3.status, '재학');
    assert.strictEqual(r3.level, '대학원(석사)');
});

test('이력서 자격증 문장', () => {
    assert.deepStrictEqual(V.resumeRow('cert', '2020년 5월에 정보처리기사 자격증을 취득했어요', today), { date: '2020-05', name: '정보처리기사' });
    assert.deepStrictEqual(V.resumeRow('cert', '컴퓨터활용능력 2급 2021년 11월 합격', today), { date: '2021-11', name: '컴퓨터활용능력 2급' });
    assert.deepStrictEqual(V.resumeRow('cert', '워드프로세서', today), { date: '', name: '워드프로세서' });
    assert.deepStrictEqual(V.resumeRow('cert', '2020년 5월의 정보처리기사 취득.', today), { date: '2020-05', name: '정보처리기사' });
    assert.strictEqual(V.resumeRow('cert', '컴퓨터 활용능력이급.', today).name, '컴퓨터 활용능력2급');
});

test('화면 이동 별칭', () => {
    const cases = {
        '채용정보로 가줘': '채용정보', '공고 보여줘': '채용정보', '일자리 찾기': '채용정보', '채용공고 열어 주세요': '채용정보',
        '이력서 작성하기': '이력서 작성', '이력서 쓰기': '이력서 작성', '새 이력서': '이력서 작성',
        '내 이력서': '이력서 관리', '이력서 보여줘': '이력서 관리',
        '지원 내역 보여줘': '지원 현황', '면접 일정': '내 일정', '찜한 공고': '저장 공고',
        '메인으로 가줘': '홈', '처음 화면': '홈', '마이페이지': '계정', '쪽지함으로': null,
        '오늘 날씨': null,
    };
    for (const [said, want] of Object.entries(cases)) assert.strictEqual(V.navAlias(said), want, said);
});

test('조사, 동사 떼고 같은 말', () => {
    assert.strictEqual(V.key('지원하기'), V.key('지원해줘'));
    assert.strictEqual(V.key('채용정보로 이동해줘'), V.key('채용정보'));
    assert.strictEqual(V.key('알림 설정 화면으로 가기'), V.key('알림 설정'));
    assert.strictEqual(V.key('보기'), '보기');
    assert.deepStrictEqual(V.match('문의해줘', ['문의하기', '메시지'], true), [0]);
});

test('공통 명령', () => {
    const cases = {
        '뒤로 가기': ['back'], '이전 화면으로': ['back'], '돌아가': ['back'],
        '다음 페이지': ['page', 'next'], '이전 페이지로 가줘': ['page', 'prev'],
        '아래로': ['scroll', 'down'], '스크롤 내려줘': ['scroll', 'down'], '위로 올려줘': ['scroll', 'up'],
        '맨 위로': ['scroll', 'top'], '맨 아래로 가줘': ['scroll', 'bottom'],
        '새로고침': ['reload'], '로그아웃 해줘': ['logout'], '도움말': ['help'], '뭐라고 말해야 돼': ['help'],
        '사무직 검색해줘': ['search', '사무직'], '사무직 공고 찾아줘': ['search', '사무직'], '바리스타를 검색': ['search', '바리스타'],
        '화면 읽어줘': ['read'], '화면을 읽어 줘': ['read'], '지금 어디야': ['where'],
    };
    for (const [said, [kind, arg]] of Object.entries(cases)) {
        const c = V.classify(said);
        assert.strictEqual(c.kind, kind, said);
        if (arg) assert.strictEqual(c.arg, arg, said);
    }
});

test('받아쓰기 중 명령 구분', () => {
    for (const t of ['이력서 저장하기', '두번째 항목 작성', '뒤로 가기', '다음 페이지', '채용정보 열어줘', '지원동기 저장해줘', '아래로']) {
        assert.ok(V.cmdLike(t), t);
    }
    for (const t of ['저는 일을 안하고 돈을 많이 벌고 싶습니다.', '그것이 이 회사에 지원한 동기입니다.',
        '꾸준히 노력하는 사람입니다', '고객 응대 업무를 맡았습니다', '화면 읽어줘']) {
        assert.ok(!V.cmdLike(t), t);
    }
});

test('받아쓰기 고치기', () => {
    const cases = {
        '삭제': 'undo', '삭제하기': 'undo', '지워줘': 'undo', '방금 거 삭제해줘': 'undo',
        '마지막 문장 삭제': 'sentence', '문장 지워줘': 'sentence',
        '전부 삭제해줘': 'clear', '모두 지워': 'clear',
        '수정하기': 'fix', '고쳐줘': 'fix', '다시': 'fix', '다시 말할게': 'fix', '틀렸어': 'fix',
    };
    for (const [said, want] of Object.entries(cases)) assert.strictEqual(V.dictCmd(said), want, said);
    assert.deepStrictEqual(V.replaceCmd('돈을 일로 바꿔줘'), { from: '돈', to: '일' });
    assert.deepStrictEqual(V.replaceCmd('많이 벌고를 적게 벌고로 고쳐줘.'), { from: '많이 벌고', to: '적게 벌고' });
    assert.strictEqual(V.replaceCmd('저는 일을 열심히 했습니다'), null);
    assert.ok(V.cmdLike('지원동기 삭제'));
    assert.ok(V.cmdLike('지원동기 수정해줘'));
});

test('음성 끄기', () => {
    for (const t of ['음성 꺼', '음성 꺼줘', '듣기 그만', '마이크 꺼', '항상 듣기 꺼줘']) assert.strictEqual(V.classify(t).kind, 'voiceoff', t);
    assert.strictEqual(V.classify('그만').kind, 'stop');
});

test('지원하기', () => {
    for (const t of ['지원하기', '지원할래', '지원해줘', '이 공고 지원하기', '여기 지원할게요']) assert.strictEqual(V.classify(t).kind, 'apply', t);
    assert.strictEqual(V.classify('지원 현황').kind, 'any');
    const labels = ['지원 현황', '지원동기 작성', '이력서 작성'];
    assert.deepStrictEqual(V.match('지원하기', labels), [0]);
    assert.deepStrictEqual(V.match('이력서 작성해줘', labels), [2]);
});

test('조사', () => {
    assert.strictEqual(V.josa('경력', '을', '를'), '경력을');
    assert.strictEqual(V.josa('자기소개서', '을', '를'), '자기소개서를');
    assert.strictEqual(V.josa('지원동기', '은', '는'), '지원동기는');
    assert.strictEqual(V.josa('서울', '으로', '로'), '서울로');
    assert.strictEqual(V.josa('사무직', '으로', '로'), '사무직으로');
});

test('호출어 오인식', () => {
    assert.strictEqual(V.stripWake('하의원 이력서 작성하기'), '이력서 작성하기');
    assert.strictEqual(V.stripWake('아이원 채용정보'), '채용정보');
    assert.strictEqual(V.stripWake('이력서 작성하기'), null);
});

test('입력칸 말하기', () => {
    const names = ['회사명', '부서', '직책/직위', '직책', '직위', '입사일'];
    const cases = {
        '부서': [1, ''], '부서 입력': [1, ''], '부서입력': [1, ''], '부서 입력해줘': [1, ''], '부서 칸': [1, ''],
        '부서는 인사': [1, '인사'], '부서: 양산기술': [1, '양산기술'], '부서 프로': [1, '프로'],
        '회사명은 삼성전자로 해줘': [0, '삼성전자'], '회사명 삼성전자로 입력해줘': [0, '삼성전자'],
        '직책 책임으로': [3, '책임'], '직책책임': [3, '책임'], '입사일 2019년 3월': [5, '2019년 3월'],
    };
    for (const [said, [idx, value]] of Object.entries(cases)) assert.deepStrictEqual(V.splitLabel(said, names), { idx, value }, said);
    assert.strictEqual(V.valueText('삼성전자로 입력해줘'), '삼성전자');
    assert.strictEqual(V.valueText('동해'), '동해');
    assert.strictEqual(V.valueText('입력'), '');
    assert.deepStrictEqual(V.splitLabel('회사명, 서울우유.', names), { idx: 0, value: '서울우유' });
    assert.deepStrictEqual(V.splitLabel('회사명 입력하기', names), { idx: 0, value: '' });
    assert.ok(V.isJunk('외자구매, 외자구매, 등으로 등으로 등으로 등으로.'));
    assert.ok(!V.isJunk('회사명 삼다수'));
});

test('목록 칸 보정', () => {
    const titles = ['사원', '대리', '과장', '차장', '부장', '선임', '책임', '수석', '팀장', '파트장', 'TL', 'PM'];
    const titleCases = { 화장: '과장', 사님: '선임', 채김: '책임', 수성: '수석', 팀짱: '팀장', 대리님: '대리', 티엘: 'TL', tl: 'TL', 파트장: '파트장' };
    for (const [said, want] of Object.entries(titleCases)) assert.strictEqual(V.closest(said, titles), want, said);
    assert.strictEqual(V.closest('삼성전자', titles), '삼성전자');

    const depts = ['인사', 'HR', 'HRD', '외자구매', '정보보안', '양산기술', 'MLCC', 'NAND', 'eSSD'];
    const deptCases = { 의자구매: '외자구매', 엠엘씨씨: 'MLCC', 에이치알디: 'HRD', 이에스에스디: 'eSSD', 정보보완: '정보보안', 양산기술: '양산기술' };
    for (const [said, want] of Object.entries(deptCases)) assert.strictEqual(V.closest(said, depts), want, said);
    for (const t of ['인사팀', '메모리사업부', '반도체연구소']) assert.strictEqual(V.closest(t, depts), t, t);
});

test('URL 발음 변환', () => {
    const cases = {
        '깃허브 닷컴 슬래시 에이치 오 엔 지': 'https://github.com/hong',
        'github.com/hong': 'https://github.com/hong',
        '에이치티티피에스 콜론 슬래시 슬래시 노션 점 에스 오': 'https://notion.so',
        '블로그 점 네이버 닷컴 슬래시 케이 아이 엠 언더바 1': 'https://blog.naver.com/kim_1',
        '에이치티티피에스 깃허브 닷컴': 'https://github.com',
        '벨로그 점 아이 오 슬래시 골뱅이 디 이 브이': 'https://velog.io/@dev',
    };
    for (const [said, want] of Object.entries(cases)) assert.strictEqual(V.url(said), want, said);
    for (const t of ['깃허브 닷컴 슬래시 홍길동', '깃허브', '']) assert.strictEqual(V.url(t), null, t);
});

test('어학 한 문장 입력', () => {
    const t = new Date(2026, 9, 7);
    const row = s => V.resumeRow('lang', s, t);
    assert.deepStrictEqual(row('토익 890 24년1월'), { language: '영어', test: 'TOEIC', score: '890', level: '', date: '2024-01' });
    assert.deepStrictEqual(row('JLPT N2 작년 7월'), { language: '일본어', test: 'JLPT', score: 'N2', level: '', date: '2025-07' });
    assert.deepStrictEqual(row('오픽 IH 비즈니스'), { language: '영어', test: 'OPIc', score: 'IH', level: '비즈니스', date: '' });
    assert.deepStrictEqual(row('스페인어 델레 B2'), { language: '스페인어', test: 'DELE', score: 'B2', level: '', date: '' });
    assert.strictEqual(row('HSK 5급').score, '5급');
});

test('행 입력 상대 연도', () => {
    const t = new Date(2026, 9, 7);
    assert.deepStrictEqual(V.resumeRow('cert', '정보처리기사 작년 7월', t), { date: '2025-07', name: '정보처리기사' });
    assert.strictEqual(V.resumeRow('car', '삼성전자 올해 3월부터 재직중', t).start, '2026-03');
});

test('부서 오인식 보정', () => {
    const depts = ['인사', '인사총무', '총무', '재무', '회계', '경영지원', '기획', '전략기획', '경영기획', '사업기획',
        '영업', '국내영업', '해외영업', '기술영업', '영업관리', '마케팅', '구매', '외자구매', '자재', '물류', '물류관리',
        '생산', '생산관리', '품질', '품질관리', '고객지원'];
    const cases = { 해외용업: '해외영업', 국내용업: '국내영업', 구메: '구매', 전략기혹: '전략기획', 경영지언: '경영지원',
        생산관니: '생산관리', 물뉴: '물류', 자제: '자재', 회개: '회계', 마캐팅: '마케팅' };
    for (const [said, want] of Object.entries(cases)) assert.strictEqual(V.closest(said, depts), want, said);
    for (const t of ['인사팀', '영업2팀', '메모리사업부']) assert.strictEqual(V.closest(t, depts), t, t);
});

test('상담 신청 명령', () => {
    assert.deepStrictEqual(V.consultCmd('채용매니저한테 상담신청해줘'), { category: '', method: '' });
    assert.deepStrictEqual(V.consultCmd('보조기기 상담 전화로 신청할래'), { category: 'device', method: 'phone' });
    assert.deepStrictEqual(V.consultCmd('메시지로 상담 신청해줘'), { category: '', method: 'chat' });
    assert.deepStrictEqual(V.consultCmd('면접 상담 받고 싶어요'), { category: 'job', method: '' });
    assert.strictEqual(V.consultCmd('상담 신청 내역 보여줘'), null);
    assert.strictEqual(V.consultCmd('상담 취소해줘'), null);
    assert.strictEqual(V.consultCmd('상담 열어줘'), null);
});

test('상담 슬롯 답변', () => {
    assert.strictEqual(V.consultCat('근무 중 어려움이요'), 'work');
    assert.strictEqual(V.consultCat('차별 받은 거요'), 'rights');
    assert.strictEqual(V.consultCat('글쎄요'), '');
    assert.strictEqual(V.consultMethod('화상으로 할게요'), 'video');
    assert.strictEqual(V.consultMethod('직접 만나서요'), 'in_person');
    assert.strictEqual(V.consultMethod('문자로'), 'chat');
});

test('메시지 명령', () => {
    assert.deepStrictEqual(V.messageCmd('채용매니저한테 메시지 보내줘'), { other: false });
    assert.deepStrictEqual(V.messageCmd('메시지 보내줘'), { other: false });
    assert.deepStrictEqual(V.messageCmd('담당자에게 문자 남길래'), { other: false });
    assert.deepStrictEqual(V.messageCmd('김철수한테 메시지 보내줘'), { other: true });
    assert.strictEqual(V.messageCmd('메시지 열어줘'), null);
    assert.strictEqual(V.messageCmd('메시지로 상담 신청해줘'), null);
});

test('이력서 항목 불러오기', () => {
    assert.deepStrictEqual(V.importCmd('예전 이력서 경력 불러와서 넣어줘'), { sec: 'career' });
    assert.deepStrictEqual(V.importCmd('예전 이력서 경력 불러와줘'), { sec: 'career' });
    assert.deepStrictEqual(V.importCmd('다른 이력서에서 자격증 가져와줘'), { sec: 'cert' });
    assert.deepStrictEqual(V.importCmd('외국어 불러와'), { sec: 'lang' });
    assert.deepStrictEqual(V.importCmd('봉사활동 가져와 줘'), { sec: 'award' });
    assert.deepStrictEqual(V.importCmd('예전 이력서 불러와줘'), { sec: '' });
    assert.strictEqual(V.importCmd('경력 추가'), null);
    assert.strictEqual(V.importSec('학력이요'), 'education');
});

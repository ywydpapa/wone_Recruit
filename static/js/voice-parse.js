(function(root) {
    // 호출어(하이원) 목록임. 오인식 표기를 포함함
    const WAKE = ['하이원', 'hiwone', 'highone', '하이won', '하이원아', '하의원', '아이원', '하이웜'];
    const PUNCT = /[\s.,!?]/;
    const DIGIT = { 영: 0, 공: 0, 일: 1, 이: 2, 삼: 3, 사: 4, 오: 5, 육: 6, 칠: 7, 팔: 8, 구: 9 };
    const SMALL = { 십: 10, 백: 100, 천: 1000 };
    const BIG = { 만: 10000, 억: 100000000 };
    const REL = { 오늘: 0, 어제: 1, 그제: 2, 그저께: 2 };
    const KNUM = '[0-9영공일이삼사오육칠팔구십]+';
    const MD = new RegExp('^(?:(' + KNUM + ')월)?(' + KNUM + ')일$');
    const YM = new RegExp('^(?:(' + KNUM + ')년)?(' + KNUM + ')월$');
    const YREL = { 올해: 0, 작년: 1, 재작년: 2 };
    const ORD = { 첫: 1, 한: 1, 하나: 1, 두: 2, 둘: 2, 세: 3, 셋: 3, 네: 4, 넷: 4, 다섯: 5 };
    const CLICK_TAIL = /\s*(을|를)?\s*(눌러\s*줘|눌러\s*주세요|눌러|클릭\s*해\s*줘|클릭)$/;
    const NAV_TAIL = /\s*(으로|로|을|를)?\s*(열어\s*줘|열어\s*주세요|열어|가\s*줘|가자|이동\s*해\s*줘|이동|보여\s*줘|화면)$/;
    const DICT_CMD = {
        undo: ['지우기', '지워', '방금거지워', '방금지워', '삭제', '방금거삭제', '방금삭제', '되돌려', '실행취소'],
        sentence: ['마지막문장지우기', '문장지우기', '마지막문장지워', '문장지워', '문장삭제', '마지막문장삭제'],
        clear: ['전부지우기', '다지우기', '전부지워', '다지워', '모두지워', '전부삭제', '다삭제', '모두삭제', '전체삭제'],
        fix: ['수정', '고쳐', '다시', '다시말할게', '다시쓰기', '마지막문장수정', '마지막문장다시', '틀렸어', '잘못됐어'],
        newline: ['줄바꿈', '엔터', '다음줄'],
        next: ['다음칸', '다음칸으로', '다음칸으로가', '다음입력칸'],
        read: ['다시읽어', '읽어'],
        send: ['전송', '보내기', '보내', '제출'],
        end: ['끝', '받아쓰기끝', '그만', '멈춰'],
    };
    const DICT_TAIL = /(해줘|해주세요|하기|해|줘)$/;
    // 받아쓰기 중 짧은 지시를 판별함. 자소서 문장은 대체로 길고 ~습니다로 끝남
    const CMD_LIKE = /(해줘|해주세요|하기|작성|저장|삭제|지워|수정|고쳐|바꿔|눌러줘|눌러|열어줘|열어|이동해줘|이동|가기|가줘|보여줘|검색|찾아줘)$/;
    // 끝의 조사와 동사를 제거한 후 비교함
    const KEY_TAIL = /(으로|로|을|를|에|좀)?(화면|페이지|메뉴)?(으로|로|을|를|에)?(가줘|가자|가기|가|이동해줘|이동|열어줘|열어주세요|열어|보여줘|보여주세요|보기|볼래|들어가줘|들어가|해줘|해주세요|하기|할래|해|줘|주세요)$/;
    // 메뉴명 대신 흔히 쓰는 표현임. 화면에 해당 메뉴가 있을 때만 적용함
    const NAV_ALIAS = {
        '홈': ['메인', '처음', '처음화면', '대시보드', '첫화면'],
        '채용정보': ['채용공고', '공고', '공고목록', '일자리', '일자리찾기', '일자리목록', '구인', '채용', '일거리'],
        '커뮤니티': ['게시판', '자유게시판'],
        '공지사항': ['공지'],
        '전체 현황': ['신청현황', '현황', '전체현황'],
        '지원 현황': ['지원내역', '지원한공고', '내지원', '지원목록', '지원한곳'],
        '받은 제안': ['제안', '스카우트', '받은제안'],
        '내 일정': ['일정', '면접일정', '스케줄', '달력', '캘린더'],
        '상담': ['상담신청', '상담사', '상담내역'],
        '내 프로필': ['프로필', '내정보수정'],
        '이력서 관리': ['이력서목록', '내이력서', '이력서', '이력서보기'],
        '이력서 작성': ['이력서쓰기', '이력서작성'],
        '열람 현황': ['열람', '누가봤어', '이력서열람'],
        '저장 공고': ['관심공고', '찜', '찜한공고', '스크랩', '북마크'],
        '최근 본 공고': ['최근공고', '최근본거', '최근본공고'],
        '메시지': ['쪽지', '메세지', '받은메시지'],
        '문의하기': ['문의', '질문', '1대1문의'],
        '계정': ['내정보', '마이페이지', '계정설정', '회원정보'],
        '개인정보': ['개인정보동의', '동의'],
        '접근성': ['접근성설정', '보조기능'],
        '알림 설정': ['알림설정'],
        '알림': ['알림목록', '새소식'],
        '메시지 양식': ['양식', '양식관리', '제안양식', '메시지양식관리'],
    };
    // 알파벳 발음표임. 긴 발음부터 비교함
    const LETTERS = [['더블유', 'W'], ['에이치', 'H'], ['에이', 'A'], ['에프', 'F'], ['에스', 'S'], ['엑스', 'X'],
        ['와이', 'Y'], ['제트', 'Z'], ['브이', 'V'], ['케이', 'K'], ['제이', 'J'], ['아이', 'I'], ['엘', 'L'], ['엠', 'M'],
        ['엔', 'N'], ['알', 'R'], ['큐', 'Q'], ['비', 'B'], ['씨', 'C'], ['디', 'D'], ['이', 'E'], ['지', 'G'], ['오', 'O'],
        ['피', 'P'], ['티', 'T'], ['유', 'U'], ['앤', '&']];
    // 긴 발음부터 비교함
    const URL_WORDS = [['에이치티티피에스', 'https'], ['에이치티티피', 'http'], ['깃허브', 'github'], ['깃헙', 'github'],
        ['티스토리', 'tistory'], ['벨로그', 'velog'], ['노션', 'notion'], ['네이버', 'naver'], ['블로그', 'blog'], ['닷컴', '.com'],
        ['슬래시', '/'], ['슬러시', '/'], ['언더바', '_'], ['하이픈', '-'], ['골뱅이', '@'], ['콜론', ':'], ['대시', '-'], ['닷', '.'],
        ['쩜', '.'], ['점', '.']];
    const PUNCT_WORD = { 마침표: '.', 온점: '.', 쉼표: ',', 콤마: ',', 물음표: '?', 느낌표: '!' };
    const JUNK = ['시청해주셔서감사합니다', '구독과좋아요', '좋아요와구독', '알림설정', 'mbc뉴스'];

    function squash(s) {
        return s.replace(/[\s.,!?]/g, '').toLowerCase();
    }

    // 공백과 문장부호를 제외하고 앞에서 n글자를 제거함
    function dropChars(raw, n) {
        let i = 0;
        while (n > 0 && i < raw.length) {
            if (!PUNCT.test(raw[i])) n--;
            i++;
        }
        return raw.slice(i).replace(/^[\s.,!?]+/, '').trim();
    }

    function stripWake(text) {
        const flat = squash(text);
        const w = WAKE.find(k => flat.startsWith(k));
        return w ? dropChars(text.trim(), w.length) : null;
    }

    function money(text) {
        const s = text.replace(/[\s,원]/g, '');
        if (!/^[0-9영공일이삼사오육칠팔구십백천만억]+$/.test(s)) return null;
        let total = 0, sect = 0, num = null;
        for (let i = 0; i < s.length; i++) {
            const c = s[i];
            if (/[0-9]/.test(c)) {
                let j = i;
                while (j < s.length && /[0-9]/.test(s[j])) j++;
                num = Number(s.slice(i, j));
                i = j - 1;
            } else if (c in DIGIT) {
                num = DIGIT[c];
            } else if (c in SMALL) {
                sect += (num === null ? 1 : num) * SMALL[c];
                num = null;
            } else {
                sect += num === null ? 0 : num;
                total += (sect || 1) * BIG[c];
                sect = 0;
                num = null;
            }
        }
        total += sect + (num === null ? 0 : num);
        return total > 0 ? total : null;
    }

    function ymd(d) {
        return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
    }

    function dateText(s) {
        return Number(s.slice(5, 7)) + '월 ' + Number(s.slice(8, 10)) + '일';
    }

    function date(text, today) {
        const s = squash(text).replace(/(으로|로|이요|요)$/, '');
        if (s in REL) {
            const d = new Date(today);
            d.setDate(d.getDate() - REL[s]);
            return ymd(d);
        }
        const m = s.match(MD);
        if (!m) return null;
        const mon = m[1] ? money(m[1]) : today.getMonth() + 1;
        const day = money(m[2]);
        const d = new Date(today.getFullYear(), mon - 1, day);
        return d.getMonth() === mon - 1 && d.getDate() === day ? ymd(d) : null;
    }

    function ym(y, m) {
        return y + '-' + String(m).padStart(2, '0');
    }

    function monthText(s) {
        return Number(s.slice(0, 4)) + '년 ' + Number(s.slice(5, 7)) + '월';
    }

    function month(text, today) {
        const raw = text.trim();
        const yearNow = today.getFullYear();
        const bare = raw.match(/^([0-9]{4})\s+([0-9]{1,2})$/);
        if (bare) {
            const mon = Number(bare[2]);
            return mon >= 1 && mon <= 12 ? ym(Number(bare[1]), mon) : null;
        }
        const s = squash(raw).replace(/(으로|로|이요|요)$/, '');
        for (const k in YREL) {
            if (!s.startsWith(k)) continue;
            const mm = s.slice(k.length).match(new RegExp('^(' + KNUM + ')월$'));
            if (!mm) return null;
            const mon = money(mm[1]);
            return mon >= 1 && mon <= 12 ? ym(yearNow - YREL[k], mon) : null;
        }
        const m = s.match(YM);
        if (!m) return null;
        const mon = money(m[2]);
        if (!mon || mon < 1 || mon > 12) return null;
        if (!m[1]) return ym(yearNow, mon);
        if (/^[0-9]{1,2}$/.test(m[1])) {
            const yy = yearNow % 100;
            const yraw = Number(m[1]);
            return ym(yraw <= yy ? 2000 + yraw : 1900 + yraw, mon);
        }
        return ym(money(m[1]), mon);
    }

    function parseOrd(s) {
        for (const k in ORD) {
            if (s.startsWith(k)) {
                const rest = s.slice(k.length).replace(/^\s+/, '').replace(/^번째\s*/, '');
                return [ORD[k], rest];
            }
        }
        const m = s.match(/^([0-9]+)\s*번째\s*/);
        return m ? [Number(m[1]), s.slice(m[0].length)] : null;
    }

    // 앞부분의 서수와 섹션명을 제거함
    function rowPrefix(text, sections) {
        const s = text.trim();
        const o = parseOrd(s);
        if (o) {
            const rest = o[1].replace(/^\s+/, '');
            for (const sec of sections) {
                if (rest.startsWith(sec)) {
                    return { ord: o[0], section: sec, rest: rest.slice(sec.length).replace(/^\s+/, '') };
                }
            }
        }
        for (const sec of sections) {
            if (!s.startsWith(sec)) continue;
            const after = s.slice(sec.length);
            const m = after.match(/^\s*([0-9]+)번?째?\s*/);
            if (m && m[1]) return { ord: Number(m[1]), section: sec, rest: after.slice(m[0].length) };
        }
        return null;
    }

    function score(q, label) {
        if (!q || !label) return 0;
        if (q === label || key(q) === key(label)) return 1000;
        if (q.includes(label) || label.includes(q)) return 100 + Math.min(q.length, label.length);
        const pool = label.split('');
        let hit = 0;
        // 동사 꼬리를 제외하고 계산함. 동사 끝 글자가 다른 메뉴명에 잘못 매칭되는 것을 방지함
        for (const c of key(q)) {
            const k = pool.indexOf(c);
            if (k >= 0) {
                hit++;
                pool.splice(k, 1);
            }
        }
        return hit >= 2 && hit * 2 >= label.length ? hit : 0;
    }

    function match(q, labels, exact) {
        const sq = squash(q);
        let best = exact ? 999 : 0;
        let idxs = [];
        labels.forEach((l, i) => {
            const sc = score(sq, squash(l));
            if (sc > best) {
                best = sc;
                idxs = [i];
            } else if (sc === best && sc > 0) {
                idxs.push(i);
            }
        });
        return idxs;
    }

    function yesno(text) {
        const s = squash(text);
        if (/^(아니|아뇨|노|싫어)/.test(s)) return 'no';
        if (/^(네|넵|예|응|맞아|그래|좋아|저장|제출)/.test(s)) return 'yes';
        return null;
    }

    function cmdLike(text) {
        const n = text.trim().split(/\s+/).length;
        if (n > 4) return false;
        return CMD_LIKE.test(squash(text)) || (n <= 3 && !['any', 'read'].includes(classify(text).kind));
    }

    // A를 B로 바꾸는 명령을 파싱함
    function replaceCmd(text) {
        const m = text.trim().replace(/[.!?]+$/, '').match(/^(.+?)\s*(을|를)\s*(.+?)\s*(으로|로)\s*(바꿔|고쳐|수정)/);
        return m ? { from: m[1], to: m[3] } : null;
    }

    function key(text) {
        const s = squash(text);
        return s.replace(KEY_TAIL, '') || s;
    }

    function navAlias(text) {
        const k = key(text);
        return Object.keys(NAV_ALIAS).find(l => key(l) === k || NAV_ALIAS[l].includes(k)) || null;
    }

    function dictCmd(text) {
        const s = squash(text).replace(DICT_TAIL, '');
        for (const k of Object.keys(DICT_CMD)) {
            if (DICT_CMD[k].includes(s)) return k;
        }
        return null;
    }

    function punct(text) {
        let out = '';
        text.split(/\s+/).filter(Boolean).forEach(w => {
            if (w in PUNCT_WORD) out += PUNCT_WORD[w];
            else out += (out ? ' ' : '') + w;
        });
        return out;
    }

    function dropSentence(text) {
        const s = text.replace(/[\s.?!]+$/, '');
        const m = s.match(/^([\s\S]*[.?!\n])[^.?!\n]*$/);
        return m ? m[1] : '';
    }

    function isJunk(text) {
        const s = squash(text);
        // 무음 구간에서 반복 출력되는 결과를 제외함
        const words = text.replace(/[.,!?]/g, ' ').split(/\s+/).filter(Boolean);
        return JUNK.some(j => s.includes(j)) || words.some(w => words.filter(x => x === w).length >= 3);
    }

    function sentences(text) {
        const out = [];
        text.split(/(?<=[.?!])|\n/).forEach(part => {
            let s = part.trim();
            while (s.length > 300) {
                out.push(s.slice(0, 300));
                s = s.slice(300);
            }
            if (s) out.push(s);
        });
        return out;
    }

    function classify(cmd) {
        const s = cmd.replace(/[.!?]+$/, '').trim();
        const f = squash(s);
        if (/^(음성|듣기|마이크|항상듣기)(꺼|끄기|끄자|그만|종료|중지)/.test(f)) return { kind: 'voiceoff' };
        if (/^(그만|멈춰|중지|스톱)/.test(f)) return { kind: 'stop' };
        if (/^취소/.test(f)) return { kind: 'cancel' };
        if (/어디야|어디예요|어디지|어디에있/.test(f)) return { kind: 'where' };
        if (/^(화면(을|를)?)?(다크|어두운|어둡게|검은)(모드|테마|화면|색)?(으로|로)?(바꿔|변경|전환|해|켜|설정)/.test(f)) return { kind: 'theme', arg: 'dark' };
        if (/^(화면(을|를)?)?(라이트|밝은|밝게|흰|하얀|일반)(모드|테마|화면|색)?(으로|로)?(바꿔|변경|전환|해|켜|설정)/.test(f)) return { kind: 'theme', arg: 'light' };
        // STT 오인식 표기(일거)를 포함함
        if (/^(화면(을|를)?)?(좀)?(읽어|일거)/.test(f)) return { kind: 'read' };
        if (/^(도움말|명령어|사용법|뭐라고말해|뭐할수있)/.test(f)) return { kind: 'help' };
        if (/^(뒤로|이전화면|전화면|돌아가)/.test(f)) return { kind: 'back' };
        if (/^새로고침/.test(f)) return { kind: 'reload' };
        if (/^로그아웃/.test(f)) return { kind: 'logout' };
        if (/^다음페이지/.test(f)) return { kind: 'page', arg: 'next' };
        if (/^(이전페이지|앞페이지)/.test(f)) return { kind: 'page', arg: 'prev' };
        if (/^(맨위|제일위|맨처음으로)/.test(f)) return { kind: 'scroll', arg: 'top' };
        if (/^(맨아래|맨밑|제일아래|맨끝)/.test(f)) return { kind: 'scroll', arg: 'bottom' };
        if (/^(아래로|밑으로|내려|스크롤내려|스크롤다운)/.test(f)) return { kind: 'scroll', arg: 'down' };
        if (/^(위로|올려|스크롤올려|스크롤업)/.test(f)) return { kind: 'scroll', arg: 'up' };
        if (/받아쓰기$/.test(s)) return { kind: 'dictate', arg: s.replace(/받아쓰기$/, '').trim() };
        if (/^(이공고에?|여기에?|이회사에?)?지원(하기|할래|할게요?|해줘|해주세요|해|신청)$/.test(f)) return { kind: 'apply' };
        if (CLICK_TAIL.test(s)) return { kind: 'click', arg: s.replace(CLICK_TAIL, '').trim() };
        if (NAV_TAIL.test(s)) return { kind: 'nav', arg: s.replace(NAV_TAIL, '').trim() };
        const sm = s.match(/^(.+?)\s*(을|를)?\s*(검색|찾아|찾기)(\s*(해|줘|주세요|봐))*$/);
        // 검색어 끝의 공고, 일자리 등은 제외함
        if (sm) return { kind: 'search', arg: sm[1].replace(/\s*(채용공고|공고|일자리|자리)$/, '').trim() || sm[1].trim() };
        return { kind: 'any', arg: s };
    }

    function splitLabel(text, names) {
        const f = squash(text);
        let idx = -1, len = 0;
        names.forEach((n, i) => {
            const sn = squash(n);
            if (sn.length > len && f.startsWith(sn)) {
                idx = i;
                len = sn.length;
            }
        });
        if (idx < 0) return null;
        // 값이 비어 있으면 라벨만 호출한 것으로 처리함
        return { idx, value: valueText(dropChars(text.trim(), len).replace(/^(은|는|을|를|이|가|에|:)\s*/, '')) };
    }

    function valueText(v) {
        const s = v.trim().replace(/[.,!?]+$/, '')
            .replace(/\s*(으로|로)\s*(해|넣어|바꿔|입력\s*해|적어|써)\s*(줘|주세요)?$/, '')
            .replace(/\s*(을|를)?\s*(입력|작성)\s*(해)?\s*(줘|주세요|하기|할게)?$/, '')
            .replace(/\s*으로$/, '')
            .trim();
        return /^(입력|작성|칸|란|쓰기|적기|선택)?$/.test(s) ? '' : s;
    }

    const CHO = 'ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ';
    const JUNG = 'ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ';
    const JONG = ['', 'ㄱ', 'ㄲ', 'ㄱㅅ', 'ㄴ', 'ㄴㅈ', 'ㄴㅎ', 'ㄷ', 'ㄹ', 'ㄹㄱ', 'ㄹㅁ', 'ㄹㅂ', 'ㄹㅅ', 'ㄹㅌ', 'ㄹㅍ', 'ㄹㅎ',
        'ㅁ', 'ㅂ', 'ㅂㅅ', 'ㅅ', 'ㅆ', 'ㅇ', 'ㅈ', 'ㅊ', 'ㅋ', 'ㅌ', 'ㅍ', 'ㅎ'];

    // 발음 비교용 자모열임. 초성 ㅇ은 제외함
    function jamo(s) {
        let out = '';
        for (const ch of s.replace(/\s/g, '').toUpperCase()) {
            const c = ch.charCodeAt(0) - 0xAC00;
            if (c < 0 || c > 11171) {
                out += ch;
                continue;
            }
            const cho = CHO[Math.floor(c / 588)];
            out += (cho === 'ㅇ' ? '' : cho) + JUNG[Math.floor(c % 588 / 28)] + JONG[c % 28];
        }
        return out;
    }

    function dist(a, b) {
        let prev = [...Array(b.length + 1).keys()];
        for (let i = 1; i <= a.length; i++) {
            const cur = [i];
            for (let j = 1; j <= b.length; j++) {
                cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
            }
            prev = cur;
        }
        return prev[b.length];
    }

    function spell(k) {
        let out = '';
        while (k) {
            const l = LETTERS.find(([r]) => k.startsWith(r));
            if (!l) return null;
            out += l[1];
            k = k.slice(l[0].length);
        }
        return out;
    }

    // 영문 주소는 알파벳 발음 기준. 한글 잔존 시 실패 처리
    function url(v) {
        let k = v.replace(/\s/g, '').toLowerCase(), out = '';
        while (k) {
            const w = URL_WORDS.find(([r]) => k.startsWith(r)) || LETTERS.find(([r]) => k.startsWith(r));
            if (w) {
                out += w[1];
                k = k.slice(w[0].length);
            } else if (/^[a-z0-9.:/_@-]/.test(k)) {
                out += k[0];
                k = k.slice(1);
            } else {
                return null;
            }
        }
        out = out.toLowerCase().replace(/^(https?):?\/*/, '$1://');
        if (!/^https?:\/\//.test(out)) out = 'https://' + out;
        return /^https?:\/\/[a-z0-9-]+(\.[a-z0-9-]+)+(\/\S*)?$/.test(out) ? out : null;
    }

    // 목록 중 발음이 가장 가까운 항목으로 보정함
    function closest(v, opts) {
        const k = squash(v).replace(/(.{2,})님$/, '$1');
        const sp = spell(k);
        const same = opts.find(o => squash(o) === k || (sp && o.toUpperCase() === sp));
        if (same) return same;
        const j = jamo(k);
        let best = v, bd = Math.max(1, Math.floor(j.length / 3)) + 1;
        for (const o of opts) {
            const d = dist(j, jamo(o));
            if (d < bd) {
                best = o;
                bd = d;
            }
        }
        return best;
    }

    // 이력서 한 문장을 파싱하여 기간, 기관명, 직무를 추출함
    const KY = '[0-9]{4}|[0-9]{2}|이천[일이삼사오육칠팔구십]*|천구백[일이삼사오육칠팔구십]*';
    const KM = '[0-9]{1,2}|십[일이]?|[일이삼사오육칠팔구]';
    const YM_RE = new RegExp('(?:(' + KY + ')\\s*년\\s*(?:(' + KM + ')\\s*월)?|([0-9]{4})\\s*[./-]\\s*([0-9]{1,2})(?![0-9])|(' + KM + ')\\s*월)', 'g');
    const STOP = new Set(['에', '의', '에서', '부터', '까지', '로', '으로', '을', '를', '은', '는', '이', '가', '~', '-', '동안', '그리고', '저는', '제가']);
    const EMP = ['정규직', '계약직', '인턴', '파견직', '프리랜서', '아르바이트'];
    const POS = ['사원', '주임', '대리', '과장', '차장', '부장', '팀장', '실장', '본부장', '이사', '대표', '매니저'];
    const GRAD = ['졸업예정', '졸업', '재학', '휴학', '중퇴', '수료'];
    const VERB_TAIL = /(^|\s+)((근무|재직|일했|다녔|다니|했|하고|있|취득|합격|땄|받았)\S*\s*)+$/;
    const NOW_RE = /(현재|지금)\s*까지|재직\s*중\S*|다니고\s*있\S*/g;

    function ymTok(y, m, defMon, today) {
        let year = today.getFullYear();
        if (/^[0-9]{2}$/.test(y)) year = (Number(y) <= year % 100 ? 2000 : 1900) + Number(y);
        else if (y) year = /^[0-9]+$/.test(y) ? Number(y) : money(y);
        const mon = m ? money(m) : defMon;
        return mon >= 1 && mon <= 12 && year > 1900 ? ym(year, mon) : '';
    }

    function period(text, today, defs) {
        const toks = [];
        let s = text;
        const current = s.search(NOW_RE) >= 0;
        s = s.replace(NOW_RE, ' ');
        s = s.replace(/(재작년|작년|올해)\s*/g, (all, w) => (today.getFullYear() - YREL[w]) + '년 ');
        s = s.replace(YM_RE, (all, y, m, ny, nm, mo) => {
            toks.push([y || ny, m || nm || mo]);
            return ' ';
        });
        s = s.replace(/[.,!?]/g, ' ');
        const [start, end] = toks.map((t, i) => ymTok(t[0], t[1], defs[i] || defs[0], today));
        s = s.replace(VERB_TAIL, '');
        const words = s.split(/\s+/).filter(w => w && !STOP.has(w));
        return { start: start || '', end: end || '', current, words };
    }

    function stem(w) {
        const t = w.replace(/(으로|로|을|를|에서|에|이었\S*|였\S*)$/, '');
        return t.length >= 2 ? t : w;
    }

    function careerRow(text, today) {
        const p = period(text, today, [1, 1]);
        const out = { start: p.start, end: p.current ? '' : p.end, current: p.current, company: '', dept: '', position: '', emp: '', desc: '' };
        let words = p.words;
        const at = words.findIndex(w => w.length > 2 && w.endsWith('에서'));
        if (at >= 0) {
            out.company = words.slice(0, at + 1).join(' ').replace(/에서$/, '');
            words = words.slice(at + 1);
        } else if (words.length) {
            out.company = stem(words.shift());
        }
        const rest = [];
        words.forEach(w => {
            const t = stem(w);
            if (!out.emp && EMP.includes(t)) out.emp = t;
            else if (!out.position && POS.includes(t)) out.position = t;
            else if (!out.dept && /.(팀|부서|본부)$/.test(t)) out.dept = t;
            else rest.push(w);
        });
        if (rest.length) rest[rest.length - 1] = stem(rest[rest.length - 1]);
        out.desc = rest.join(' ');
        return out;
    }

    function eduLevel(school) {
        if (/대학원$/.test(school)) return '대학원(석사)';
        if (/대학교$/.test(school)) return '대학교(4년)';
        if (/대학$/.test(school)) return '전문대(2/3년)';
        if (/고등학교$|고$/.test(school)) return '고등학교';
        return '';
    }

    function eduRow(text, today) {
        const p = period(text, today, [3, 2]);
        const out = { start: p.start, end: p.end, school: '', major: '', level: '', status: p.current ? '재학' : '' };
        const rest = [];
        p.words.forEach((w, i) => {
            const t = stem(w);
            const g = GRAD.find(k => t.startsWith(k));
            if (g && !out.status) out.status = g;
            else if (!out.school && /(학교|대학원|대학|고등학교)$/.test(t)) out.school = t;
            else if (!out.major && /.(학과|학부|과)$/.test(t)) out.major = t;
            else if (t === '전공' && rest.length && !out.major) out.major = rest.pop();
            else rest.push(t);
        });
        if (!out.major && rest.length) out.major = rest.join(' ');
        out.level = eduLevel(out.school);
        return out;
    }

    function certRow(text, today) {
        const p = period(text, today, [1]);
        return { date: p.start, name: certName(p.words.map(stem).filter(w => w !== '자격증').join(' ')) };
    }

    // Whisper가 숫자 등급을 한글로 표기하는 경우에 대응함
    function certName(s) {
        return s.replace(/([일이삼])\s*급/g, (all, n) => money(n) + '급');
    }

    // [발음, 표기, 언어]. 긴 발음부터 비교함
    const LANG_TESTS = [['토익스피킹', 'TOEIC Speaking', '영어'], ['토익', 'TOEIC', '영어'], ['toeic', 'TOEIC', '영어'],
        ['토플', 'TOEFL', '영어'], ['toefl', 'TOEFL', '영어'], ['텝스', 'TEPS', '영어'], ['teps', 'TEPS', '영어'],
        ['오픽', 'OPIc', '영어'], ['opic', 'OPIc', '영어'], ['아이엘츠', 'IELTS', '영어'], ['ielts', 'IELTS', '영어'],
        ['제이엘피티', 'JLPT', '일본어'], ['jlpt', 'JLPT', '일본어'], ['제이피티', 'JPT', '일본어'], ['jpt', 'JPT', '일본어'],
        ['에이치에스케이', 'HSK', '중국어'], ['hsk', 'HSK', '중국어'], ['델레', 'DELE', '스페인어'], ['dele', 'DELE', '스페인어'],
        ['델프', 'DELF', '프랑스어'], ['delf', 'DELF', '프랑스어']];
    // 서버 LANGUAGE_LEVELS 값 기준
    const LANG_LEVEL = [['네이티브', /네이티브|원어민/], ['비즈니스', /비즈니스/], ['일상회화', /회화/], ['기초', /기초|초급/]];

    // 시험명 기준 언어 추정. 언어 직접 발화 시 우선
    function langRow(text, today) {
        const p = period(text, today, [1]);
        const out = { language: '', test: '', score: '', level: '', date: p.start };
        const rest = [];
        p.words.map(stem).forEach(w => {
            const k = w.toLowerCase();
            const t = !out.test && LANG_TESTS.find(([r]) => k === r);
            const lv = slot(w, LANG_LEVEL);
            if (t) {
                out.test = t[1];
                out.language ||= t[2];
            } else if (/.어$/.test(w)) {
                out.language = w;
            } else if (lv) {
                out.level = lv;
            } else if (!out.score && /^([0-9]{2,3}|n[1-5]|[1-6]급|[abc][12]|al|ih|im[1-3]|il|nh|nm|nl)점?$/i.test(k)) {
                out.score = k.replace(/점$/, '').toUpperCase();
            } else {
                rest.push(w);
            }
        });
        if (!out.test && rest.length) out.test = rest.join(' ');
        return out;
    }

    // 받침에 따라 조사를 선택함. ㄹ받침 뒤에서는 으로 대신 로를 사용함
    function josa(w, a, b) {
        const c = w.charCodeAt(w.length - 1) - 0xAC00;
        if (c < 0 || c > 11171) return w + b;
        const jong = c % 28;
        return w + (jong && !(a === '으로' && jong === 8) ? a : b);
    }

    function resumeRow(kind, text, today) {
        if (kind === 'car') return careerRow(text, today);
        if (kind === 'edu') return eduRow(text, today);
        if (kind === 'lang') return langRow(text, today);
        return certRow(text, today);
    }

    // 서버 CONSULT_CATEGORIES, CONSULT_METHODS 키 기준
    const CONSULT_CAT = [['job', /취업|구직|일자리|면접|이력서/], ['device', /보조기기|보조장비|장비|기기/],
        ['work', /근무|직장|회사생활|업무/], ['rights', /권익|권리|차별|부당/], ['etc', /기타|그냥|다른거/]];
    const CONSULT_METHOD = [['phone', /전화|통화/], ['video', /화상|영상|비대면|줌/], ['in_person', /대면|만나|방문|직접/],
        ['chat', /메시지|메세지|문자|채팅/]];
    const IMPORT_SEC = [['career', /경력/], ['education', /학력/], ['cert', /자격/], ['lang', /어학|외국어/],
        ['award', /수상|대외활동|봉사|활동/], ['portfolio', /포트폴리오|링크/]];

    function slot(text, table) {
        const s = squash(text);
        const hit = table.find(([, re]) => re.test(s));
        return hit ? hit[0] : '';
    }

    function consultCmd(text) {
        const s = squash(text);
        if (!/상담/.test(s) || !/(신청|요청|예약|받고싶|하고싶|잡아)/.test(s) || /(내역|목록|현황|취소)/.test(s)) return null;
        return { category: slot(text, CONSULT_CAT), method: slot(text, CONSULT_METHOD) };
    }

    // 음성 메시지는 담당 매니저 한정. 다른 대상 지목 시 other
    function messageCmd(text) {
        const s = squash(text);
        if (!/(메시지|메세지|문자|쪽지)/.test(s) || !/(보내|전송|남겨|남길|쓸래|쓸게)/.test(s)) return null;
        const to = s.match(/^(.+?)(한테|에게|께)/);
        return { other: !!to && !/(매니저|담당|상담사|선생님)/.test(to[1]) };
    }

    function importCmd(text) {
        const s = squash(text);
        if (!/(불러|가져)(와|오)/.test(s)) return null;
        return { sec: slot(text, IMPORT_SEC) };
    }

    // 이력서 목록 명령임. 기본 설정은 보기, 수정보다 뒤에 판정함
    const RES_ACT = [
        ['del', /(을|를)?(삭제|지워|지우기|빼)(해줘|해주세요|하기|버려|해|줘|주세요)?$/],
        ['copy', /(을|를)?(복사|복제)(해줘|해주세요|하기|해|줘|주세요)?$/],
        ['edit', /(을|를)?(수정|편집|고쳐)(해줘|해주세요|하기|해|줘|주세요)?$/],
        ['view', /(을|를)?(보기|보여줘|보여주세요|열어줘|열어|볼래|봐줘|봐)$/],
        ['default', /(을|를|이|가)?(기본|대표)(이력서)?(으로|로)?(설정|지정|바꿔|변경|만들어|해)(해|줘|주세요)*$|(을|를)?(기본|대표)(이력서)?(으로|로)$/],
    ];

    function resumeCmd(text) {
        const s = squash(text);
        if (/^(내)?이력서(목록|리스트)?(읽어|알려|뭐뭐?있|몇개|뭐야)|^목록(읽어|알려)/.test(s)) return { act: 'list' };
        if (/^(새|새로운|새로)이력서(만들|작성|추가|쓰|써|하나)?|^이력서(새로|하나)?(만들|추가)/.test(s)) return { act: 'new' };
        for (const [act, re] of RES_ACT) {
            const m = s.match(re);
            if (!m) continue;
            return { act, ...resumeTarget(s.slice(0, m.index)) };
        }
        return null;
    }

    // 이름 비교용 원문과 순서를 함께 반환함. 마지막은 -1
    function resumeTarget(target) {
        const full = squash(target).replace(/(이에요|예요|이요|요)$/, '');
        const t = full.replace(/^이력서|이력서$/g, '');
        const o = ORD[t.replace(/번째?$/, '')];
        let ord = 0;
        if (/^마지막/.test(t)) ord = -1;
        else if (/^[0-9]+번?째?$/.test(t)) ord = parseInt(t, 10);
        else if (o && /번/.test(t)) ord = o;
        return { target: t && full, ord };
    }

    // 다른 화면에서 이력서 항목 추가 시 사용함. 자기소개서는 항목 제목 명령으로 처리함
    function secAdd(text) {
        const m = squash(text).match(/^(새)?(학력|경력|자격증|자격|어학|외국어|수상|대외활동|봉사활동|포트폴리오)(을|를)?(추가|입력|작성|쓰기|써)(해줘|해주세요|하기|할게|해|줘|주세요)?$/);
        return m ? m[2] : null;
    }

    const LANG_SCORE = /([0-9]{2,3}|n[1-5]|[1-6]급|레벨[1-8]|[abc][12]|al|ih|im[1-3]|il|nh|nm|nl)점?(이요|요|입니다|이에요|예요)?[.!]?$/i;

    // 섹션명 없이 자격증명, 시험명만 말한 추가 명령임. 시험명이면 어학, 그 외는 자격증으로 처리함
    // 동사 없는 발화는 시험명과 점수가 모두 있는 경우만 어학 추가로 처리함
    function itemAdd(text) {
        const s = squash(text).toLowerCase();
        const lang = LANG_TESTS.some(([r]) => s.startsWith(r));
        if (lang && LANG_SCORE.test(s)) {
            return { sec: 'lang', item: text.trim().replace(/\s*(이요|요|입니다|이에요|예요)?\s*[.!]?$/, '') };
        }
        const m = text.trim().match(/^(.+?)\s*(을|를)?\s*(추가|넣어|등록)\s*(해\s*줘|해\s*주세요|하기|할게|해|줘|주세요)?\s*[.!?]?$/);
        if (!m) return null;
        const item = m[1].trim();
        if (/^(새)?(이력서|학력|경력|자격증?|어학|외국어|수상|대외활동|봉사활동|활동|포트폴리오|링크|자기소개서|자소서|파일|첨부파일|항목|칸|행)$/.test(squash(item))) return null;
        const k = squash(item).toLowerCase();
        return { sec: LANG_TESTS.some(([r]) => k.startsWith(r)) ? 'lang' : 'cert', item };
    }

    function fileCmd(text) {
        const s = squash(text);
        return /^(이력서)?(파일|첨부파일|pdf)(을|를)?(첨부|올려|올리기|업로드|추가|넣어|선택)(해줘|해주세요|하기|할게|해|줘|주세요)?$/.test(s)
            || /^(이력서)?파일첨부(해줘|해주세요|하기|할게|해|줘|주세요)?$/.test(s);
    }

    // 기업 채용 제안 명령임. 받는 사람이 추천 인재 등 일반 명칭이면 이름 없음으로 처리함
    function offerCmd(text) {
        const s = squash(text);
        if (!/(제안|메시지|메세지|양식)/.test(s) || !/(보내|전송|발송)/.test(s)) return null;
        const to = s.match(/^(.+?)(님)?(한테|에게|께)/);
        const name = to && !/(추천|인재|사람|지원자|후보|이분|그분)/.test(to[1]) ? to[1] : '';
        const t = text.match(/(\S+)\s*양식\s*(으로|로)/);
        // 조사로 끝나는 단어는 양식 이름이 아닌 앞 문장 성분임
        const tpl = t && !/^(메시지|메세지|저장한|저장된|저장해둔|우리|회사|제안|그|기본)$|(한테|에게|께|을|를|은|는)$/.test(t[1]) ? squash(t[1]) : '';
        return { name, tpl };
    }

    function tplListCmd(text) {
        return /^(메시지|메세지|제안)?양식(목록|리스트)?(뭐뭐?있|읽어|알려|몇개)/.test(squash(text));
    }

    // 값이 없는 치환 표시는 그대로 둠
    function fillTpl(s, vals) {
        return s.replace(/\{([^{}]+)\}/g, (m, k) => vals[k] || m);
    }

    function tplKeys(s) {
        return [...new Set([...s.matchAll(/\{([^{}]+)\}/g)].map(m => m[1]))];
    }

    // 맞춤/조건 공고 검색 명령임. 값의 지역, 고용형태 등 변환은 실행부(seeker-voice.js)에서 처리함
    // 질문형 어미는 범용 질문과 겹치므로 공고 명사가 있을 때만 인정함
    const JOB_FIT_WORDS = /(맞춤|나한테\s*맞는|내\s*조건에\s*맞는|추천|어울리는|할\s*만한|나한테\s*어울리는)/;
    // 보여줘는 이력서, 메시지 등 다른 화면 요청과 겹치므로 공고 명사가 있을 때만 인정함
    const JOB_TAIL_FIND = /(공고|일자리|일거리|자리|직장|일)?\s*(을|를)?\s*(찾아\s*줘|찾아\s*주세요|찾아|찾기)$/;
    const JOB_TAIL_SHOW = /(공고|일자리|일거리|자리|직장|일)\s*(을|를)?\s*(보여\s*줘|보여\s*주세요)$/;
    const JOB_TAIL_HARD = /(공고|일자리|일거리|자리|직장|일)\s*(을|를)?\s*(있\s*어\s*요?|있\s*나\s*요?|있\s*지)$/;
    const JOB_BARE = /^(.+?)\s*(공고|일자리|일거리|자리|직장)$/;

    function jobCmd(text) {
        const s = text.trim().replace(/[.!?]+$/, '');
        if (/^맞춤\s*공고$/.test(s)) return { fit: true, value: '' };
        const tail = [JOB_TAIL_FIND, JOB_TAIL_SHOW, JOB_TAIL_HARD].find(re => re.test(s));
        // 메뉴명(저장 공고, 이력서 등)은 메뉴 이동으로 넘김
        if (tail && navAlias(s.replace(/\s*(을|를)?\s*(찾아\s*줘|찾아\s*주세요|찾아|찾기|보여\s*줘|보여\s*주세요)$/, ''))) return null;
        if (!tail) {
            const b = s.match(JOB_BARE);
            if (!b) return null;
            return { fit: JOB_FIT_WORDS.test(s), value: b[1].replace(JOB_FIT_WORDS, '').trim() };
        }
        const fit = JOB_FIT_WORDS.test(s);
        const value = s.replace(tail, '').replace(JOB_FIT_WORDS, '')
            .replace(/^(나한테|내게|저한테|나는|내가|저는)\s*/, '').trim();
        return { fit, value };
    }

    // 서수는 문장 맨 앞에만 옴. 마지막은 -1
    function itemOrd(s) {
        if (s.startsWith('마지막')) return [-1, s.slice(3)];
        return parseOrd(s);
    }

    const ITEM_OPEN_TAIL = /(을|를)?(열어줘|열어주세요|열어|들어가줘|들어가주세요|들어가|보여줘|보여주세요)$/;
    const ITEM_READ_TAIL = /(을|를)?(읽어줘|읽어주세요|읽어|뭐야|뭐예요|내용알려줘|내용알려주세요|알려줘)$/;

    // 목록 항목 열기/읽기 명령임. 대상은 [data-voice-item]
    function itemCmd(text) {
        const s = squash(text.replace(/[.!?]+$/, ''));
        const openM = s.match(ITEM_OPEN_TAIL);
        const readM = !openM && s.match(ITEM_READ_TAIL);
        if (!openM && !readM) return null;
        const tail = (openM || readM)[0];
        const rest = s.slice(0, s.length - tail.length).replace(/(공고|거|것|내용)$/, '');
        const o = itemOrd(rest);
        // 서수 뒤에 이력서 등 대상 명사가 남으면 해당 명령에서 처리함
        if (!o || o[1]) return null;
        return { act: openM ? 'open' : 'read', ord: o[0] };
    }

    function bookmarkCmd(text) {
        const s = squash(text);
        // 저장만 말한 경우는 화면의 저장 버튼 명령임
        return /^이공고(을|를)?(저장|찜|스크랩)(해줘|해주세요|하기|해|줘|주세요)?$/.test(s)
            || /^(찜|스크랩)(해줘|해주세요|하기|해|줘|주세요)?$/.test(s)
            || /^관심공고에?넣어(줘|주세요)?$/.test(s)
            || /^나중에볼래요?$/.test(s);
    }

    function statusCmd(text) {
        const s = squash(text);
        return /^(내)?지원(현황|상황)(을|를)?(알려줘|알려주세요|알려|어때)$/.test(s)
            || /^지원한거(어떻게됐어|어때)요?$/.test(s)
            || /^합격했어요?$/.test(s)
            || /^서류결과나왔어요?$/.test(s);
    }

    // 지원 취소 명령임. 대상은 순서 또는 회사명 원문
    function withdrawCmd(text) {
        const s = squash(text);
        const m = s.match(/^(.*?)지원(을|를)?(취소|철회)(해줘|해주세요|할래|하기|해|줘|주세요)?$/);
        if (!m) return null;
        const pre = m[1];
        if (!pre) return { ord: 0, value: '' };
        if (pre.startsWith('마지막')) return { ord: -1, value: pre.slice(3) };
        const o = parseOrd(pre);
        if (o && !o[1]) return { ord: o[0], value: '' };
        return { ord: 0, value: pre };
    }

    function proposalCmd(text) {
        const s = squash(text);
        const m = s.match(/^(.*?)제안(을|를)?(수락|거절|받을게|받겠)(해줘|해주세요|할게|하기|해|줘|주세요)?$/);
        if (!m) return null;
        const act = /거절/.test(m[3]) ? 'reject' : 'accept';
        const pre = m[1];
        if (!pre) return { act, ord: 0, value: '' };
        if (pre.startsWith('마지막')) return { act, ord: -1, value: pre.slice(3) };
        const o = parseOrd(pre);
        if (o && !o[1]) return { act, ord: o[0], value: '' };
        return { act, ord: 0, value: pre };
    }

    // 일정 조회 명령임. 기간 없으면 다가오는 일정 기준으로 실행부에서 처리함
    const SCHED_PERIOD = ['오늘', '내일', '이번주', '다음주'];
    function scheduleCmd(text) {
        const s = text.trim().replace(/[.!?]+$/, '');
        let m = s.match(/^(.*?)\s*일정\s*(을|를)?\s*(알려\s*줘|알려\s*주세요|알려|뭐야|뭐예요|어때)$/);
        if (m) {
            const pre = squash(m[1]);
            return { period: SCHED_PERIOD.includes(pre) ? pre : '' };
        }
        m = s.match(/^(오늘|내일|이번\s*주|다음\s*주)\s*(면접)?\s*언제야\s*요?$/);
        if (m) return { period: squash(m[1]) };
        m = s.match(/^(오늘|내일|이번\s*주|다음\s*주)\s*뭐\s*있어\s*요?$/);
        if (m) return { period: squash(m[1]) };
        return null;
    }

    function inboxCmd(text) {
        const s = squash(text);
        if (/^(새)?메시지(가|이)?(있어|있나요?|왔어)요?$/.test(s)) return { kind: 'message' };
        if (/^(새)?메시지(를|을)?읽어(줘|주세요)?$/.test(s)) return { kind: 'message' };
        if (/^매니저가?뭐라고했어요?$/.test(s)) return { kind: 'message' };
        if (/^(새)?알림(이|가)?(있어|있나요?|왔어)요?$/.test(s)) return { kind: 'notif' };
        if (/^(새)?알림(을|를)?읽어(줘|주세요)?$/.test(s)) return { kind: 'notif' };
        return null;
    }

    // 접근성 설정 명령임. 다크모드/라이트모드는 기존 theme 분류를 그대로 재사용함
    // 메시지 본문 속 설정 낱말 오인식 방지로 문장 앞부분 기준 판정, 메시지/상담 문장 제외
    const A11Y_SET = [
        ['font_big', /^(글자|글씨).*(크게|키워|확대)/],
        ['font_normal', /^(글자|글씨).*(보통|원래|기본)/],
        ['contrast_off', /^고대비.*(끄|해제|그만|꺼)/],
        ['contrast_on', /^고대비|^화면.*안보여/],
        ['easy_off', /^쉬운화면.*(끄|해제|그만|꺼)/],
        ['easy_on', /^쉬운화면/],
    ];
    function a11yCmd(text) {
        const s = squash(text);
        if (/(보내|전송|메시지|메세지|상담)/.test(s)) return null;
        const hit = A11Y_SET.find(([, re]) => re.test(s));
        return hit ? hit[0] : null;
    }

    function copyCmd(text) {
        const s = squash(text);
        return /^(이전|예전|지난번|전)(에작성한|에쓴)?(이력서|거)?(랑|이랑|과|와)?(똑같이|그대로|동일하게)(해줘|해주세요|써줘|써주세요|채워줘|채워주세요|만들어줘|만들어주세요)?$/.test(s)
            || /^(이전|예전|지난번|전)이력서(를)?복사해서만들어줘요?$/.test(s);
    }

    // 자격증명 단독 발화 판정임. 짧은 일반 낱말(컴퓨터, 정보 등)의 앞부분 일치 오인식 방지로 이름의 60% 이상 일치만 인정함
    function certHit(q, list) {
        const sq = squash(q);
        if (sq.length < 3) return null;
        return list.find(c => {
            const n = squash(c.name);
            return n === sq || (n.startsWith(sq) && sq.length >= n.length * 0.6) || (n.length >= 3 && sq.startsWith(n));
        }) || null;
    }

    const api = {
        squash, stripWake, money, date, dateText, match, yesno, classify, splitLabel,
        dictCmd, cmdLike, replaceCmd, key, navAlias, punct, dropSentence, isJunk, sentences, month, monthText, rowPrefix, ORD, resumeRow, certName, josa, valueText, closest, url,
        consultCmd, consultCat: t => slot(t, CONSULT_CAT), consultMethod: t => slot(t, CONSULT_METHOD), messageCmd, importCmd, importSec: t => slot(t, IMPORT_SEC),
        resumeCmd, resumeTarget, secAdd, itemAdd, fileCmd, offerCmd, tplListCmd, fillTpl, tplKeys,
        jobCmd, itemCmd, bookmarkCmd, statusCmd, withdrawCmd, proposalCmd, scheduleCmd, inboxCmd, a11yCmd, copyCmd, certHit,
    };
    if (typeof module !== 'undefined') module.exports = api;
    else root.VoiceParse = api;
})(this);

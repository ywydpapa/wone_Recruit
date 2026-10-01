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
        '이력서 작성': ['이력서쓰기', '이력서만들기', '이력서작성', '새이력서'],
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
    };
    // 알파벳 발음표임. 긴 발음부터 비교함
    const LETTERS = [['더블유', 'W'], ['에이치', 'H'], ['에이', 'A'], ['에프', 'F'], ['에스', 'S'], ['엑스', 'X'],
        ['와이', 'Y'], ['제트', 'Z'], ['브이', 'V'], ['케이', 'K'], ['제이', 'J'], ['아이', 'I'], ['엘', 'L'], ['엠', 'M'],
        ['엔', 'N'], ['알', 'R'], ['큐', 'Q'], ['비', 'B'], ['씨', 'C'], ['디', 'D'], ['이', 'E'], ['지', 'G'], ['오', 'O'],
        ['피', 'P'], ['티', 'T'], ['유', 'U'], ['앤', '&']];
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
        // Whisper가 숫자 등급을 한글로 표기하는 경우에 대응함
        const name = p.words.map(stem).filter(w => w !== '자격증').join(' ')
            .replace(/([일이삼])\s*급/g, (all, n) => money(n) + '급');
        return { date: p.start, name };
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
        return certRow(text, today);
    }

    const api = {
        squash, stripWake, money, date, dateText, match, yesno, classify, splitLabel,
        dictCmd, cmdLike, replaceCmd, key, navAlias, punct, dropSentence, isJunk, sentences, month, monthText, rowPrefix, ORD, resumeRow, josa, valueText, closest,
    };
    if (typeof module !== 'undefined') module.exports = api;
    else root.VoiceParse = api;
})(this);

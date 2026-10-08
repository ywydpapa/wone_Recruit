(function() {
    const SECS = {
        edu: { label: '학력', row: 'edu-row', add: 'addEduRow' },
        car: { label: '경력', row: 'career-row', add: 'addCareerRow' },
        cert: { label: '자격증', row: 'cert-row', add: 'addCertRow' },
        lang: { label: '어학', row: 'lang-row', add: 'addLangRow' },
        intro: { label: '자기소개서', row: 'intro-row', add: 'addIntroRow' },
    };
    // [파싱 키, 필드 name, 화면 표시명]
    const FIELDS = {
        edu: [['school', 'edu_school', '학교명'], ['level', 'edu_level', '학교급'], ['major', 'edu_major', '전공'],
            ['start', 'edu_start', '입학'], ['end', 'edu_end', '졸업'], ['status', 'edu_grad_status', '졸업상태']],
        car: [['company', 'car_company', '회사명'], ['dept', 'car_dept', '부서'], ['position', 'car_position', '직책/직위'],
            ['emp', 'car_emp_type', '고용형태'], ['start', 'car_start', '입사'], ['end', 'car_end', '퇴사'],
            ['current', '', '재직중'], ['desc', 'car_desc', '업무 내용']],
        cert: [['name', 'cert_name', '자격증명'], ['date', 'cert_date', '취득일']],
        lang: [['language', 'lang_language', '언어'], ['test', 'lang_test', '시험명'], ['score', 'lang_score', '점수/등급'],
            ['level', 'lang_level', '회화수준'], ['date', 'lang_date', '취득일']],
    };
    const REF_NAMES = ['edu_school', 'cert_name'];
    // 추천 목록이 있는 항목은 발음이 가까운 값으로 보정함
    const LISTS = { dept: 'carDeptList', position: 'carPositionList', language: 'langList' };
    // [섹션명, 섹션 id, 행 추가 함수, 행 class, 대표 칸, 서버 SECTION_COLS 키]
    const SECTIONS = [
        [['학력'], 'sec-education', 'addEduRow', 'edu-row', 'edu_school', 'education'],
        [['경력'], 'sec-career', 'addCareerRow', 'career-row', 'car_company', 'career'],
        [['자격증', '자격'], 'sec-cert', 'addCertRow', 'cert-row', 'cert_name', 'cert'],
        [['어학', '외국어'], 'sec-lang', 'addLangRow', 'lang-row', 'lang_test', 'lang'],
        [['수상활동', '대외활동', '봉사활동', '수상', '활동'], 'sec-award', 'addAwardRow', 'award-row', 'award_title', 'award'],
        [['포트폴리오', '링크'], 'sec-portfolio', 'addPortRow', 'port-row', 'port_desc', 'portfolio'],
        [['자기소개서', '자소서'], 'sec-intro', 'addIntroRow', 'intro-row', 'intro_title'],
        [['파일첨부', '첨부파일', '이력서파일'], 'sec-resume', null],
        [['근무조건', '희망조건', '희망근무조건'], 'sec-work', null],
    ];
    const SEC_RE = new RegExp('^(새)?(' + SECTIONS.flatMap(x => x[0]).join('|') + ')(을|를|칸)?'
        + '(추가|입력|작성|쓰기|써|열어|보여|보기)?(해줘|해주세요|하기|할게|해|줘|주세요)?$');
    const ASK_RE = new RegExp('^(이력서|' + SECTIONS.flatMap(x => x[0]).join('|') + ')?(에|의)?(항목|(입력)?칸)?(은|는|이|가|에)?'
        + '(뭐뭐?|무엇|어떤[거것])(이|가)?(있어요?|있나요?|있지|야|[예에]요|써(야돼)?|입력해)$');
    const BODY_RE = /^내용(을|를)?(말할[게께]|(입력|작성)할게|쓸게|적을게|받아쓰기|작성|입력)/;
    // 섹션명 뒤에 명이 붙은 칸 이름은 섹션명 판정 제외
    const ROW_WORD = new RegExp('(' + SECTIONS.filter(x => x[3]).flatMap(x => x[0]).join('|') + ')(?!증?명)');
    const DEL_TAIL = /\s*(을|를)?\s*(삭제|지워|지우기|빼)\s*(하기|버려|(해\s*)?(줘|주세요)?)\s*[.!?]?$/;
    const EDIT_TAIL = /\s*(으로|로)\s*(바꿔|변경|수정|고쳐)\s*(해\s*)?(줘|주세요)?\s*[.!?]?$/;
    const FILL_RE = /^\s*(학력|경력|자격증|어학|외국어)\s*(칸|란)?\s*(에다가|에다|에)\s*(.+?)\s*(을|를)?\s*(입력|넣어|추가|적어)\s*(해\s*)?(줘|주세요)?\s*[.!?]?$/;
    const INTRO_TITLES = ['지원동기', '성장과정', '성격의 장단점', '입사 후 포부', '직무역량', '자기소개'];

    const panel = document.getElementById('voiceConfirm');
    const heardEl = document.getElementById('voiceHeard');
    const listEl = document.getElementById('voiceFields');
    const applyBtn = document.getElementById('voiceApply');
    let cur = null;
    let busy = null;
    let introEl = null;

    function shown(key, v) {
        if (key === 'current') return v ? '예' : '';
        if (/^(start|end|date)$/.test(key)) return v ? VoiceParse.monthText(v) : '';
        return v;
    }

    function hide() {
        panel.classList.add('d-none');
        cur = null;
    }

    function show(sec, btn, heard, data) {
        Object.entries(LISTS).forEach(([key, id]) => {
            const dl = document.getElementById(id);
            if (data[key] && dl) data[key] = VoiceParse.closest(data[key], [...dl.options].map(o => o.value));
        });
        cur = { sec, btn, heard, data };
        heardEl.textContent = '"' + heard + '"';
        listEl.innerHTML = '';
        const said = [];
        FIELDS[sec].forEach(([key, , name]) => {
            const v = shown(key, data[key]);
            if (!v) return;
            const dt = document.createElement('dt');
            const dd = document.createElement('dd');
            dt.textContent = name;
            dd.textContent = v;
            listEl.append(dt, dd);
            said.push(name + ' ' + v);
        });
        applyBtn.disabled = !said.length;
        btn.after(panel);
        panel.classList.remove('d-none');
        (said.length ? applyBtn : document.getElementById('voiceRetry')).focus();
        Voice.speak(said.length
            ? said.join(', ') + '. 맞으면 입력칸에 넣기를 누르세요'
            : '알아들은 항목이 없어요. 다시 말하기를 누르세요', true);
    }

    async function listen(sec, btn) {
        hide();
        busy = btn;
        btn.setAttribute('aria-pressed', 'true');
        btn.classList.add('dictating');
        const text = await Voice.ask(VoiceParse.josa(SECS[sec].label, '을', '를') + ' 말씀하세요');
        btn.setAttribute('aria-pressed', 'false');
        btn.classList.remove('dictating');
        busy = null;
        if (text) show(sec, btn, text, VoiceParse.resumeRow(sec, text, new Date()));
    }

    function blankRow(cls, add) {
        const last = [...document.querySelectorAll('.' + cls)].pop();
        if (last && [...last.querySelectorAll('input:not([type=checkbox]), select, textarea')].every(el => !el.value)) return last;
        window[add]();
        return [...document.querySelectorAll('.' + cls)].pop();
    }

    function apply() {
        const { sec, data } = cur;
        const row = blankRow(SECS[sec].row, SECS[sec].add);
        let first = null, ref = null;
        FIELDS[sec].forEach(([key, name]) => {
            const v = data[key];
            if (!v) return;
            if (key === 'current') {
                const cb = row.querySelector('.car-current-cb');
                cb.checked = true;
                cb.dispatchEvent(new Event('change', { bubbles: true }));
                return;
            }
            const el = row.querySelector('[name="' + name + '"]');
            if (el.tagName === 'SELECT' && ![...el.options].some(o => o.value === v)) return;
            el.value = v;
            el.dispatchEvent(new Event('change', { bubbles: true }));
            first ||= el;
            if (REF_NAMES.includes(name)) ref = el;
        });
        hide();
        Voice.speak(row.getAttribute('aria-label') + '에 넣었어요. 저장 전에 확인해 주세요', true);
        if (ref) window.refResolve(ref);
        (ref || first || row.querySelector('input, select, textarea')).focus();
    }

    function introTarget() {
        const act = document.activeElement;
        if (act && act.classList.contains('intro-textarea')) return act;
        const all = document.querySelectorAll('.intro-textarea');
        if (all.length) return all[all.length - 1];
        addIntroRow();
        return [...document.querySelectorAll('.intro-textarea')].pop();
    }

    function toggle(btn) {
        const sec = btn.dataset.sec;
        if (sec === 'intro') {
            if (btn.getAttribute('aria-pressed') !== 'true') introEl = introTarget();
            return Voice.dictate(introEl, btn);
        }
        if (busy) return Voice.stop();
        return listen(sec, btn);
    }

    document.querySelectorAll('.resume-voice-btn').forEach(btn => {
        btn.addEventListener('click', () => toggle(btn));
    });
    applyBtn.addEventListener('click', apply);
    document.getElementById('voiceRetry').addEventListener('click', () => listen(cur.sec, cur.btn));
    document.getElementById('voiceCancel').addEventListener('click', () => {
        const btn = cur.btn;
        hide();
        btn.focus();
        Voice.speak('취소했어요', true);
    });
    panel.addEventListener('keydown', e => {
        if (e.key === 'Escape') document.getElementById('voiceCancel').click();
    });

    // 다른 화면에서 지원동기 작성 명령으로 진입한 경우 바로 받아쓰기를 시작함. 새로고침 시 재실행되지 않도록 주소에서 제거함
    window.addEventListener('DOMContentLoaded', () => {
        const q = new URLSearchParams(location.search);
        const item = q.get('voice');
        if (!item) return;
        q.delete('voice');
        history.replaceState(null, '', location.pathname + (q.size ? '?' + q : ''));
        introDictate(VoiceParse.squash(item));
    });

    // 섹션 음성 입력 및 자기소개서 받아쓰기 명령임. STT 프롬프트 영향으로 입력을 이력으로 인식하는 경우도 포함함
    window.addEventListener('DOMContentLoaded', () => Voice.onCommand(async cmd => {
        const s = VoiceParse.squash(cmd);
        const imp = VoiceParse.importCmd(cmd);
        if (imp) {
            await importSec(imp.sec);
            return true;
        }
        const m = s.match(/^(학력|경력|자격증|어학|자기소개서)(을|를)?(말로|음성|받아쓰기)/);
        if (m) {
            const btn = document.querySelector('.resume-voice-btn[aria-label^="' + m[1] + '"]');
            openSec(btn);
            await toggle(btn);
            return true;
        }
        if (BODY_RE.test(s)) {
            const at = document.activeElement && document.activeElement.closest('.intro-row');
            const row = at || [...document.querySelectorAll('.intro-row')].pop();
            if (row) {
                const btn = document.querySelector('.resume-voice-btn[data-sec="intro"]');
                introEl = row.querySelector('.intro-textarea');
                Voice.dictate(introEl, btn);
                return true;
            }
        }
        if (await secCmd(s)) return true;
        if (askFields(s)) return true;
        const f = cmd.match(FILL_RE);
        if (f) {
            const btn = document.querySelector('#' + SECTIONS.find(x => x[0].includes(f[1]))[1] + ' .resume-voice-btn');
            const sec = btn.dataset.sec;
            openSec(btn);
            show(sec, btn, f[4], VoiceParse.resumeRow(sec, f[4], new Date()));
            return true;
        }
        if (await delRow(cmd)) return true;
        if (await editRow(cmd)) return true;
        if (/^(말로)?작성(방법|가이드)|^도움말/.test(s)) {
            bootstrap.Modal.getOrCreateInstance(document.getElementById('voiceGuideModal')).show();
            Voice.speak('말로 작성 방법을 열었어요', true);
            return true;
        }
        const e = s.match(/^(.*?)(을|를)?(내용)?(을|를)?(삭제|지워|지우기|수정|고쳐|이어서|다시|읽어)/);
        if (e && await introEdit(e[1], e[5])) return true;
        if (/저장(해줘|해주세요|해|하기)?$/.test(s)) {
            const a = await Voice.ask('이력서를 저장할까요?', true);
            if (a && VoiceParse.yesno(a) === 'yes') document.getElementById('resumeSaveBtn').click();
            else Voice.speak('저장하지 않았어요', true);
            return true;
        }
        const t = s.match(/^(.+?)(을|를)?(작성|쓰기|입력|받아쓰기)/);
        return t ? introDictate(t[1]) : false;
    }, cmd => [SEC_RE, ASK_RE, BODY_RE].some(re => re.test(VoiceParse.squash(cmd))) || FILL_RE.test(cmd)
        || ((DEL_TAIL.test(cmd) || EDIT_TAIL.test(cmd)) && ROW_WORD.test(cmd))));

    function putRow(row, data) {
        Object.entries(data).forEach(([name, v]) => {
            if (!v) return;
            if (name === 'car_current') {
                const cb = row.querySelector('.car-current-cb');
                cb.checked = true;
                cb.dispatchEvent(new Event('change', { bubbles: true }));
                return;
            }
            const el = row.querySelector('[name="' + name + '"]');
            el.value = v;
            el.dispatchEvent(new Event('change', { bubbles: true }));
        });
        if (data.edu_gpa) row.querySelector('.edu-gpa-wrap').classList.remove('d-none');
    }

    // 현재 폼에 행만 추가. 저장은 사용자 직접 처리
    async function importSec(sec) {
        const others = JSON.parse(document.getElementById('otherResumes').textContent);
        if (!others.length) return Voice.speak('불러올 다른 이력서가 없어요', true);
        if (!sec) {
            const a = await Voice.ask('어떤 항목을 불러올까요? ' + SECTIONS.filter(x => x[5]).map(x => x[0][0]).join(', ') + ' 중에 말씀하세요');
            sec = a && VoiceParse.importSec(a);
            if (!sec) return Voice.speak('불러오지 않았어요', true);
        }
        const [[label], secId, add, cls] = SECTIONS.find(x => x[5] === sec);
        const src = others.length === 1 ? others[0] : await Voice.pick(others, x => x.name);
        if (!src) return Voice.speak('불러오지 않았어요', true);
        const r = await fetch('/resumes/' + src.id + '/sections/' + sec);
        if (!r.ok) return Voice.speak('불러오지 못했어요', true);
        const { rows } = await r.json();
        if (!rows.length) return Voice.speak(src.name + '에는 ' + label + ' 항목이 없어요', true);
        const box = document.getElementById(secId);
        if (box.classList.contains('d-none')) document.querySelector('.section-toggle-btn[data-target="' + secId + '"]').click();
        rows.forEach(data => putRow(blankRow(cls, add), data));
        box.scrollIntoView({ block: 'start' });
        Voice.speak(src.name + '에서 ' + label + ' ' + rows.length + '건을 불러왔어요. 저장 전에 확인해 주세요', true);
    }

    // 서수는 번째 접미사가 있는 경우만 인정. 서수로 시작하는 일반 단어 오인 방지
    function takeOrd(s) {
        const t = s.replace(/\s/g, '');
        if (t.startsWith('마지막')) return [-1, t.slice(3)];
        const m = t.match(/^(첫|한|하나|두|둘|세|셋|네|넷|다섯|[0-9]+)(번째|번|째)/);
        if (!m) return [0, t];
        return [VoiceParse.ORD[m[1]] || Number(m[1]), t.slice(m[0].length)];
    }

    function rowTarget(text) {
        const m = text.match(ROW_WORD);
        if (!m) return null;
        const [names, , , cls, main] = SECTIONS.find(x => x[3] && x[0].includes(m[1]));
        const [ord, pre] = takeOrd(text.slice(0, m.index));
        let post = text.slice(m.index + m[1].length).replace(/^\s*(칸|란)?\s*(의|에서|에|중에)?\s*/, '');
        const n = post.match(/^([0-9]+)\s*(번째|번)?\s*/);
        if (n) post = post.slice(n[0].length);
        const rest = ((pre ? pre + ' ' : '') + post).trim().replace(/\s*(을|를|은|는)$/, '');
        return { label: names[0], cls, main, ord: ord || (n ? Number(n[1]) : 0), rest };
    }

    // 서수, 포커스 행, 단일 행 순으로 대상 결정
    function pickRow(t, rows) {
        if (t.ord === -1) return rows[rows.length - 1];
        if (t.ord) return rows[t.ord - 1] || null;
        const at = document.activeElement && document.activeElement.closest('.' + t.cls);
        return at || (rows.length === 1 ? rows[0] : null);
    }

    function missRow(t, rows, verb) {
        if (!rows.length) return Voice.speak(t.label + '에 ' + verb + ' 항목이 없어요', true);
        if (t.ord) return Voice.speak(t.label + ' ' + (t.ord === -1 ? '마지막' : t.ord + '번째') + ' 항목이 없어요', true);
        return Voice.speak(VoiceParse.josa(t.label, '이', '가') + ' ' + rows.length + '개 있어요. 두 번째 ' + t.label + '처럼 몇 번째인지 말씀해 주세요', true);
    }

    async function delRow(cmd) {
        if (!DEL_TAIL.test(cmd)) return false;
        const t = rowTarget(cmd.replace(DEL_TAIL, ''));
        if (!t) return false;
        const rows = [...document.querySelectorAll('.' + t.cls)];
        const k = VoiceParse.squash(t.rest);
        const row = k
            ? rows.find(r => [...r.querySelectorAll('input, select, textarea')].some(el => el.value && VoiceParse.squash(el.value).includes(k)))
            : pickRow(t, rows);
        if (!row) {
            if (k && rows.length) Voice.speak(VoiceParse.josa(t.rest, '이', '가') + ' 들어간 ' + t.label + '을 찾지 못했어요', true);
            else missRow(t, rows, '삭제할');
            return true;
        }
        const name = row.getAttribute('aria-label');
        const v = row.querySelector('[name="' + t.main + '"]').value;
        const a = await Voice.ask(VoiceParse.josa(v ? name + ', ' + v : name, '을', '를') + ' 삭제할까요?', true);
        if (a && VoiceParse.yesno(a) === 'yes') {
            deleteRow(row);
            Voice.speak(name + ' 삭제했어요', true);
        } else {
            Voice.speak('삭제하지 않았어요', true);
        }
        return true;
    }

    // 칸 이름 미지정 시 대표 칸 수정
    async function editRow(cmd) {
        if (!EDIT_TAIL.test(cmd)) return false;
        const t = rowTarget(cmd.replace(EDIT_TAIL, ''));
        if (!t || !t.rest) return false;
        const rows = [...document.querySelectorAll('.' + t.cls)];
        const row = pickRow(t, rows);
        if (!row) {
            missRow(t, rows, '수정할');
            return true;
        }
        const fields = [...row.querySelectorAll('label[for]')]
            .map(l => ({ name: l.textContent.trim(), el: document.getElementById(l.htmlFor) })).filter(x => x.el);
        const hit = VoiceParse.splitLabel(t.rest, fields.map(x => x.name));
        const f = hit && hit.value ? fields[hit.idx] : fields.find(x => x.el.name === t.main);
        let val = hit && hit.value ? hit.value : t.rest;
        let said = val;
        const el = f.el;
        if (el.type === 'month') {
            val = VoiceParse.month(val, new Date());
            if (!val) {
                Voice.speak('날짜를 못 알아들었어요. 2024년 3월처럼 말해 주세요', true);
                return true;
            }
            said = VoiceParse.monthText(val);
        } else if (el.type === 'url') {
            val = said = VoiceParse.url(val);
            if (!val) {
                Voice.speak('주소를 못 알아들었어요. 알파벳으로 불러 주세요', true);
                return true;
            }
        } else if (el.tagName === 'SELECT') {
            const o = [...el.options].find(x => x.value && VoiceParse.squash(x.textContent) === VoiceParse.squash(val));
            if (!o) {
                Voice.speak(f.name + ' 항목에 ' + VoiceParse.josa(val, '은', '는') + ' 없어요', true);
                return true;
            }
            val = o.value;
        } else if (el.name === 'cert_name') {
            val = said = VoiceParse.certName(val);
        } else if (el.list) {
            val = said = VoiceParse.closest(val, [...el.list.options].map(o => o.value));
        }
        el.value = val;
        el.dispatchEvent(new Event('change', { bubbles: true }));
        el.focus();
        Voice.speak(row.getAttribute('aria-label') + ', ' + f.name + ' ' + VoiceParse.josa(said, '으로', '로') + ' 바꿨어요', true);
        return true;
    }

    // 섹션명 미지정 시 포커스 섹션 기준. 포커스도 없으면 섹션 목록 안내
    function askFields(s) {
        const m = s.match(ASK_RE);
        if (!m) return false;
        const at = document.activeElement && document.activeElement.closest('fieldset[id^="sec-"]');
        const found = m[1] && m[1] !== '이력서'
            ? SECTIONS.find(x => x[0].includes(m[1]))
            : at && SECTIONS.find(x => x[1] === at.id);
        if (!found) {
            Voice.speak('이력서 칸은 ' + SECTIONS.map(x => x[0][0]).join(', ') + '이 있어요. 포트폴리오 항목 뭐 있어처럼 물어보세요', true);
            return true;
        }
        const [names, id, add] = found;
        const sec = document.getElementById(id);
        if (sec.classList.contains('d-none')) document.querySelector('.section-toggle-btn[data-target="' + id + '"]').click();
        if (add && !sec.querySelector('[role=group]')) window[add]();
        const scope = sec.querySelector('[role=group]') || sec;
        const labs = [...scope.querySelectorAll('label[for]')].filter(l => document.getElementById(l.htmlFor));
        if (!labs.length) {
            Voice.speak(names[0] + ' 칸은 직접 고르거나 누르는 항목이에요', true);
            return true;
        }
        const name = l => l.textContent.replace('*', '').trim();
        let msg = names[0] + ' 항목은 ' + labs.map(name).join(', ') + '이에요.';
        labs.forEach(l => {
            const el = document.getElementById(l.htmlFor);
            if (el.tagName !== 'SELECT') return;
            const opts = [...el.options].filter(o => o.value).map(o => o.textContent.trim());
            if (opts.length <= 6) msg += ' ' + VoiceParse.josa(name(l), '은', '는') + ' ' + opts.join(', ') + ' 중에 고르면 돼요.';
        });
        sec.scrollIntoView({ block: 'start' });
        document.getElementById(labs[0].htmlFor).focus();
        Voice.speak(msg + ' ' + name(labs[0]) + '부터 말씀하세요', true);
        return true;
    }

    async function secCmd(s) {
        const m = s.match(SEC_RE);
        if (!m) return false;
        const [names, id, add] = SECTIONS.find(x => x[0].includes(m[2]));
        const sec = document.getElementById(id);
        if (sec.classList.contains('d-none')) document.querySelector('.section-toggle-btn[data-target="' + id + '"]').click();
        let row = null;
        if (add && (m[1] || /추가|입력|작성|쓰기|써/.test(m[4] || ''))) {
            const rows = [...sec.querySelectorAll('[role=group][aria-label]')];
            row = rows.reverse().find(r => [...r.querySelectorAll('input[type=text], input:not([type]), textarea')].every(el => !el.value));
            if (!row) {
                window[add]();
                row = [...sec.querySelectorAll('[role=group][aria-label]')].pop();
            }
        }
        const el = (row || sec).querySelector('input[type=text], input:not([type]), textarea, select');
        sec.scrollIntoView({ block: 'start' });
        if (!row || !el) {
            Voice.speak(names[0] + ' 칸을 열었어요', true);
            return true;
        }
        el.focus();
        const lab = el.id && document.querySelector('label[for="' + el.id + '"]');
        const name = lab ? lab.textContent.trim() : el.placeholder;
        Voice.speak(row.getAttribute('aria-label') + ', ' + VoiceParse.josa(name, '을', '를') + ' 말씀하세요', true);
        return true;
    }

    // 제목 없이 삭제를 요청하면 마지막으로 받아쓴 항목을 대상으로 함
    async function introEdit(said, verb) {
        if (verb === '읽어' && !said) return false;
        const titleOf = r => r.querySelector('[name="intro_title"]');
        const rows = [...document.querySelectorAll('.intro-row')];
        const row = said
            ? rows.find(r => VoiceParse.squash(titleOf(r).value) === said) || rows[itemNo(said, rows) - 1]
            : introEl && introEl.closest('.intro-row');
        if (!row) return false;
        const ta = row.querySelector('.intro-textarea');
        const name = titleOf(row).value || (rows.indexOf(row) + 1) + '번째 항목';
        if (verb === '읽어') {
            Voice.speak(ta.value ? name + '. ' + ta.value : VoiceParse.josa(name, '은', '는') + ' 비어 있어요');
            return true;
        }
        if (/삭제|지워|지우기/.test(verb)) {
            const a = await Voice.ask(name + ' 내용을 모두 지울까요?');
            if (a && VoiceParse.yesno(a) === 'yes') {
                ta.value = '';
                ta.dispatchEvent(new Event('input', { bubbles: true }));
                Voice.speak('지웠어요. ' + name + ' 작성이라고 하면 다시 쓸 수 있어요', true);
            } else {
                Voice.speak('지우지 않았어요', true);
            }
            return true;
        }
        const btn = document.querySelector('.resume-voice-btn[data-sec="intro"]');
        openSec(btn);
        introEl = ta;
        ta.dataset.voiceName = name;
        await Voice.speak('끝에 이어서 받아쓸게요');
        Voice.dictate(ta, btn);
        return true;
    }

    function itemNo(said, rows) {
        const m = said.match(/^(.+?)(번째|번)?항목$/);
        if (!m) return 0;
        if (m[1] === '다음') {
            const i = introEl ? rows.indexOf(introEl.closest('.intro-row')) : -1;
            return (i >= 0 ? i + 1 : rows.length) + 1;
        }
        const n = VoiceParse.ORD[m[1]] || VoiceParse.money(m[1]) || 0;
        return n <= 10 ? n : 0;
    }

    function openSec(btn) {
        const sec = btn.closest('fieldset');
        if (sec.classList.contains('d-none')) document.querySelector('.section-toggle-btn[data-target="' + sec.id + '"]').click();
    }

    // 같은 제목 항목, 빈 항목, 새 항목 순으로 대상을 정함
    function introDictate(said) {
        const titleOf = r => r.querySelector('[name="intro_title"]');
        const rows = [...document.querySelectorAll('.intro-row')];
        let row = rows.find(r => VoiceParse.squash(titleOf(r).value) === said);
        const n = !row && itemNo(said, rows);
        if (n) {
            while (rows.length < n) {
                addIntroRow();
                rows.push([...document.querySelectorAll('.intro-row')].pop());
            }
            row = rows[n - 1];
        } else if (!row) {
            const title = INTRO_TITLES.find(x => VoiceParse.squash(x) === said);
            if (!title) return false;
            row = rows.find(r => !titleOf(r).value && !r.querySelector('.intro-textarea').value);
            if (!row) {
                addIntroRow();
                row = [...document.querySelectorAll('.intro-row')].pop();
            }
            titleOf(row).value = title;
        }
        const btn = document.querySelector('.resume-voice-btn[data-sec="intro"]');
        openSec(btn);
        introEl = row.querySelector('.intro-textarea');
        introEl.dataset.voiceName = titleOf(row).value || (rows.indexOf(row) + 1) + '번째 항목';
        Voice.dictate(introEl, btn);
        return true;
    }

    // 제목 입력 후 엔터 시 폼 제출 대신 내용 칸으로 이동
    document.addEventListener('keydown', e => {
        if (e.key !== 'Enter' || e.isComposing || e.target.name !== 'intro_title' || e.defaultPrevented) return;
        e.preventDefault();
        e.target.closest('.intro-row').querySelector('.intro-textarea').focus();
    });

    document.addEventListener('keydown', e => {
        if (!e.altKey || e.code !== 'KeyM') return;
        const sec = document.activeElement && document.activeElement.closest('fieldset');
        const btn = sec && sec.querySelector('.resume-voice-btn');
        e.preventDefault();
        if (!btn) return Voice.speak('학력, 경력, 자격증, 어학, 자기소개서 칸에서 눌러 주세요');
        toggle(btn);
    });
})();

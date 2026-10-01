(function() {
    const SECS = {
        edu: { label: '학력', row: 'edu-row', add: 'addEduRow' },
        car: { label: '경력', row: 'career-row', add: 'addCareerRow' },
        cert: { label: '자격증', row: 'cert-row', add: 'addCertRow' },
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
    };
    const REF_NAMES = ['edu_school', 'cert_name'];
    // [섹션명, 섹션 id, 행 추가 함수]
    const SECTIONS = [
        [['학력'], 'sec-education', 'addEduRow'],
        [['경력'], 'sec-career', 'addCareerRow'],
        [['자격증', '자격'], 'sec-cert', 'addCertRow'],
        [['어학', '외국어'], 'sec-lang', 'addLangRow'],
        [['수상활동', '수상', '활동', '대외활동', '봉사활동'], 'sec-award', 'addAwardRow'],
        [['포트폴리오', '링크'], 'sec-portfolio', 'addPortRow'],
        [['자기소개서', '자소서'], 'sec-intro', 'addIntroRow'],
        [['파일첨부', '첨부파일', '이력서파일'], 'sec-resume', null],
        [['근무조건', '희망조건', '희망근무조건'], 'sec-work', null],
    ];
    const SEC_RE = new RegExp('^(새)?(' + SECTIONS.flatMap(x => x[0]).join('|') + ')(을|를|칸)?'
        + '(추가|입력|작성|쓰기|써|열어|보여|보기)?(해줘|해주세요|하기|할게|해|줘|주세요)?$');
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

    function targetRow(sec) {
        const rows = document.querySelectorAll('.' + SECS[sec].row);
        const last = rows[rows.length - 1];
        const empty = last && FIELDS[sec].every(([, name]) => {
            const el = name && last.querySelector('[name="' + name + '"]');
            return !el || !el.value;
        });
        if (empty) return last;
        window[SECS[sec].add]();
        return [...document.querySelectorAll('.' + SECS[sec].row)].pop();
    }

    function apply() {
        const { sec, data } = cur;
        const row = targetRow(sec);
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
        const m = s.match(/^(학력|경력|자격증|자기소개서)(을|를)?(말로|음성|받아쓰기)/);
        if (m) {
            const btn = document.querySelector('.resume-voice-btn[aria-label^="' + m[1] + '"]');
            openSec(btn);
            await toggle(btn);
            return true;
        }
        if (await secCmd(s)) return true;
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
    }, cmd => SEC_RE.test(VoiceParse.squash(cmd))));

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

    document.addEventListener('keydown', e => {
        if (!e.altKey || e.code !== 'KeyM') return;
        const sec = document.activeElement && document.activeElement.closest('fieldset');
        const btn = sec && sec.querySelector('.resume-voice-btn');
        e.preventDefault();
        if (!btn) return Voice.speak('학력, 경력, 자격증, 자기소개서 칸에서 눌러 주세요');
        toggle(btn);
    });
})();

(function() {
    const V = window.VoiceParse;
    const CATS = { job: '취업 상담', device: '보조장비', work: '근무 중 어려움', rights: '권익 보호', etc: '기타' };
    const METHODS = { phone: '전화', video: '화상', in_person: '대면', chat: '메시지' };
    const NONE = /^(없|상관없|아무때|아니|아뇨)/;

    // 현재 화면이 아니면 이동 후 cmd로 재실행함
    async function navCmd(path, cmd, msg) {
        await Voice.speak(msg, true);
        location.href = path + '?cmd=' + encodeURIComponent(cmd);
    }

    function voiceItems() {
        return [...document.querySelectorAll('[data-voice-item]')].filter(el => el.getClientRects().length > 0);
    }

    // ord 0은 항목이 하나뿐일 때만 단일 선택함
    function pickItem(ord) {
        const items = voiceItems();
        if (ord === -1) return items[items.length - 1] || null;
        if (ord > 0) return items[ord - 1] || null;
        return items.length === 1 ? items[0] : null;
    }

    async function openItem(ord) {
        const items = voiceItems();
        const it = pickItem(ord);
        if (!it) return Voice.speak(items.length ? '해당 순서의 항목이 없어요' : '열 수 있는 목록이 없어요');
        const link = it.matches('a[href]') ? it : it.querySelector('a[href]');
        if (!link) return Voice.speak('열 수 있는 링크가 없어요');
        await Voice.speak('열게요', true);
        location.href = link.href;
    }

    function readItem(ord) {
        const items = voiceItems();
        const it = pickItem(ord);
        if (!it) return Voice.speak(items.length ? '해당 순서의 항목이 없어요' : '읽을 목록이 없어요');
        const text = (it.dataset.voiceText || it.textContent).replace(/\s+/g, ' ').trim();
        return Voice.speak(text || '내용이 없어요');
    }

    // 취소/응답 폼이 남아 있는 항목만 대상으로 함
    function findRow(ord, value, formSel) {
        const items = voiceItems().filter(el => el.querySelector(formSel));
        if (!items.length) return { items, row: null };
        if (ord === -1) return { items, row: items[items.length - 1] };
        if (ord > 0) return { items, row: items[ord - 1] || null };
        if (value) {
            const v = V.squash(value);
            return { items, row: items.find(el => V.squash(el.dataset.voiceText || el.textContent).includes(v)) || null };
        }
        return { items, row: items.length === 1 ? items[0] : null };
    }

    async function bookmarkToggle() {
        if (!/^\/jobs\/[0-9]+$/.test(location.pathname)) return Voice.speak('공고 상세 화면에서 공고를 저장할 수 있어요');
        const form = document.querySelector('form[action^="/bookmarks/"][action$="/toggle"]');
        const btn = form && form.querySelector('button[type=submit]');
        if (!btn) return Voice.speak('공고 상세 화면에서 공고를 저장할 수 있어요');
        const saved = btn.textContent.includes('저장됨');
        await Voice.speak(saved ? '저장을 취소했어요' : '공고를 저장했어요', true);
        btn.click();
    }

    // 지역명 접미사를 떼고 비교함
    const SIDO_TAIL = /(특별자치시|특별자치도|특별시|광역시|도|시)$/;
    let jobRegionsCache = null;
    async function jobRegions() {
        if (jobRegionsCache) return jobRegionsCache;
        try {
            const r = await fetch('/api/regions');
            jobRegionsCache = r.ok ? await r.json() : [];
        } catch (e) {
            jobRegionsCache = [];
        }
        return jobRegionsCache;
    }

    const JOB_EMP = ['정규직', '계약직', '인턴', '파견', '프리랜서'];

    // 맞춤/조건 공고 검색 실행. 매칭되지 않은 낱말은 q로 넘김
    async function jobSearch(j) {
        let text = (j.value || '').trim();
        const params = new URLSearchParams();
        if (j.fit) params.set('sort', 'fit');
        const emp = JOB_EMP.find(e => text.includes(e));
        if (emp) {
            params.set('employment_type', emp);
            text = text.replace(emp, ' ');
        }
        if (/재택|집에서|홈오피스/.test(text)) {
            params.set('remote', '1');
            text = text.replace(/집에서\s*하는\s*일|집에서\s*하는|재택|집에서|홈오피스/g, ' ');
        }
        const hm = text.match(/([0-9]+)\s*시간/);
        if (hm) {
            const hrs = Number(hm[1]);
            params.set('max_hours', String([4, 6, 8].find(o => hrs <= o) || 8));
            text = text.replace(hm[0], ' ').replace(/하루\s*$/, ' ');
        }
        const regions = await jobRegions();
        const sido = regions.find(s => text.includes(s.replace(SIDO_TAIL, '')));
        if (sido) {
            params.set('sido', sido);
            text = text.replace(sido.replace(SIDO_TAIL, ''), ' ');
        }
        const q = text.replace(/\s+/g, ' ').trim();
        if (q) params.set('q', q);
        params.set('voice', '1');
        const lead = j.fit ? '맞춤 ' : (q ? q + ' ' : '');
        await Voice.speak(lead + '공고를 찾을게요', true);
        location.href = '/jobs?' + params.toString();
    }

    function announceJobs(fit) {
        const rows = voiceItems();
        const cntEl = document.querySelector('.jobs-count strong');
        const cnt = cntEl ? cntEl.textContent.trim() : String(rows.length);
        const titles = rows.slice(0, 3).map(el => (el.dataset.voiceText || el.textContent).replace(/\s+/g, ' ').trim()).filter(Boolean);
        Voice.speak((fit ? '맞춤 ' : '') + '공고 ' + cnt + '건이에요' + (titles.length ? '. ' + titles.join('. ') : ''));
    }

    async function withdrawExec(w, cmd) {
        if (location.pathname !== '/applications') return navCmd('/applications', cmd, '지원 현황 화면에서 처리할게요');
        const { items, row } = findRow(w.ord, w.value, 'form[action$="/withdraw"]');
        if (!row) return Voice.speak(items.length ? '취소할 지원을 못 찾았어요' : '취소할 수 있는 지원이 없어요');
        const name = (row.dataset.voiceText || row.textContent).replace(/\s+/g, ' ').trim();
        const a = await Voice.ask(name + ' 지원을 취소할까요?', true);
        if (!a || V.yesno(a) !== 'yes') return Voice.speak('취소하지 않았어요');
        row.querySelector('form[action$="/withdraw"]').submit();
    }

    async function proposalExec(p, cmd) {
        if (location.pathname !== '/proposals') return navCmd('/proposals', cmd, '매칭 제안 화면에서 처리할게요');
        const { items, row } = findRow(p.ord, p.value, 'form[action$="/respond"]');
        if (!row) return Voice.speak(items.length ? '처리할 제안을 못 찾았어요' : '처리할 수 있는 제안이 없어요');
        const name = (row.dataset.voiceText || row.textContent).replace(/\s+/g, ' ').trim();
        const verb = p.act === 'reject' ? '거절' : '수락';
        const a = await Voice.ask(name + ' 제안을 ' + verb + '할까요?', true);
        if (!a || V.yesno(a) !== 'yes') return Voice.speak(verb + '하지 않았어요');
        const form = row.querySelector('form[action$="/respond"]');
        const fd = new FormData(form);
        fd.set('action', p.act);
        const res = await fetch(form.action, { method: 'POST', body: fd });
        if (!res.ok) return Voice.speak(verb + '하지 못했어요');
        await Voice.speak(verb + '했어요');
        location.reload();
    }

    function ymd(d) {
        return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
    }

    // 일정 화면의 데이터는 월 상관없이 전체가 들어있으므로 날짜 문자열로 범위만 거름
    function schedMatches(period) {
        const today = new Date();
        const groups = [...document.querySelectorAll('.schedule-date-group')];
        if (!period) {
            const until = new Date(today);
            until.setDate(until.getDate() + 7);
            const lo = ymd(today), hi = ymd(until);
            return groups.filter(g => g.dataset.date >= lo && g.dataset.date <= hi);
        }
        if (period === '오늘' || period === '내일') {
            const t = new Date(today);
            if (period === '내일') t.setDate(t.getDate() + 1);
            const ds = ymd(t);
            return groups.filter(g => g.dataset.date === ds);
        }
        const start = new Date(today);
        start.setDate(start.getDate() - today.getDay() + (period === '다음주' ? 7 : 0));
        const end = new Date(start);
        end.setDate(end.getDate() + 6);
        const lo = ymd(start), hi = ymd(end);
        return groups.filter(g => g.dataset.date >= lo && g.dataset.date <= hi);
    }

    async function scheduleRead(period, cmd) {
        if (location.pathname !== '/schedule') return navCmd('/schedule', cmd, '일정 화면에서 알려 드릴게요');
        const evs = schedMatches(period).flatMap(g => [...g.querySelectorAll('.schedule-event')]);
        if (!evs.length) return Voice.speak((period ? period + ' ' : '다가오는 ') + '일정이 없어요');
        const lines = evs.slice(0, 5).map(ev => {
            const time = ev.querySelector('.schedule-event-time')?.textContent.trim() || '';
            const title = ev.querySelector('.schedule-event-title')?.textContent.trim() || '';
            return (time ? time + ' ' : '') + title;
        });
        await Voice.speak((period ? period + ' ' : '') + '일정 ' + evs.length + '건이에요. ' + lines.join('. '));
    }

    async function notifRead(cmd) {
        if (location.pathname !== '/notifications') return navCmd('/notifications', cmd, '알림 화면에서 읽어 드릴게요');
        const items = [...document.querySelectorAll('.home-list li')];
        if (!items.length) return Voice.speak('알림이 없어요');
        const unread = items.filter(el => el.classList.contains('unread')).length;
        const lines = items.slice(0, 3).map(el => (el.querySelector('a')?.textContent || '').trim());
        await Voice.speak('안 읽은 알림 ' + unread + '건이에요. ' + lines.join('. '));
    }

    async function inboxRead(kind, cmd) {
        if (kind === 'notif') return notifRead(cmd);
        if (location.pathname !== '/messages') return navCmd('/messages', cmd, '메시지 화면에서 읽어 드릴게요');
        const items = [...document.querySelectorAll('.msg-list .msg-item')];
        if (!items.length) return Voice.speak('받은 메시지가 없어요');
        const unread = items.filter(el => el.classList.contains('msg-unread')).length;
        const lines = items.slice(0, 3).map(el => {
            const name = (el.querySelector('.msg-item-name')?.textContent || '').trim();
            const prev = (el.querySelector('.msg-item-preview')?.textContent || '').trim();
            return name + ', ' + prev;
        });
        await Voice.speak('안 읽은 메시지 ' + unread + '건이에요. ' + lines.join('. '));
    }

    function statusRead() {
        if (location.pathname !== '/applications') {
            Voice.speak('지원 현황 화면에서 알려 드릴게요', true);
            location.href = '/applications?voice=read';
            return;
        }
        const rows = [...document.querySelectorAll('.mp-row')];
        if (!rows.length) return Voice.speak('아직 지원한 공고가 없어요');
        const counts = {};
        rows.forEach(r => {
            const label = (r.querySelector('.badge')?.textContent || '').trim();
            if (label) counts[label] = (counts[label] || 0) + 1;
        });
        const summary = Object.entries(counts).map(([k, v]) => k + ' ' + v + '건').join(', ');
        const lines = rows.slice(0, 3).map(r => (r.dataset.voiceText || r.textContent).replace(/\s+/g, ' ').trim());
        Voice.speak('지원 ' + rows.length + '건, ' + summary + '이에요. 최근 지원은 ' + lines.join('. '));
    }

    function a11ySet(key) {
        const A = window.A11y;
        if (!A) return;
        if (key === 'font_big') {
            const size = A.get('font_size') === 150 ? 200 : 150;
            A.set('font_size', size);
            return Voice.speak('글자를 ' + (size === 200 ? '더 크게' : '크게') + ' 했어요', true);
        }
        if (key === 'font_normal') {
            A.set('font_size', 100);
            return Voice.speak('글자를 보통 크기로 했어요', true);
        }
        if (key === 'contrast_on') {
            A.set('high_contrast', true);
            return Voice.speak('고대비로 바꿨어요', true);
        }
        if (key === 'contrast_off') {
            A.set('high_contrast', false);
            return Voice.speak('고대비를 해제했어요', true);
        }
        if (key === 'easy_on') {
            A.set('easy_mode', true);
            return Voice.speak('쉬운 화면으로 바꿨어요', true);
        }
        if (key === 'easy_off') {
            A.set('easy_mode', false);
            return Voice.speak('쉬운 화면을 해제했어요', true);
        }
    }

    async function copyLatest() {
        const fd = new FormData();
        fd.append('csrf_token', document.querySelector('meta[name="csrf-token"]').content);
        const res = await fetch('/resumes/copy-latest', { method: 'POST', body: fd });
        if (!res.ok) return Voice.speak('복사할 이력서가 없어요');
        const { id } = await res.json();
        await Voice.speak('최근 이력서를 복사해서 열게요');
        location.href = '/resumes/' + id + '/edit';
    }

    // 취소 시 null 반환. 인식 실패 시 1회 재질문
    async function askSlot(q, parse) {
        for (let i = 0; i < 2; i++) {
            const a = await Voice.ask(i ? '잘 못 알아들었어요. ' + q : q);
            if (a === null) return null;
            const v = parse(a);
            if (v) return v;
        }
        return null;
    }

    async function consult(c) {
        const cat = c.category || await askSlot('어떤 상담인가요? ' + Object.values(CATS).join(', ') + ' 중에 말씀하세요', V.consultCat);
        if (!cat) return Voice.speak('상담 신청을 취소했어요');
        const method = c.method || await askSlot('상담 방법은 ' + Object.values(METHODS).join(', ') + ' 중에 어떤 걸로 할까요?', V.consultMethod);
        if (!method) return Voice.speak('상담 신청을 취소했어요');
        const content = await Voice.ask('상담받고 싶은 내용을 말씀하세요');
        if (!content) return Voice.speak('상담 신청을 취소했어요');
        const t = await Voice.ask('원하는 시간대가 있으면 말씀하세요. 없으면 없어요라고 하세요');
        if (t === null) return Voice.speak('상담 신청을 취소했어요');
        const time = NONE.test(V.squash(t)) ? '' : t.trim();
        const a = await Voice.ask('상담 분야 ' + CATS[cat] + ', 방법 ' + METHODS[method] + (time ? ', 희망 시간 ' + time : '')
            + ', 내용 ' + content + '. 이대로 신청할까요?');
        if (!a || V.yesno(a) !== 'yes') return Voice.speak('신청하지 않았어요');
        // 성공 시 /consult, 검증 실패 시 /consult/new로 리다이렉트됨
        const fd = new FormData();
        fd.append('category', cat);
        fd.append('method', method);
        fd.append('content', content);
        fd.append('preferred_time', time);
        fd.append('csrf_token', document.querySelector('meta[name="csrf-token"]').content);
        const r = await fetch('/consult', { method: 'POST', body: fd });
        if (!r.ok || new URL(r.url).pathname !== '/consult') return Voice.speak('신청하지 못했어요. 상담 신청 화면에서 다시 해 주세요');
        await Voice.speak('상담을 신청했어요. 신청 내역으로 이동할게요');
        location.href = '/consult';
    }

    async function message(m) {
        if (m.other) return Voice.speak('음성으로는 담당 매니저에게만 메시지를 보낼 수 있어요');
        const r = await fetch('/api/messages/manager');
        if (r.status === 404) return Voice.speak('아직 담당 매니저가 배정되지 않았어요');
        if (!r.ok) return Voice.speak('담당 매니저 정보를 가져오지 못했어요');
        const mgr = await r.json();
        const body = await Voice.ask(mgr.name + ' 매니저님께 보낼 내용을 말씀하세요');
        if (!body) return Voice.speak('메시지를 보내지 않았어요');
        const a = await Voice.ask(mgr.name + ' 매니저님께 보낼 내용이에요. ' + body + '. 보낼까요?');
        if (!a || V.yesno(a) !== 'yes') return Voice.speak('메시지를 보내지 않았어요');
        const fd = new FormData();
        fd.append('to_id', mgr.id);
        fd.append('body', body);
        fd.append('csrf_token', document.querySelector('meta[name="csrf-token"]').content);
        const res = await fetch('/api/messages/send', { method: 'POST', body: fd });
        Voice.speak(res.ok ? '보냈어요' : '메시지를 보내지 못했어요');
    }

    const ACT_VERB = { del: '삭제할', copy: '복사할', edit: '수정할', view: '볼', default: '기본으로 설정할' };
    const rows = () => [...document.querySelectorAll('[data-resume-id]')];
    // 이력서 편집 화면의 항목 명령은 resume-voice.js에서 처리함
    const onEdit = () => !!document.getElementById('sec-resume');

    // 이름 완전일치, 이름 부분일치(1건), 기본 이력서, 순서 기준으로 찾음
    function findResume(r, list) {
        if (!r.target) return null;
        const name = el => V.squash(el.dataset.name);
        const t = r.target.replace(/이력서$/, '');
        const hit = list.find(el => name(el) === r.target) || (t && list.find(el => name(el) === t));
        if (hit) return hit;
        const part = t ? list.filter(el => name(el).includes(t)) : [];
        if (part.length === 1) return part[0];
        if (/^(기본|대표)(이력서)?$/.test(r.target)) return list.find(el => el.dataset.default);
        return r.ord === -1 ? list[list.length - 1] : list[r.ord - 1] || null;
    }

    function readList(list) {
        if (!list.length) return Voice.speak('아직 작성한 이력서가 없어요. 새 이력서라고 하면 만들 수 있어요');
        return Voice.speak('이력서가 ' + list.length + '개 있어요. ' + list.map((el, i) => (i + 1) + '번 ' + el.dataset.name
            + (el.dataset.default ? ', 기본 이력서' : '') + (el.dataset.updated ? ', ' + V.dateText(el.dataset.updated) + ' 수정' : '')).join('. '));
    }

    async function newResume() {
        const f = document.querySelector('#newResumeModal form');
        if (!f) {
            await Voice.speak('이력서 관리 화면에서 새 이력서를 만들게요');
            location.href = '/resumes?voice=new';
            return;
        }
        const ans = await Voice.ask('새 이력서 이름을 말씀하세요. 이름 없이 만들려면 없어요라고 하세요');
        if (ans === null) return Voice.speak('새 이력서를 만들지 않았어요');
        const name = NONE.test(V.squash(ans)) ? '' : ans.trim().replace(/[.!?]+$/, '');
        await Voice.speak((name ? V.josa(name, '으로', '로') + ' ' : '') + '새 이력서를 만들게요');
        f.elements.name.value = name;
        f.elements.copy_from.value = '';
        f.submit();
    }

    // 처리하지 않은 보기 명령은 메뉴 이동으로 넘기기 위해 false 반환
    async function resumeAct(r) {
        const list = rows();
        if (r.act === 'list') return readList(list);
        if (r.act === 'new') return newResume();
        let row = r.target ? findResume(r, list) : list.length === 1 ? list[0] : null;
        if (!row && r.act === 'view') return false;
        if (!row && r.target) return Voice.speak('말씀하신 이력서를 못 찾았어요. 이력서 목록 읽어줘라고 하면 이름을 알려 드려요');
        if (!row) {
            const ans = await Voice.ask(ACT_VERB[r.act] + ' 이력서의 이름이나 번호를 말씀하세요');
            if (ans === null) return Voice.speak('취소했어요');
            row = findResume(V.resumeTarget(ans), list);
            if (!row) return Voice.speak('말씀하신 이력서를 못 찾았어요');
        }
        const name = row.dataset.name;
        const id = row.dataset.resumeId;
        if (r.act === 'view' || r.act === 'edit') {
            await Voice.speak(V.josa(name, '을', '를') + (r.act === 'view' ? ' 열게요' : ' 수정할게요'));
            location.href = '/resumes/' + id + (r.act === 'edit' ? '/edit' : '');
        } else if (r.act === 'copy') {
            await Voice.speak(name + ' 복사본을 만들게요');
            row.querySelector('form[action="/resumes/new"]').submit();
        } else if (r.act === 'default') {
            if (row.dataset.default) return Voice.speak('이미 기본 이력서예요');
            await Voice.speak(V.josa(name, '을', '를') + ' 기본 이력서로 바꿀게요');
            row.querySelector('form[action$="/default"]').submit();
        } else if (row.dataset.default) {
            Voice.speak('기본 이력서는 삭제할 수 없어요. 다른 이력서를 기본으로 설정한 다음 삭제해 주세요');
        } else {
            // 음성 확인으로 대체하여 브라우저 확인 창을 띄우지 않음
            const a = await Voice.ask(V.josa(name, '을', '를') + ' 삭제할까요? 삭제하면 되돌릴 수 없어요');
            if (!a || V.yesno(a) !== 'yes') return Voice.speak('삭제하지 않았어요');
            const res = await fetch('/resumes/' + id, { method: 'DELETE' });
            if (!res.ok) return Voice.speak('삭제하지 못했어요');
            await Voice.speak('삭제했어요');
            location.href = (await res.json()).redirect;
        }
        return true;
    }

    // 다른 화면에서 받은 항목 명령은 기본 이력서, 없으면 최근 수정 이력서 편집 화면에서 실행함
    async function toEdit(cmd) {
        await Voice.speak('이력서 작성 화면으로 갈게요');
        location.href = '/resumes/write?cmd=' + encodeURIComponent(cmd);
    }

    // 이력서 목록 명령은 보기/열기 꼬리말이 다른 명령과 겹치므로 맨 뒤에서 처리함
    async function seekerCmd(cmd) {
        const it = V.itemCmd(cmd);
        if (it) {
            if (it.act === 'open') await openItem(it.ord);
            else readItem(it.ord);
            return true;
        }
        if (V.bookmarkCmd(cmd)) {
            await bookmarkToggle();
            return true;
        }
        const js = V.jobCmd(cmd);
        if (js) {
            await jobSearch(js);
            return true;
        }
        if (V.statusCmd(cmd)) {
            statusRead();
            return true;
        }
        const wd = V.withdrawCmd(cmd);
        if (wd) {
            await withdrawExec(wd, cmd);
            return true;
        }
        const pr = V.proposalCmd(cmd);
        if (pr) {
            await proposalExec(pr, cmd);
            return true;
        }
        const sc = V.scheduleCmd(cmd);
        if (sc) {
            await scheduleRead(sc.period, cmd);
            return true;
        }
        const ib = V.inboxCmd(cmd);
        if (ib) {
            await inboxRead(ib.kind, cmd);
            return true;
        }
        const a11y = V.a11yCmd(cmd);
        if (a11y) {
            a11ySet(a11y);
            return true;
        }
        const c = V.consultCmd(cmd);
        if (c) {
            await consult(c);
            return true;
        }
        const m = V.messageCmd(cmd);
        if (m) {
            await message(m);
            return true;
        }
        if (V.copyCmd(cmd)) {
            if (onEdit()) return false; // 작성 화면은 resume-voice.js가 처리함
            await copyLatest();
            return true;
        }
        if (!onEdit()) {
            const sec = V.secAdd(cmd);
            if (sec) {
                await toEdit(sec + ' 추가');
                return true;
            }
            if (V.fileCmd(cmd)) {
                await toEdit('파일 첨부');
                return true;
            }
            const ia = V.itemAdd(cmd);
            if (ia) {
                await toEdit(cmd);
                return true;
            }
        }
        const raw = V.resumeCmd(cmd);
        if (raw) {
            if (raw.act === 'new' || document.getElementById('newResumeModal')) {
                if (await resumeAct(raw) !== false) return true;
            } else {
                await navCmd('/resumes', cmd, '이력서 관리 화면에서 처리할게요');
                return true;
            }
        }
        return false;
    }

    Voice.onCommand(seekerCmd, cmd => !!(V.consultCmd(cmd) || V.messageCmd(cmd) || V.resumeCmd(cmd) || V.copyCmd(cmd)
        || V.itemCmd(cmd) || V.bookmarkCmd(cmd) || V.jobCmd(cmd) || V.statusCmd(cmd) || V.withdrawCmd(cmd)
        || V.proposalCmd(cmd) || V.scheduleCmd(cmd) || V.inboxCmd(cmd) || V.a11yCmd(cmd)
        || (!onEdit() && (V.secAdd(cmd) || V.fileCmd(cmd) || V.itemAdd(cmd)))));

    // 메뉴명/버튼명 완전일치가 모두 실패한 짧은 발화만 자격증명으로 간주함
    Voice.onLate(async cmd => {
        if (onEdit()) return false; // 작성 화면은 resume-voice.js가 처리함
        const words = cmd.trim().split(/\s+/).filter(Boolean);
        if (!words.length || words.length > 5) return false;
        const act = document.activeElement;
        if (act && act.matches('input, textarea, select') && act.closest('#main')) return false;
        const q = cmd.replace(/[1-3]급|일급|이급|삼급/g, '').trim();
        if (!q) return false;
        let list;
        try {
            const r = await fetch('/api/refs/certs?q=' + encodeURIComponent(q));
            if (!r.ok) return false;
            list = await r.json();
        } catch (e) {
            return false;
        }
        if (!V.certHit(q, list)) return false;
        await toEdit('자격증에 ' + cmd.trim() + ' 입력해줘');
        return true;
    });

    window.addEventListener('DOMContentLoaded', () => {
        const q = new URLSearchParams(location.search);
        // 다른 화면에서 새 이력서 명령으로 진입한 경우임. 새로고침 시 재실행되지 않도록 주소에서 제거함
        if (q.get('voice') === 'new' && document.getElementById('newResumeModal')) {
            history.replaceState(null, '', location.pathname);
            newResume();
            return;
        }
        if (location.pathname === '/jobs' && q.get('voice') === '1') {
            const fit = q.get('sort') === 'fit';
            q.delete('voice');
            history.replaceState(null, '', location.pathname + (q.toString() ? '?' + q : ''));
            announceJobs(fit);
            return;
        }
        if (location.pathname === '/applications' && q.get('voice') === 'read') {
            history.replaceState(null, '', location.pathname);
            statusRead();
            return;
        }
        const cmd = q.get('cmd');
        if (cmd) {
            history.replaceState(null, '', location.pathname);
            seekerCmd(cmd);
        }
    });
})();

(function() {
    const V = window.VoiceParse;
    const READ_MAX = 5;

    function tplData() {
        const el = document.getElementById('offerTplData');
        return el ? JSON.parse(el.textContent) : null;
    }

    // 번호는 읽어 준 범위 안에서만, 이름은 전체 목록에서 찾음
    function choose(ans, list, nameOf) {
        const s = V.squash(ans).replace(/(이에요|예요|이요|요)$/, '').replace(/님$/, '');
        const n = V.ORD[s.replace(/번째?$/, '')] || parseInt(s, 10);
        if (n >= 1 && n <= Math.min(list.length, READ_MAX)) return list[n - 1];
        const hit = list.filter(x => {
            const k = V.squash(nameOf(x));
            return k.includes(s) || s.includes(k);
        });
        return hit.length === 1 ? hit[0] : null;
    }

    async function askPick(intro, list, nameOf, q) {
        const more = list.length > READ_MAX ? '최근 ' + READ_MAX + '개만 읽을게요. ' : '';
        const names = list.slice(0, READ_MAX).map((x, i) => (i + 1) + '번 ' + nameOf(x)).join(', ');
        for (let i = 0; i < 2; i++) {
            const a = await Voice.ask((i ? '잘 못 알아들었어요. ' : intro + more + names + '. ') + q);
            if (a === null) return null;
            const hit = choose(a, list, nameOf);
            if (hit) return hit;
        }
        return null;
    }

    function cancel() {
        return Voice.speak('제안을 보내지 않았어요');
    }

    async function offer(o, cmd) {
        const tpls = tplData();
        const btns = [...document.querySelectorAll('[data-offer-url]')];
        // 추천 인재 목록과 양식이 있는 화면에서만 진행함
        if (!tpls || !btns.length && !document.getElementById('offerForm')) {
            await Voice.speak('추천 인재 화면으로 갈게요');
            location.href = '/company/recommendations?voice=' + encodeURIComponent(cmd);
            return;
        }
        if (!btns.length) return Voice.speak('채용매니저가 추천한 인재가 없어요');
        const label = b => b.dataset.name + (b.dataset.job ? ', ' + b.dataset.job : '');
        const cands = o.name ? btns.filter(b => {
            const k = V.squash(b.dataset.name);
            return k.includes(o.name) || o.name.includes(k);
        }) : btns;
        if (!cands.length) return Voice.speak('추천 인재 중에 ' + o.name + ' 님이 없어요');
        const who = cands.length === 1 ? cands[0]
            : await askPick('추천 인재가 ' + cands.length + '명 있어요. ', cands, label, '몇 번에게 보낼까요?');
        if (!who) return cancel();
        const name = who.dataset.name;
        if (who.dataset.offered) return Voice.speak(name + ' 님에게는 이미 제안을 보냈어요');

        if (!tpls.length) {
            const a = await Voice.ask('저장한 메시지 양식이 없어요. 메시지 양식 화면으로 갈까요?', true);
            if (a && V.yesno(a) === 'yes') location.href = '/company/offer-templates';
            else cancel();
            return;
        }
        let tpl = o.tpl && tpls.find(t => V.squash(t.name).includes(o.tpl) || o.tpl.includes(V.squash(t.name)));
        if (!tpl && tpls.length === 1) tpl = tpls[0];
        if (!tpl) tpl = await askPick('저장한 양식이 ' + tpls.length + '개 있어요. ', tpls, t => t.name, '어떤 양식으로 보낼까요?');
        if (!tpl) return cancel();

        const form = document.getElementById('offerForm');
        const vals = { 이름: name, 회사명: form.dataset.company, 공고명: who.dataset.job };
        // 자동으로 채우지 못한 치환 표시는 음성으로 받음
        for (const k of V.tplKeys(tpl.title + ' ' + tpl.message)) {
            if (vals[k]) continue;
            const a = await Voice.ask(tpl.name + ' 양식의 ' + k + '에 들어갈 내용을 말씀하세요');
            if (!a) return cancel();
            vals[k] = a.trim().replace(/[.!?]+$/, '');
        }
        const title = V.fillTpl(tpl.title, vals);
        const message = V.fillTpl(tpl.message, vals);

        const q = name + ' 님께 ' + tpl.name + ' 양식으로 보낼 제안이에요. 제목, ' + title + '. 내용, ' + message + '. 보낼까요?';
        for (;;) {
            const a = await Voice.ask(q);
            if (a && /다시|읽어/.test(V.squash(a))) continue;
            if (!a || V.yesno(a) !== 'yes') return cancel();
            break;
        }
        const fd = new FormData();
        fd.append('title', title);
        fd.append('message', message);
        fd.append('contact', tpl.contact || '');
        if (form.elements.next) fd.append('next', form.elements.next.value);
        fd.append('csrf_token', form.elements.csrf_token.value);
        const res = await fetch(who.dataset.offerUrl, { method: 'POST', body: fd });
        if (!res.ok) return Voice.speak('제안을 보내지 못했어요');
        await Voice.speak(name + ' 님께 제안을 보냈어요');
        location.href = res.url;
    }

    async function readTpls(cmd) {
        const tpls = tplData();
        if (!tpls) {
            await Voice.speak('메시지 양식 화면으로 갈게요');
            location.href = '/company/offer-templates?voice=' + encodeURIComponent(cmd);
            return;
        }
        if (!tpls.length) return Voice.speak('저장한 메시지 양식이 없어요');
        Voice.speak('저장한 양식이 ' + tpls.length + '개 있어요. ' + tpls.map((t, i) => (i + 1) + '번 ' + t.name).join(', '));
    }

    async function run(cmd) {
        if (V.tplListCmd(cmd)) {
            await readTpls(cmd);
            return true;
        }
        const o = V.offerCmd(cmd);
        if (!o) return false;
        await offer(o, cmd);
        return true;
    }

    Voice.onCommand(run, cmd => V.tplListCmd(cmd) || !!V.offerCmd(cmd));

    // 다른 화면에서 받은 명령을 이어서 실행함. 새로고침 시 재실행되지 않도록 주소에서 제거함
    const said = new URLSearchParams(location.search).get('voice');
    if (said && tplData()) {
        history.replaceState(null, '', location.pathname);
        run(said);
    }
})();

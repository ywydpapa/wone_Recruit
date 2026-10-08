(function() {
    const V = window.VoiceParse;
    const CATS = { job: '취업 상담', device: '보조장비', work: '근무 중 어려움', rights: '권익 보호', etc: '기타' };
    const METHODS = { phone: '전화', video: '화상', in_person: '대면', chat: '메시지' };
    const NONE = /^(없|상관없|아무때|아니|아뇨)/;

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

    Voice.onCommand(async cmd => {
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
        return false;
    });
})();

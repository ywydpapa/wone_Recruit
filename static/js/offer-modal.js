(function() {
    const modal = document.getElementById('offerModal');
    const form = document.getElementById('offerForm');
    const tpls = JSON.parse(document.getElementById('offerTplData').textContent);
    const sel = document.getElementById('offerTpl');
    const f = form.elements;
    let vals = { 회사명: form.dataset.company };

    // 제안 버튼마다 받는 사람과 공고가 다르므로 열 때 주소와 치환값을 지정함
    modal.addEventListener('show.bs.modal', e => {
        const b = e.relatedTarget;
        if (!b || !b.dataset.offerUrl) return;
        form.action = b.dataset.offerUrl;
        vals = { 이름: b.dataset.name, 회사명: form.dataset.company, 공고명: b.dataset.job };
        modal.querySelector('.modal-title').textContent = b.dataset.name + '님께 채용 제안하기';
    });

    if (sel) sel.addEventListener('change', () => {
        const t = tpls.find(x => String(x.id) === sel.value);
        if (!t) return;
        f.title.value = VoiceParse.fillTpl(t.title, vals);
        f.message.value = VoiceParse.fillTpl(t.message, vals);
        f.contact.value = t.contact;
    });

    // 받는 사람 이름 등은 다시 치환 표시로 되돌려 저장함
    const unfill = s => Object.entries(vals).reduce((acc, [k, v]) => v ? acc.split(v).join('{' + k + '}') : acc, s);

    document.getElementById('offerTplSave').addEventListener('click', async () => {
        const msg = document.getElementById('offerTplMsg');
        const name = document.getElementById('offerTplName').value.trim();
        if (!name || !f.title.value.trim() || !f.message.value.trim()) {
            msg.textContent = '양식 이름, 제목, 내용을 모두 입력해 주세요.';
            return;
        }
        const fd = new FormData();
        fd.append('name', name);
        fd.append('title', unfill(f.title.value));
        fd.append('message', unfill(f.message.value));
        fd.append('contact', f.contact.value);
        fd.append('ajax', '1');
        fd.append('csrf_token', f.csrf_token.value);
        const res = await fetch('/company/offer-templates', { method: 'POST', body: fd });
        msg.textContent = res.ok ? '양식을 저장했습니다.' : '양식을 저장하지 못했습니다.';
        if (!res.ok) return;
        const t = await res.json();
        tpls.unshift(t);
        if (sel) sel.add(new Option(t.name, t.id), 1);
    });
})();

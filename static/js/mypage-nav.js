(function() {
    const bar = document.getElementById('mypageResize');
    if (!bar) return;
    const root = document.documentElement;
    const nav = bar.parentElement;
    const MIN = 120, MAX = 280, DEF = 168;

    function setW(w, save) {
        w = Math.min(MAX, Math.max(MIN, Math.round(w)));
        root.style.setProperty('--mypage-nav-w', w + 'px');
        bar.setAttribute('aria-valuenow', w);
        if (save) localStorage.setItem('recruit_mypage_w', w);
    }

    bar.addEventListener('pointerdown', e => {
        e.preventDefault();
        bar.setPointerCapture(e.pointerId);
        const x0 = e.clientX, w0 = nav.offsetWidth;
        root.classList.add('mypage-resizing');
        const move = ev => setW(w0 + ev.clientX - x0);
        // 캡처 해제 시점을 종료 기준으로 함. 창 밖 놓기, 포커스 이탈 시 pointerup 누락 대응
        const up = () => {
            bar.removeEventListener('pointermove', move);
            bar.removeEventListener('lostpointercapture', up);
            root.classList.remove('mypage-resizing');
            setW(nav.offsetWidth, true);
        };
        bar.addEventListener('pointermove', move);
        bar.addEventListener('lostpointercapture', up);
    });
    // 드래그 불가 사용자 대응. WCAG 2.5.7 기준
    bar.addEventListener('keydown', e => {
        const step = { ArrowLeft: -10, ArrowRight: 10 }[e.key];
        if (e.key === 'Home') setW(MIN, true);
        else if (e.key === 'End') setW(MAX, true);
        else if (step) setW(nav.offsetWidth + step, true);
        else return;
        e.preventDefault();
    });
    bar.addEventListener('dblclick', () => {
        root.style.removeProperty('--mypage-nav-w');
        localStorage.removeItem('recruit_mypage_w');
        bar.setAttribute('aria-valuenow', DEF);
    });
    bar.setAttribute('aria-valuenow', nav.offsetWidth);
})();

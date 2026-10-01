(function() {
    var DEBOUNCE = 200;

    var CONFIGS = {
        cert_name: {
            url: '/api/refs/certs',
            label: function(r) { return r.org ? r.name + ' (' + r.org + ')' : r.name; },
            apply: function(input, r) {
                var row = input.closest('.cert-row');
                var org = row && row.querySelector('input[name="cert_org"]');
                if (org && r.org) org.value = r.org;
            }
        },
        edu_school: {
            url: '/api/refs/schools',
            label: function(r) { return r.name + ' (' + r.level + ')'; },
            apply: function(input, r) {
                var row = input.closest('.edu-row');
                var level = row && row.querySelector('select[name="edu_level"]');
                if (level) level.value = r.level;
            }
        }
    };

    var state = new WeakMap();
    var timers = new WeakMap();
    var seq = 0;

    function cfgFor(input) {
        return input && input.tagName === 'INPUT' ? CONFIGS[input.name] : null;
    }

    function announce(msg) {
        var live = document.getElementById('srLive');
        if (live) live.textContent = msg;
    }

    function ensureSetup(input) {
        if (state.has(input)) return state.get(input);

        var wrap = document.createElement('div');
        wrap.className = 'ref-combo-wrap';
        input.parentNode.insertBefore(wrap, input);
        wrap.appendChild(input);

        var listId = 'refCombo' + (seq++) + 'List';
        var list = document.createElement('ul');
        list.className = 'ref-combo-list d-none';
        list.id = listId;
        list.setAttribute('role', 'listbox');
        wrap.appendChild(list);

        input.setAttribute('role', 'combobox');
        input.setAttribute('aria-autocomplete', 'list');
        input.setAttribute('aria-haspopup', 'listbox');
        input.setAttribute('aria-expanded', 'false');
        input.setAttribute('aria-controls', listId);
        input.setAttribute('autocomplete', 'off');

        var st = { listEl: list, items: [], activeIndex: -1 };
        state.set(input, st);
        return st;
    }

    function optionId(list, idx) {
        return list.id + '-opt-' + idx;
    }

    function renderList(input, cfg, st) {
        var list = st.listEl;
        list.innerHTML = '';
        st.items.forEach(function(item, idx) {
            var li = document.createElement('li');
            li.id = optionId(list, idx);
            li.setAttribute('role', 'option');
            li.setAttribute('aria-selected', 'false');
            if (item.literal) {
                li.className = 'ref-combo-literal';
                li.textContent = "'" + item.q + "' 직접 입력";
            } else {
                li.textContent = cfg.label(item.data);
            }
            list.appendChild(li);
        });
    }

    function openList(input, st) {
        st.listEl.classList.remove('d-none');
        input.setAttribute('aria-expanded', 'true');
    }

    function closeList(input) {
        var st = state.get(input);
        if (!st) return;
        st.listEl.classList.add('d-none');
        st.listEl.innerHTML = '';
        st.items = [];
        st.activeIndex = -1;
        input.removeAttribute('aria-activedescendant');
        input.setAttribute('aria-expanded', 'false');
    }

    function setActive(input, st, idx) {
        var opts = st.listEl.querySelectorAll('li');
        opts.forEach(function(li) { li.classList.remove('active'); li.setAttribute('aria-selected', 'false'); });
        st.activeIndex = idx;
        if (idx >= 0 && opts[idx]) {
            opts[idx].classList.add('active');
            opts[idx].setAttribute('aria-selected', 'true');
            opts[idx].scrollIntoView({ block: 'nearest' });
            input.setAttribute('aria-activedescendant', opts[idx].id);
        } else {
            input.removeAttribute('aria-activedescendant');
        }
    }

    function moveActive(input, st, dir) {
        var n = st.items.length;
        if (!n) return;
        var next = st.activeIndex + dir;
        if (next < 0) next = n - 1;
        if (next >= n) next = 0;
        setActive(input, st, next);
    }

    function selectItem(input, st, idx) {
        var item = st.items[idx];
        if (!item) return;
        if (item.literal) {
            input.value = item.q;
        } else {
            var cfg = cfgFor(input);
            input.value = item.data.name;
            cfg.apply(input, item.data);
        }
        closeList(input);
        input.focus();
    }

    function showResults(input, cfg, st, q, results) {
        st.items = results.slice(0, 10).map(function(r) { return { data: r }; });
        st.items.push({ literal: true, q: q });
        renderList(input, cfg, st);
        setActive(input, st, -1);
        openList(input, st);
        announce(results.length + '건 검색됨');
    }

    function search(input, cfg, st, q) {
        fetch(cfg.url + '?q=' + encodeURIComponent(q))
            .then(function(res) { return res.ok ? res.json() : []; })
            .then(function(results) { showResults(input, cfg, st, q, results); })
            .catch(function() { showResults(input, cfg, st, q, []); });
    }

    // 음성 입력용임. 1건으로 일치하면 바로 선택하고, 아니면 후보 목록을 표시함
    window.refResolve = function(input) {
        var cfg = cfgFor(input);
        var q = input.value.trim();
        if (!cfg || !q) return;
        var st = ensureSetup(input);
        var key = q.replace(/\s/g, '');
        fetch(cfg.url + '?q=' + encodeURIComponent(q))
            .then(function(res) { return res.ok ? res.json() : []; })
            .catch(function() { return []; })
            .then(function(results) {
                var exact = results.filter(function(r) { return r.name.replace(/\s/g, '') === key; });
                var hit = exact.length === 1 ? exact[0] : results.length === 1 ? results[0] : null;
                if (hit) {
                    input.value = hit.name;
                    cfg.apply(input, hit);
                    return;
                }
                input.focus();
                showResults(input, cfg, st, q, results);
            });
    };

    document.addEventListener('focusin', function(e) {
        var cfg = cfgFor(e.target);
        if (!cfg) return;
        ensureSetup(e.target);
    });

    document.addEventListener('input', function(e) {
        var input = e.target;
        var cfg = cfgFor(input);
        if (!cfg) return;
        var st = ensureSetup(input);

        clearTimeout(timers.get(input));
        var q = input.value.trim();
        if (!q) {
            closeList(input);
            return;
        }
        timers.set(input, setTimeout(function() { search(input, cfg, st, q); }, DEBOUNCE));
    });

    document.addEventListener('keydown', function(e) {
        var input = e.target;
        var cfg = cfgFor(input);
        if (!cfg) return;
        var st = state.get(input);
        if (!st || st.listEl.classList.contains('d-none')) return;

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            moveActive(input, st, 1);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            moveActive(input, st, -1);
        } else if (e.key === 'Enter') {
            if (st.activeIndex >= 0) {
                e.preventDefault();
                selectItem(input, st, st.activeIndex);
            }
        } else if (e.key === 'Escape') {
            closeList(input);
        }
    });

    // 옵션 클릭 시 input blur로 목록이 먼저 닫히지 않도록 mousedown에서 차단함
    document.addEventListener('mousedown', function(e) {
        if (e.target.closest('.ref-combo-list li')) e.preventDefault();
    });

    document.addEventListener('click', function(e) {
        var li = e.target.closest('.ref-combo-list li');
        if (!li) return;
        var wrap = li.closest('.ref-combo-wrap');
        var input = wrap && wrap.querySelector('[role="combobox"]');
        if (!input) return;
        var st = state.get(input);
        var idx = Array.prototype.indexOf.call(li.parentNode.children, li);
        selectItem(input, st, idx);
    });

    document.addEventListener('focusout', function(e) {
        var input = e.target;
        var cfg = cfgFor(input);
        if (!cfg) return;
        var wrap = input.closest('.ref-combo-wrap');
        setTimeout(function() {
            if (!wrap.contains(document.activeElement)) closeList(input);
        }, 0);
    });
}());

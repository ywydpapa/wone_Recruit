(function () {
    var show = document.getElementById('pwShow');
    if (!show) return;
    var form = show.form;
    var fields = form.querySelectorAll('input[type=password]');
    show.addEventListener('change', function () {
        fields.forEach(function (f) { f.type = show.checked ? 'text' : 'password'; });
    });

    var pw = form.querySelector('[data-pw-new]');
    var cf = form.querySelector('[data-pw-confirm]');
    var msg = document.getElementById('pwMatch');
    function check() {
        if (!cf.value) {
            msg.textContent = '';
            return;
        }
        var ok = cf.value === pw.value;
        msg.textContent = ok ? '비밀번호가 일치합니다.' : '비밀번호가 일치하지 않습니다.';
        msg.className = 'small ' + (ok ? 'text-success' : 'text-danger');
    }
    pw.addEventListener('input', check);
    cf.addEventListener('input', check);
})();

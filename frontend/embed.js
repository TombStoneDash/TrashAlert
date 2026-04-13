/**
 * TrashAlert Embeddable Widget
 *
 * Drop into any tenant portal:
 *   <div id="trashalert-widget" data-city="san_diego"></div>
 *   <script src="https://trashalert.io/embed.js"></script>
 *
 * Options (data attributes on the container div):
 *   data-city      City slug (default: "san_diego")
 *   data-theme     "dark" or "light" (default: "light")
 *   data-api-base  Override API base URL (default: same origin / trashalert.io)
 */
(function () {
  'use strict';

  var container = document.getElementById('trashalert-widget');
  if (!container) return;

  var city = container.getAttribute('data-city') || 'san_diego';
  var theme = container.getAttribute('data-theme') || 'light';
  var apiBase = container.getAttribute('data-api-base') || 'https://trashalert.io';

  var isDark = theme === 'dark';
  var bg = isDark ? '#1e293b' : '#ffffff';
  var text = isDark ? '#e2e8f0' : '#1e293b';
  var muted = isDark ? '#94a3b8' : '#64748b';
  var border = isDark ? 'rgba(255,255,255,0.1)' : '#e2e8f0';
  var accent = '#22c55e';
  var inputBg = isDark ? '#0f172a' : '#f8fafc';

  container.innerHTML = ''
    + '<div style="font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;'
    + 'background:' + bg + ';border:1px solid ' + border + ';border-radius:12px;padding:24px;max-width:420px;">'
    + '<div style="font-size:16px;font-weight:700;color:' + text + ';margin-bottom:4px;">'
    + '\uD83D\uDDD1\uFE0F TrashAlert</div>'
    + '<div style="font-size:13px;color:' + muted + ';margin-bottom:16px;">Find your pickup schedule</div>'
    + '<form id="ta-form" style="display:flex;gap:8px;margin-bottom:12px;">'
    + '<input id="ta-input" type="text" placeholder="Enter your address" '
    + 'style="flex:1;padding:10px 14px;border:1px solid ' + border + ';border-radius:8px;'
    + 'background:' + inputBg + ';color:' + text + ';font-size:14px;outline:none;" />'
    + '<button type="submit" style="padding:10px 18px;border:none;border-radius:8px;'
    + 'background:' + accent + ';color:#fff;font-size:14px;font-weight:600;cursor:pointer;">Look Up</button>'
    + '</form>'
    + '<div id="ta-result" style="display:none;padding:16px;background:' + inputBg + ';'
    + 'border-radius:8px;border:1px solid ' + border + ';">'
    + '<div id="ta-day" style="font-size:24px;font-weight:800;color:' + accent + ';"></div>'
    + '<div id="ta-detail" style="font-size:13px;color:' + muted + ';margin-top:4px;"></div>'
    + '</div>'
    + '<div id="ta-error" style="display:none;padding:12px;color:#ef4444;font-size:13px;"></div>'
    + '<div style="margin-top:12px;text-align:right;">'
    + '<a href="https://trashalert.io/' + city + '" target="_blank" rel="noopener" '
    + 'style="font-size:11px;color:' + muted + ';text-decoration:none;">'
    + 'Powered by TrashAlert</a></div>'
    + '</div>';

  var form = document.getElementById('ta-form');
  var input = document.getElementById('ta-input');
  var result = document.getElementById('ta-result');
  var dayEl = document.getElementById('ta-day');
  var detailEl = document.getElementById('ta-detail');
  var errorEl = document.getElementById('ta-error');

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var addr = input.value.trim();
    if (!addr) return;

    result.style.display = 'none';
    errorEl.style.display = 'none';
    dayEl.textContent = 'Looking up\u2026';
    result.style.display = 'block';

    var url = apiBase + '/api/lookup?address=' + encodeURIComponent(addr) + '&city=' + encodeURIComponent(city);

    fetch(url)
      .then(function (res) { return res.json().then(function (d) { return { ok: res.ok, data: d }; }); })
      .then(function (r) {
        if (!r.ok) throw new Error(r.data.detail || 'Not found');
        dayEl.textContent = r.data.pickup_day;
        detailEl.textContent = r.data.address + ' \u2014 ' + r.data.zone + ' \u2014 Next: ' + r.data.next_pickup;
      })
      .catch(function (err) {
        result.style.display = 'none';
        errorEl.style.display = 'block';
        errorEl.textContent = err.message;
      });
  });
})();

/**
 * MaterialHub Workspace UX helpers
 * - Active sidebar highlighting
 * - Dark mode toggle
 * - Button loading states
 */
(function () {
  function highlightActiveNav() {
    const path = window.location.pathname.replace(/\/$/, '') || '/';
    document.querySelectorAll('.mh-nav a').forEach(function (link) {
      const href = (link.getAttribute('href') || '').replace(/\/$/, '') || '/';
      if (href === path || (href !== '/' && path.indexOf(href) === 0)) {
        link.classList.add('active');
      } else {
        link.classList.remove('active');
      }
    });
  }

  function initDarkMode() {
    const stored = localStorage.getItem('mh-theme');
    const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    const theme = stored || (prefersDark ? 'dark' : 'light');
    document.documentElement.setAttribute('data-theme', theme);

    // Inject toggle into topbar if authenticated
    const actions = document.querySelector('.mh-top-actions');
    if (actions && !document.getElementById('mh-theme-toggle')) {
      const btn = document.createElement('button');
      btn.id = 'mh-theme-toggle';
      btn.type = 'button';
      btn.className = 'mh-pill mh-theme-toggle';
      btn.setAttribute('aria-label', 'Toggle dark mode');
      btn.innerHTML = theme === 'dark'
        ? '<i class="fas fa-sun"></i>'
        : '<i class="fas fa-moon"></i>';
      btn.addEventListener('click', function () {
        const current = document.documentElement.getAttribute('data-theme') || 'light';
        const next = current === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', next);
        localStorage.setItem('mh-theme', next);
        btn.innerHTML = next === 'dark'
          ? '<i class="fas fa-sun"></i>'
          : '<i class="fas fa-moon"></i>';
      });
      actions.insertBefore(btn, actions.firstChild);
    }
  }

  function initLoadingButtons() {
    document.addEventListener('submit', function (e) {
      const form = e.target;
      if (!(form instanceof HTMLFormElement)) return;
      const btn = form.querySelector('button[type="submit"], input[type="submit"]');
      if (!btn || btn.disabled || btn.classList.contains('mh-loading')) return;
      btn.classList.add('mh-loading');
      btn.disabled = true;
      const original = btn.innerHTML;
      btn.dataset.originalHtml = original;
      if (btn.tagName === 'BUTTON') {
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> ' + (btn.textContent.trim() || 'Working…');
      }
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    highlightActiveNav();
    initDarkMode();
    initLoadingButtons();
  });
})();

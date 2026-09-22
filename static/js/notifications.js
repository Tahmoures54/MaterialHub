/**
 * MaterialHub Toast Notifications
 * Converts flash messages into non-blocking, auto-dismiss toasts.
 */
(function () {
  function ensureContainer() {
    let el = document.getElementById('mh-toast-container');
    if (!el) {
      el = document.createElement('div');
      el.id = 'mh-toast-container';
      el.className = 'mh-toast-container';
      el.setAttribute('aria-live', 'polite');
      el.setAttribute('aria-atomic', 'true');
      document.body.appendChild(el);
    }
    return el;
  }

  function showToast(message, category, duration) {
    category = category || 'info';
    duration = duration || 4500;
    const container = ensureContainer();

    const toast = document.createElement('div');
    toast.className = 'mh-toast mh-toast-' + category;
    toast.setAttribute('role', 'status');

    const icons = {
      success: 'fa-check-circle',
      danger: 'fa-exclamation-circle',
      warning: 'fa-exclamation-triangle',
      info: 'fa-info-circle',
      message: 'fa-info-circle',
      error: 'fa-exclamation-circle'
    };
    const icon = icons[category] || icons.info;

    toast.innerHTML =
      '<i class="fas ' + icon + ' mh-toast-icon" aria-hidden="true"></i>' +
      '<span class="mh-toast-text"></span>' +
      '<button type="button" class="mh-toast-close" aria-label="Dismiss">&times;</button>';

    toast.querySelector('.mh-toast-text').textContent = message;

    const close = function () {
      toast.classList.add('mh-toast-out');
      setTimeout(function () {
        if (toast.parentNode) toast.parentNode.removeChild(toast);
      }, 220);
    };

    toast.querySelector('.mh-toast-close').addEventListener('click', close);
    container.appendChild(toast);

    // Force reflow then show
    void toast.offsetWidth;
    toast.classList.add('mh-toast-in');

    if (duration > 0) {
      setTimeout(close, duration);
    }
  }

  // Convert existing flash alerts into toasts
  document.addEventListener('DOMContentLoaded', function () {
    const flashes = document.querySelectorAll('.mh-flashes .mh-alert');
    flashes.forEach(function (alert) {
      let cat = 'info';
      alert.classList.forEach(function (c) {
        if (c.indexOf('mh-alert-') === 0) {
          cat = c.replace('mh-alert-', '');
        }
      });
      const text = (alert.textContent || '').trim();
      if (text) showToast(text, cat);
      alert.style.display = 'none';
    });
  });

  // Expose for programmatic use
  window.mhToast = showToast;
})();

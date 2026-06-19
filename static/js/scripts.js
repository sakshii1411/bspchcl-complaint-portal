document.addEventListener('DOMContentLoaded', function () {

  // ── Loading overlay ────────────────────────────────────────────────────────
  const overlay = document.getElementById('loading-overlay');
  document.querySelectorAll('form.show-loading').forEach(form => {
    form.addEventListener('submit', function () {
      if (overlay) overlay.classList.add('active');
    });
  });

  // ── Sidebar hamburger ──────────────────────────────────────────────────────
  const hamburger = document.getElementById('hamburger');
  const sidebar = document.getElementById('sidebar');
  const sidebarOverlay = document.getElementById('sidebarOverlay');
  if (hamburger && sidebar) {
    hamburger.addEventListener('click', function () {
      sidebar.classList.toggle('open');
      if (sidebarOverlay) sidebarOverlay.classList.toggle('active');
    });
    if (sidebarOverlay) {
      sidebarOverlay.addEventListener('click', function () {
        sidebar.classList.remove('open');
        sidebarOverlay.classList.remove('active');
      });
    }
  }

  // ── Toggle password visibility ─────────────────────────────────────────────
  document.querySelectorAll('.toggle-password').forEach(toggle => {
    toggle.style.cursor = 'pointer';
    toggle.addEventListener('click', function () {
      const input = document.getElementById(this.getAttribute('data-target'));
      if (!input) return;
      const isPass = input.type === 'password';
      input.type = isPass ? 'text' : 'password';
      this.innerHTML = isPass
        ? '<i class="bi bi-eye-slash"></i>'
        : '<i class="bi bi-eye"></i>';
    });
  });

  // ── Confirm dialogs ────────────────────────────────────────────────────────
  document.querySelectorAll('[data-confirm]').forEach(el => {
    el.addEventListener('click', function (e) {
      if (!confirm(this.getAttribute('data-confirm') || 'Are you sure?')) {
        e.preventDefault();
      }
    });
  });

  // ── Auto-dismiss flash alerts after 6 seconds ──────────────────────────────
  document.querySelectorAll('.flash-alert').forEach(alert => {
    // Don't auto-dismiss OTP alerts — user needs to read the code
    if (alert.textContent.includes('OTP is:')) return;
    setTimeout(() => {
      alert.style.transition = 'opacity 0.5s';
      alert.style.opacity = '0';
      setTimeout(() => alert.remove(), 500);
    }, 6000);
  });

  // ── Notification badge (live count) ───────────────────────────────────────
  function updateNotifBadge() {
    fetch('/api/notif-count')
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (!data) return;
        const dot  = document.getElementById('notif-dot');
        const badge = document.getElementById('notif-badge');
        if (data.count > 0) {
          if (dot)  { dot.style.display = 'block'; }
          if (badge){ badge.textContent = data.count > 99 ? '99+' : data.count; badge.style.display = 'inline-flex'; }
        } else {
          if (dot)  dot.style.display  = 'none';
          if (badge) badge.style.display = 'none';
        }
      })
      .catch(() => {});
  }
  // Only poll if user is logged in (badge elements exist)
  if (document.getElementById('notif-dot')) {
    updateNotifBadge();
    setInterval(updateNotifBadge, 60000); // refresh every 60s
  }

  // ── OTP input: auto-format (numbers only, 6 digits) ───────────────────────
  const otpInput = document.querySelector('input[name="otp"]');
  if (otpInput) {
    otpInput.addEventListener('input', function () {
      this.value = this.value.replace(/\D/g, '').slice(0, 6);
    });
    otpInput.addEventListener('paste', function (e) {
      e.preventDefault();
      const pasted = (e.clipboardData || window.clipboardData).getData('text');
      this.value = pasted.replace(/\D/g, '').slice(0, 6);
    });
  }

  // ── Select-all checkbox for admin tables ──────────────────────────────────
  const selectAll = document.getElementById('select-all');
  if (selectAll) {
    selectAll.addEventListener('change', function () {
      document.querySelectorAll('input[name="complaint_ids"]')
        .forEach(cb => { cb.checked = this.checked; });
    });
  }

  // ── FAQ accordion ──────────────────────────────────────────────────────────
  document.querySelectorAll('.faq-question').forEach(q => {
    q.addEventListener('click', function () {
      const item = this.closest('.faq-item');
      const wasOpen = item.classList.contains('open');
      document.querySelectorAll('.faq-item.open').forEach(i => i.classList.remove('open'));
      if (!wasOpen) item.classList.add('open');
    });
  });

});

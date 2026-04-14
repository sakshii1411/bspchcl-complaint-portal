document.addEventListener('DOMContentLoaded', function () {
  const overlay = document.getElementById('loading-overlay');
  document.querySelectorAll('form.show-loading').forEach(form => {
    form.addEventListener('submit', function () {
      if (overlay) overlay.classList.add('active');
    });
  });

  const hamburger = document.getElementById('hamburger');
  const sidebar = document.getElementById('sidebar');
  const sidebarOverlay = document.getElementById('sidebarOverlay');

  if (hamburger && sidebar && sidebarOverlay) {
    hamburger.addEventListener('click', function () {
      sidebar.classList.toggle('open');
      sidebarOverlay.classList.toggle('active');
    });

    sidebarOverlay.addEventListener('click', function () {
      sidebar.classList.remove('open');
      sidebarOverlay.classList.remove('active');
    });
  }

  document.querySelectorAll('[data-confirm]').forEach(el => {
    el.addEventListener('click', function (e) {
      const msg = this.getAttribute('data-confirm') || 'Are you sure?';
      if (!confirm(msg)) {
        e.preventDefault();
      }
    });
  });

  document.querySelectorAll('.toggle-password').forEach(toggle => {
    toggle.style.cursor = 'pointer';
    toggle.addEventListener('click', function () {
      const targetId = this.getAttribute('data-target');
      const input = document.getElementById(targetId);
      if (!input) return;

      if (input.type === 'password') {
        input.type = 'text';
        this.innerHTML = '<i class="bi bi-eye-slash"></i>';
      } else {
        input.type = 'password';
        this.innerHTML = '<i class="bi bi-eye"></i>';
      }
    });
  });
});

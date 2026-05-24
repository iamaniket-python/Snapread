/* ═══════════════════════════════════════
   main.js — Medium Clone
═══════════════════════════════════════ */

// ── Dropdown toggle ──────────────────────
function toggleDropdown() {
  document.getElementById('navDropdown').classList.toggle('open');
}

document.addEventListener('click', function (e) {
  const wrap = document.querySelector('.nav-avatar-wrap');
  if (wrap && !wrap.contains(e.target)) {
    const dd = document.getElementById('navDropdown');
    if (dd) dd.classList.remove('open');
  }
});


// ── Auto-dismiss flash messages ──────────
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.alert').forEach(alert => {
    setTimeout(() => alert.remove(), 4000);
  });
});


// ── Confirm delete forms ─────────────────
document.querySelectorAll('form[data-confirm]').forEach(form => {
  form.addEventListener('submit', function (e) {
    if (!confirm(this.dataset.confirm)) e.preventDefault();
  });
});


// ── Clap button animation ────────────────
const clapBtn = document.querySelector('.clap-btn');
if (clapBtn) {
  clapBtn.addEventListener('click', function () {
    this.classList.add('active');
    this.style.transform = 'scale(1.25)';
    setTimeout(() => { this.style.transform = 'scale(1)'; }, 200);
  });
}


// ── Lazy load images ─────────────────────
if ('IntersectionObserver' in window) {
  const imgs = document.querySelectorAll('img[data-src]');
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.src = entry.target.dataset.src;
        observer.unobserve(entry.target);
      }
    });
  });
  imgs.forEach(img => observer.observe(img));
}


// ── Reading progress bar ─────────────────
const postBody = document.querySelector('.post-body');
if (postBody) {
  const bar = document.createElement('div');
  bar.style.cssText = 'position:fixed;top:0;left:0;height:3px;background:#000;z-index:999;width:0%;transition:width .1s linear;';
  document.body.appendChild(bar);

  window.addEventListener('scroll', () => {
    const scrolled = window.scrollY;
    const total    = document.body.scrollHeight - window.innerHeight;
    bar.style.width = Math.min(100, (scrolled / total) * 100) + '%';
  });
}


// ── Back to top ──────────────────────────
const backBtn = document.createElement('button');
backBtn.innerHTML = '↑';
backBtn.title     = 'Back to top';
backBtn.style.cssText = [
  'position:fixed', 'bottom:80px', 'right:24px',
  'width:40px', 'height:40px', 'border-radius:50%',
  'background:var(--black)', 'color:var(--white)',
  'font-size:18px', 'display:none', 'align-items:center',
  'justify-content:center', 'z-index:50', 'box-shadow:0 2px 8px rgba(0,0,0,.2)',
  'cursor:pointer', 'border:none'
].join(';');

backBtn.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));
document.body.appendChild(backBtn);

window.addEventListener('scroll', () => {
  backBtn.style.display = window.scrollY > 400 ? 'flex' : 'none';
});
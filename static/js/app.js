/*
 * app.js - the small amount of vanilla JavaScript that keeps the original
 * frontend behaviour now that React, Radix UI, framer-motion and sonner are gone.
 *
 *   1. Toasts            (was: sonner)
 *   2. Scroll animations (was: framer-motion)
 *   3. Mobile menu       (was: Header.tsx useState)
 *   4. Select dropdowns  (was: Radix <Select>)
 *   5. Confirm dialogs   (was: Radix <AlertDialog>)
 *   6. Date formatting   (was: toLocaleDateString / toLocaleString)
 *   7. Home page comments (was: CommentSection in Index.tsx)
 *   8. Submit / Track / Login / Admin page behaviour
 *
 * All data lives on the server (Flask + SQLite); this file only handles the UI.
 */
(function () {
  'use strict';

  var $ = function (sel, root) { return (root || document).querySelector(sel); };
  var $$ = function (sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); };

  // Tiny element builder:  el('div', 'class names', { attr: 'x' }, child, child...)
  function el(tag, cls, attrs) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (attrs) Object.keys(attrs).forEach(function (k) {
      if (k === 'text') node.textContent = attrs[k];
      else if (k === 'html') node.innerHTML = attrs[k];
      else node.setAttribute(k, attrs[k]);
    });
    for (var i = 3; i < arguments.length; i++) {
      var c = arguments[i];
      if (c == null) continue;
      node.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    }
    return node;
  }

  var csrfToken = function () {
    var m = $('meta[name="csrf-token"]');
    return m ? m.content : '';
  };

  // ------------------------------------------------------------------
  // 1. Toasts (look and timing follow the sonner defaults)
  // ------------------------------------------------------------------
  var ICON_SUCCESS =
    '<svg viewBox="0 0 20 20" fill="currentColor" height="20" width="20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clip-rule="evenodd"></path></svg>';
  var ICON_ERROR =
    '<svg viewBox="0 0 20 20" fill="currentColor" height="20" width="20"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd"></path></svg>';

  function showToast(type, message) {
    var host = $('#toaster');
    if (!host) return;
    var li = el('li', 'toast group', { 'data-sonner-toast': '', 'data-styled': 'true', 'data-type': type, role: 'status' },
      el('div', null, { 'data-icon': '', html: type === 'error' ? ICON_ERROR : ICON_SUCCESS }),
      el('div', null, { 'data-content': '' }, el('div', null, { 'data-title': '', text: message }))
    );
    host.appendChild(li);
    requestAnimationFrame(function () { requestAnimationFrame(function () { li.setAttribute('data-mounted', 'true'); }); });
    setTimeout(function () {
      li.removeAttribute('data-mounted');
      li.setAttribute('data-removed', 'true');
      setTimeout(function () { li.remove(); }, 400);
    }, 4000);
  }
  var toast = {
    success: function (m) { showToast('success', m); },
    error: function (m) { showToast('error', m); }
  };

  // Messages queued by Flask (flash()) are shown as toasts on page load.
  try {
    var flashes = JSON.parse(($('#flash-data') || {}).textContent || '[]');
    flashes.forEach(function (f) { showToast(f[0] === 'error' ? 'error' : 'success', f[1]); });
  } catch (e) { /* ignore */ }

  // ------------------------------------------------------------------
  // 2. Scroll / load animations (framer-motion initial/animate/whileInView)
  // ------------------------------------------------------------------
  function initReveal() {
    var items = $$('[data-reveal]');
    if (!items.length) return;

    function play(node) {
      var dur = parseFloat(node.getAttribute('data-dur') || '0.3');
      var delay = parseFloat(node.getAttribute('data-delay') || '0');
      node.style.setProperty('--rv-dur', dur + 's');
      node.style.setProperty('--rv-delay', delay + 's');
      node.classList.add('is-in');
      // When finished, drop the helper styles so hover transitions etc. work normally.
      setTimeout(function () {
        node.removeAttribute('data-reveal');
        node.classList.remove('is-in');
        ['--rv-dur', '--rv-delay', '--rv-y', '--rv-s'].forEach(function (p) { node.style.removeProperty(p); });
      }, (dur + delay) * 1000 + 80);
    }

    var io = 'IntersectionObserver' in window ? new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { io.unobserve(e.target); play(e.target); }
      });
    }, { threshold: 0 }) : null;

    items.forEach(function (node) {
      node.style.setProperty('--rv-y', node.getAttribute('data-y') || '0');
      node.style.setProperty('--rv-s', node.getAttribute('data-scale') || '1');
      if (node.getAttribute('data-reveal') === 'view' && io) io.observe(node);
      else requestAnimationFrame(function () { requestAnimationFrame(function () { play(node); }); });
    });
  }

  // ------------------------------------------------------------------
  // 3. Mobile menu
  // ------------------------------------------------------------------
  function initMobileMenu() {
    var btn = $('#mobile-menu-toggle'), menu = $('#mobile-menu');
    if (!btn || !menu) return;
    btn.addEventListener('click', function () {
      var open = menu.classList.toggle('hidden') === false;
      $('[data-menu-open]', btn).classList.toggle('hidden', open);
      $('[data-menu-close]', btn).classList.toggle('hidden', !open);
      btn.setAttribute('aria-expanded', String(open));
    });
  }

  // ------------------------------------------------------------------
  // 4. Select dropdowns (Radix <Select>, position="popper")
  // ------------------------------------------------------------------
  var CHECK_ICON =
    '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-check h-4 w-4"><path d="M20 6 9 17l-5-5"></path></svg>';

  function initSelect(trigger) {
    var input = trigger.nextElementSibling;               // hidden <input>
    var list = input.nextElementSibling;                  // hidden <ul> of options
    var labelEl = $('[data-select-label]', trigger);
    var options = $$('li', list).map(function (li) { return { value: li.dataset.value, label: li.textContent }; });
    var wrapper = null, content = null, items = [], closing = false;

    function setValue(value) {
      var changed = input.value !== value;
      input.value = value;
      var opt = options.filter(function (o) { return o.value === value; })[0];
      labelEl.textContent = opt ? opt.label : labelEl.getAttribute('data-placeholder');
      if (changed) {
        input.dispatchEvent(new Event('change', { bubbles: true }));
        if (trigger.hasAttribute('data-autosubmit')) {
          var form = trigger.closest('form');
          if (form) form.submit();
        }
      }
    }

    function position() {
      var r = trigger.getBoundingClientRect();
      wrapper.style.minWidth = r.width + 'px';
      wrapper.style.left = Math.max(0, r.left) + 'px';
      var h = wrapper.offsetHeight;
      var below = window.innerHeight - r.bottom, above = r.top;
      if (below < h + 8 && above > below) {
        wrapper.style.top = Math.max(0, r.top - h) + 'px';
        content.setAttribute('data-side', 'top');
      } else {
        wrapper.style.top = r.bottom + 'px';
        content.setAttribute('data-side', 'bottom');
      }
    }

    function focusItem(i) {
      if (!items.length) return;
      i = (i + items.length) % items.length;
      items[i].focus();
    }

    function open() {
      if (wrapper) return;
      closing = false;
      wrapper = el('div', null, { 'data-select-wrapper': '' });
      content = el('div', 'ui-select-content relative z-50 max-h-96 min-w-[8rem] overflow-hidden rounded-md border bg-popover text-popover-foreground shadow-md',
        { 'data-state': 'open', 'data-side': 'bottom', role: 'listbox' });
      var viewport = el('div', 'p-1 w-full');
      viewport.style.minWidth = trigger.offsetWidth + 'px';
      viewport.style.overflowY = 'auto';
      viewport.style.maxHeight = 'inherit';
      items = options.map(function (o) {
        var selected = o.value === input.value;
        var item = el('div', 'relative flex w-full cursor-default select-none items-center rounded-sm py-1.5 pl-8 pr-2 text-sm outline-none focus:bg-accent focus:text-accent-foreground',
          { role: 'option', tabindex: '-1', 'data-value': o.value, 'aria-selected': String(selected) },
          el('span', 'absolute left-2 flex h-3.5 w-3.5 items-center justify-center', { html: selected ? CHECK_ICON : '' }),
          o.label);
        item.addEventListener('pointermove', function () { if (document.activeElement !== item) item.focus(); });
        item.addEventListener('click', function () { setValue(o.value); close(); });
        viewport.appendChild(item);
        return item;
      });
      content.appendChild(viewport);
      wrapper.appendChild(content);
      document.body.appendChild(wrapper);
      trigger.setAttribute('aria-expanded', 'true');
      trigger.setAttribute('data-state', 'open');
      position();
      var sel = items.filter(function (it) { return it.getAttribute('aria-selected') === 'true'; })[0];
      (sel || items[0]).focus();

      setTimeout(function () {
        document.addEventListener('pointerdown', outside, true);
      }, 0);
      document.addEventListener('keydown', onKey, true);
      window.addEventListener('resize', close);
    }

    function close() {
      if (!wrapper || closing) return;
      closing = true;
      document.removeEventListener('pointerdown', outside, true);
      document.removeEventListener('keydown', onKey, true);
      window.removeEventListener('resize', close);
      trigger.setAttribute('aria-expanded', 'false');
      trigger.setAttribute('data-state', 'closed');
      var w = wrapper;
      content.setAttribute('data-state', 'closed');
      setTimeout(function () { w.remove(); }, 150);
      wrapper = null; content = null;
      trigger.focus();
    }

    function outside(e) {
      if (wrapper && !wrapper.contains(e.target) && !trigger.contains(e.target)) close();
    }

    function onKey(e) {
      if (!wrapper) return;
      var idx = items.indexOf(document.activeElement);
      if (e.key === 'Escape') { e.preventDefault(); close(); }
      else if (e.key === 'ArrowDown') { e.preventDefault(); focusItem(idx + 1); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); focusItem(idx - 1); }
      else if (e.key === 'Home') { e.preventDefault(); focusItem(0); }
      else if (e.key === 'End') { e.preventDefault(); focusItem(items.length - 1); }
      else if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        if (idx >= 0) { setValue(options[idx].value); close(); }
      } else if (e.key === 'Tab') { e.preventDefault(); }
    }

    trigger.addEventListener('click', function () { wrapper ? close() : open(); });
    trigger.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); open(); }
    });
  }

  // ------------------------------------------------------------------
  // 5. Confirm dialogs (Radix <AlertDialog>)
  // ------------------------------------------------------------------
  function initDialogs() {
    $$('[data-dialog]').forEach(function (dlg) {
      document.body.appendChild(dlg);   // like a Radix portal: avoids transformed ancestors
    });

    $$('[data-dialog-open]').forEach(function (trigger) {
      var dlg = document.getElementById(trigger.getAttribute('data-dialog-open'));
      if (!dlg) return;
      var overlay = $('[data-dialog-overlay]', dlg), content = $('[data-dialog-content]', dlg);
      var cancel = $('[data-dialog-cancel]', dlg);
      var action = $('button[type="submit"]', dlg);
      var prevOverflow, prevPadding;

      function onKey(e) {
        if (e.key === 'Escape') { e.preventDefault(); close(); }
        else if (e.key === 'Tab') {            // keep focus inside the dialog
          e.preventDefault();
          (document.activeElement === cancel ? action : cancel).focus();
        }
      }

      function open() {
        dlg.hidden = false;
        overlay.setAttribute('data-state', 'open');
        content.setAttribute('data-state', 'open');
        trigger.setAttribute('aria-expanded', 'true');
        var sbw = window.innerWidth - document.documentElement.clientWidth;
        prevOverflow = document.body.style.overflow; prevPadding = document.body.style.paddingRight;
        document.body.style.overflow = 'hidden';
        if (sbw > 0) document.body.style.paddingRight = sbw + 'px';
        cancel.focus();
        document.addEventListener('keydown', onKey, true);
      }

      function close() {
        document.removeEventListener('keydown', onKey, true);
        overlay.setAttribute('data-state', 'closed');
        content.setAttribute('data-state', 'closed');
        trigger.setAttribute('aria-expanded', 'false');
        setTimeout(function () {
          dlg.hidden = true;
          document.body.style.overflow = prevOverflow || '';
          document.body.style.paddingRight = prevPadding || '';
          trigger.focus();
        }, 200);
      }

      trigger.addEventListener('click', open);
      cancel.addEventListener('click', close);
      // (like Radix AlertDialog, clicking the dark overlay does NOT close it)
    });
  }

  // ------------------------------------------------------------------
  // 6. Dates: show in the visitor's own locale, like the original
  // ------------------------------------------------------------------
  function initDates() {
    $$('time[data-fmt]').forEach(function (t) {
      var d = new Date(t.getAttribute('datetime'));
      if (isNaN(d)) return;
      t.textContent = t.getAttribute('data-fmt') === 'date' ? d.toLocaleDateString() : d.toLocaleString();
    });
  }

  // ------------------------------------------------------------------
  // 7. Home page: comments under each active complaint
  // ------------------------------------------------------------------
  var SEND_ICON =
    '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-send h-3 w-3"><path d="M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z"></path><path d="m21.854 2.147-10.94 10.939"></path></svg>';

  function initComments() {
    var toggles = $$('[data-comments-toggle]');
    if (!toggles.length) return;
    var cfg = $('[data-class-author]') || document.body;
    var CLS = {
      author: cfg.getAttribute('data-class-author'),
      content: cfg.getAttribute('data-class-content'),
      send: cfg.getAttribute('data-class-send')
    };
    var openToggle = null;

    function mount(toggle) {
      var root = toggle.parentNode.parentNode.querySelector('[data-comments-root]');
      var id = toggle.getAttribute('data-complaint-id');
      var comments = [], showAll = false, posting = false;

      root.hidden = false;
      root.innerHTML = '';

      var wrap = el('div', 'mt-3 space-y-3');
      var authorInput = el('input', CLS.author, { placeholder: 'Your name (optional)', maxlength: '50' });
      var contentInput = el('input', CLS.content, { placeholder: 'Add a comment...', maxlength: '1000' });
      var sendBtn = el('button', CLS.send, { type: 'button', html: SEND_ICON });
      sendBtn.disabled = true;
      wrap.appendChild(el('div', 'flex gap-2', null, authorInput, contentInput, sendBtn));
      root.appendChild(wrap);

      function sync() { sendBtn.disabled = posting || !contentInput.value.trim(); }
      contentInput.addEventListener('input', sync);
      contentInput.addEventListener('keydown', function (e) { if (e.key === 'Enter') post(); });
      sendBtn.addEventListener('click', post);

      function render() {
        $$('[data-c]', wrap).forEach(function (n) { n.remove(); });
        var visible = showAll ? comments : comments.slice(0, 2);
        visible.forEach(function (c) {
          wrap.appendChild(el('div', 'text-xs bg-muted/40 rounded-md px-3 py-2', { 'data-c': '' },
            el('span', 'font-medium text-foreground', { text: c.author_name }),
            el('span', 'text-muted-foreground ml-2', { text: new Date(c.created_at).toLocaleDateString() }),
            el('p', 'text-foreground/80 mt-0.5', { text: c.content })));
        });
        if (comments.length > 2) {
          var more = el('button', 'text-xs text-accent hover:underline', { type: 'button', 'data-c': '',
            text: showAll ? 'Show less' : 'View all ' + comments.length + ' comments' });
          more.addEventListener('click', function () { showAll = !showAll; render(); });
          wrap.appendChild(more);
        }
        if (comments.length === 0) {
          wrap.appendChild(el('p', 'text-xs text-muted-foreground', { 'data-c': '', text: 'No comments yet. Be the first to speak up!' }));
        }
      }

      function load() {
        return fetch('/api/complaints/' + id + '/comments').then(function (r) { return r.json(); })
          .then(function (data) { comments = data || []; render(); })
          .catch(function () { comments = []; render(); });
      }

      function post() {
        var text = contentInput.value.trim();
        if (!text) return;
        posting = true; sync();
        fetch('/api/complaints/' + id + '/comments', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken() },
          body: JSON.stringify({ author_name: authorInput.value.trim(), content: text })
        }).then(function (r) {
          if (!r.ok) throw new Error('failed');
          toast.success('Comment posted!');
          contentInput.value = '';
          return load();
        }).catch(function () {
          toast.error('Failed to post comment');
        }).then(function () { posting = false; sync(); });
      }

      load();
    }

    function unmount(toggle) {
      var root = toggle.parentNode.parentNode.querySelector('[data-comments-root]');
      root.hidden = true; root.innerHTML = '';
    }

    toggles.forEach(function (t) {
      t.addEventListener('click', function () {
        if (openToggle === t) { unmount(t); openToggle = null; return; }
        if (openToggle) unmount(openToggle);
        openToggle = t; mount(t);
      });
    });
  }

  // ------------------------------------------------------------------
  // 8. Page specific behaviour
  // ------------------------------------------------------------------
  function initSubmitPage() {
    var form = $('[data-submit-form]');
    if (!form) return;
    var fileInput = $('[data-file-input]', form), chips = $('[data-file-chips]', form);
    var namesBox = $('[data-file-names]', form);
    var desc = $('[data-char-source]', form), count = $('[data-char-count]', form);
    var files = [];

    desc.addEventListener('input', function () { count.textContent = desc.value.length; });

    fileInput.addEventListener('change', function () {
      files = Array.prototype.slice.call(fileInput.files || [], 0, 5);   // max 5, like the original
      chips.innerHTML = '';
      files.forEach(function (f) { chips.appendChild(el('span', 'text-xs bg-muted px-2 py-1 rounded', { text: f.name })); });
      chips.hidden = files.length === 0;
    });

    form.addEventListener('submit', function (e) {
      var title = form.elements.title.value.trim(), description = desc.value.trim();
      var category = form.elements.category.value;
      if (!title || !description || !category) {
        e.preventDefault();
        toast.error('Please fill in all required fields.');
        return;
      }
      // Like the original app, only the attachment *names* are saved.
      namesBox.innerHTML = '';
      files.forEach(function (f) { namesBox.appendChild(el('input', null, { type: 'hidden', name: 'file_name', value: f.name })); });
      var btn = $('[data-submit-button]', form);
      btn.disabled = true; btn.textContent = 'Submitting...';
    });
  }

  function initCopyButton() {
    var btn = $('[data-copy]');
    if (!btn) return;
    btn.addEventListener('click', function () {
      var text = btn.getAttribute('data-copy');
      function done() { toast.success('Tracking ID copied!'); }
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done, done);
      } else {
        var ta = el('textarea', null, { style: 'position:fixed;opacity:0' });
        ta.value = text; document.body.appendChild(ta); ta.select();
        try { document.execCommand('copy'); } catch (e) { /* ignore */ }
        ta.remove(); done();
      }
    });
  }

  function initTrackPage() {
    var input = $('[data-uppercase]');
    if (!input) return;
    input.addEventListener('input', function () {
      var pos = input.selectionStart;
      input.value = input.value.toUpperCase();
      try { input.setSelectionRange(pos, pos); } catch (e) { /* ignore */ }
    });
    var form = input.form;
    form.addEventListener('submit', function (e) {
      if (!input.value.trim()) e.preventDefault();   // original ignores empty searches
    });
  }

  function initLoginPage() {
    var form = $('[data-login-form]');
    if (!form) return;
    form.addEventListener('submit', function (e) {
      if (!form.elements.email.value.trim() || !form.elements.password.value) {
        e.preventDefault();
        toast.error('Please enter your credentials.');
        return;
      }
      var btn = $('[data-submit-button]', form);
      $('[data-label]', btn).textContent = btn.getAttribute('data-busy-text');
      btn.disabled = true;
    });
  }

  function initAdminPage() {
    var cards = $$('[data-complaint]');
    var reload = $('[data-reload]');
    if (reload) reload.addEventListener('click', function () { window.location.reload(); });

    var current = cards.filter(function (c) { return !$('[data-expand-panel]', c).hidden; })[0] || null;

    function setOpen(card, open) {
      var panel = $('[data-expand-panel]', card);
      $('[data-chevron-down]', card).classList.toggle('hidden', open);
      $('[data-chevron-up]', card).classList.toggle('hidden', !open);
      if (open) {
        panel.hidden = false;
        var h = panel.scrollHeight;
        panel.style.overflow = 'hidden';
        panel.animate([{ height: '0px', opacity: 0 }, { height: h + 'px', opacity: 1 }], { duration: 250, easing: 'ease-out' })
          .onfinish = function () { panel.style.overflow = ''; };
      } else {
        panel.hidden = true;
      }
    }

    cards.forEach(function (card) {
      $('[data-expand-toggle]', card).addEventListener('click', function () {
        if (current === card) { setOpen(card, false); current = null; return; }
        if (current) setOpen(current, false);
        setOpen(card, true); current = card;
      });

      var form = $('[data-status-form]', card);
      var update = $('[data-update-button]', card);
      var statusInput = $('[data-select-input]', form);
      statusInput.addEventListener('change', function () { update.disabled = !statusInput.value; });
    });
  }

  // ------------------------------------------------------------------
  // Boot
  // ------------------------------------------------------------------
  document.addEventListener('DOMContentLoaded', function () {
    initMobileMenu();
    $$('[data-select-trigger]').forEach(initSelect);
    initDialogs();
    initDates();
    initReveal();
    initComments();
    initSubmitPage();
    initCopyButton();
    initTrackPage();
    initLoginPage();
    initAdminPage();
  });
})();

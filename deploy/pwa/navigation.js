/* Navigation only. No Service Worker, data caching, auth or touch interception. */
(() => {
  const mode = window.matchMedia('(display-mode: standalone)');
  let host;
  function hasWorkspaceNavigation() {
    return /^\/(drill|ei)(?:\/|$)/.test(location.pathname);
  }
  function syncMode() {
    if (!mode.matches && !navigator.standalone) {
      if (host) host.hidden = true;
      return;
    }
    // Drill and EI already provide a safe-area-aware drawer. The extra PWA
    // launcher can cover their fixed answer actions on small screens.
    if (hasWorkspaceNavigation()) {
      if (host) host.hidden = true;
      return;
    }
    if (host) { host.hidden = false; return; }
    host = document.createElement('eh-pwa-navigation');
    const shadow = host.attachShadow({ mode: 'open' });
    const services = 'https://47.95.10.128';
    shadow.innerHTML = `
      <style>
        :host { position:fixed; left:max(10px, env(safe-area-inset-left)); bottom:max(10px, env(safe-area-inset-bottom)); z-index:1000; font:13px/1.3 system-ui,sans-serif; color:var(--text-primary,#eee); }
        :host([hidden]) { display:none; }
        details { position:relative; }
        summary { list-style:none; display:grid; place-items:center; width:36px; height:36px; box-sizing:border-box; cursor:pointer; color:inherit; background:var(--bg-surface,#202326); border:1px solid var(--border-default,#64676a); border-radius:50%; box-shadow:0 2px 10px #0003; }
        summary::-webkit-details-marker { display:none; }
        svg { width:18px; height:18px; }
        nav { position:absolute; left:0; bottom:44px; display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:6px; width:min(252px,calc(100vw - 28px)); padding:8px; box-sizing:border-box; background:var(--bg-surface,#202326); border:1px solid var(--border-default,#64676a); border-radius:10px; box-shadow:0 4px 16px #0004; }
        button,a { font:inherit; min-width:0; min-height:44px; padding:6px; display:grid; place-items:center; border:1px solid var(--border-default,#64676a); border-radius:6px; background:transparent; color:inherit; text-decoration:none; cursor:pointer; }
        button:focus-visible,a:focus-visible,summary:focus-visible { outline:2px solid var(--accent,#70cba1); outline-offset:2px; }
        a[aria-current="page"] { border-color:var(--accent,#70cba1); color:var(--accent,#70cba1); }
      </style>
      <details>
        <summary aria-label="App navigation" title="App navigation"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16"/></svg></summary>
        <nav aria-label="App navigation">
          <button type="button" data-action="back">Back</button>
          <button type="button" data-action="refresh">Refresh</button>
          <a data-action="home" href="${services}/">Home</a>
          <a href="${services}/">Timer</a>
          <a href="${services}/drill/practice">Drill</a>
          <a href="${services}/ei/practice">EI</a>
        </nav>
      </details>`;
    const menu = shadow.querySelector('details');
    function updateLabels() {
      const zh = document.documentElement.lang.startsWith('zh');
      const label = zh ? '应用导航' : 'App navigation';
      shadow.querySelector('summary').setAttribute('aria-label', label);
      shadow.querySelector('summary').title = label;
      shadow.querySelector('nav').setAttribute('aria-label', label);
      for (const [action, text] of Object.entries({ back: zh ? '后退' : 'Back', refresh: zh ? '刷新' : 'Refresh', home: zh ? '首页' : 'Home' })) {
        shadow.querySelector(`[data-action="${action}"]`).textContent = text;
      }
      const workspace = /^\/(drill|ei)(?:\/|$)/.exec(location.pathname)?.[1] || 'timer';
      for (const link of shadow.querySelectorAll('nav a:not([data-action])')) {
        if (link.textContent.toLowerCase() === workspace) link.setAttribute('aria-current', 'page');
        else link.removeAttribute('aria-current');
      }
    }
    updateLabels();
    new MutationObserver(updateLabels).observe(document.documentElement, { attributes: true, attributeFilter: ['lang'] });
    window.addEventListener('popstate', updateLabels);
    shadow.addEventListener('click', event => {
      const action = event.target.closest('[data-action]')?.dataset.action;
      if (action === 'refresh') location.reload();
      if (action === 'back') { if (history.length > 1) history.back(); else location.assign('/'); }
      if (event.target.closest('a,button')) menu.open = false;
    });
    shadow.addEventListener('keydown', event => {
      if (event.key === 'Escape' && menu.open) { menu.open = false; shadow.querySelector('summary').focus(); }
    });
    document.addEventListener('pointerdown', event => {
      if (!event.composedPath().includes(host)) menu.open = false;
    }, { passive: true });
    document.body.append(host);
  }
  syncMode();
  window.addEventListener('popstate', syncMode);
  mode.addEventListener('change', syncMode);
})();

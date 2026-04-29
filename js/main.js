/* Site behaviour
   Tiny progressive-enhancement script: mobile nav, theme toggle, dynamic year. */

(function () {
  "use strict";

  // ---- Footer year ----
  const yearEl = document.getElementById("year");
  if (yearEl) yearEl.textContent = new Date().getFullYear();

  // ---- Mobile nav toggle ----
  const toggle = document.querySelector(".nav__toggle");
  const links = document.querySelector(".nav__links");
  if (toggle && links) {
    toggle.addEventListener("click", () => {
      const open = links.classList.toggle("open");
      toggle.setAttribute("aria-expanded", String(open));
    });
    // Close menu when a link is clicked (mobile)
    links.querySelectorAll("a").forEach((a) =>
      a.addEventListener("click", () => {
        if (window.innerWidth <= 640) {
          links.classList.remove("open");
          toggle.setAttribute("aria-expanded", "false");
        }
      })
    );
  }

  // ---- Theme toggle (cookie-based; no localStorage) ----
  // Terminal-dark is default (:root). [data-theme="light"] enables paper terminal.
  const themeBtn = document.querySelector(".nav__theme");
  const root = document.documentElement;

  function readCookie(name) {
    const m = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
    return m ? decodeURIComponent(m[2]) : null;
  }
  function writeCookie(name, value, days) {
    const d = new Date();
    d.setTime(d.getTime() + days * 24 * 60 * 60 * 1000);
    document.cookie = `${name}=${encodeURIComponent(value)};expires=${d.toUTCString()};path=/;SameSite=Lax`;
  }

  // Determine initial theme — dark by default, only flip to light if user
  // has stored "light" or has prefers-color-scheme: light
  const stored = readCookie("theme");
  const prefersLight = window.matchMedia &&
    window.matchMedia("(prefers-color-scheme: light)").matches;
  const initial = stored || (prefersLight ? "light" : "dark");
  if (initial === "light") root.setAttribute("data-theme", "light");

  function setTheme(t) {
    if (t === "light") root.setAttribute("data-theme", "light");
    else root.removeAttribute("data-theme");
    writeCookie("theme", t, 365);
  }

  if (themeBtn) {
    themeBtn.addEventListener("click", () => {
      const next = root.getAttribute("data-theme") === "light" ? "dark" : "light";
      setTheme(next);
      themeBtn.textContent = next === "light" ? "◐" : "◑";
    });
    // Set initial icon
    themeBtn.textContent = initial === "light" ? "◐" : "◑";
  }

  // ---- Smooth-scroll active section highlight (subtle) ----
  const sections = document.querySelectorAll("main section[id], header[id]");
  const navLinkMap = new Map();
  document.querySelectorAll(".nav__links a[href^='#']").forEach((a) => {
    navLinkMap.set(a.getAttribute("href").slice(1), a);
  });

  if ("IntersectionObserver" in window && sections.length) {
    const obs = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            navLinkMap.forEach((link) => link.classList.remove("active"));
            const link = navLinkMap.get(e.target.id);
            if (link) link.classList.add("active");
          }
        });
      },
      { rootMargin: "-40% 0px -55% 0px" }
    );
    sections.forEach((s) => obs.observe(s));
  }

  // ---- Reading progress bar (post pages only) ----
  const progress = document.querySelector(".read-progress");
  const postBody = document.querySelector(".post__body");
  if (progress && postBody) {
    const update = () => {
      const rect = postBody.getBoundingClientRect();
      const total = rect.height - window.innerHeight;
      const scrolled = Math.min(Math.max(-rect.top, 0), Math.max(total, 1));
      const pct = total > 0 ? (scrolled / total) * 100 : 0;
      progress.style.width = pct + "%";
    };
    update();
    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update, { passive: true });
  }

  // ---- Auto-compute reading time for posts ----
  // Skip if author already typed a value (e.g. "8 min", "8 分鐘") — auto-compute
  // would overcount on posts with a code/config appendix.
  const readingTimeEl = document.querySelector("[data-reading-time]");
  if (readingTimeEl && postBody && !readingTimeEl.textContent.trim()) {
    const words = postBody.innerText.trim().split(/\s+/).length;
    const minutes = Math.max(1, Math.round(words / 220));
    readingTimeEl.textContent = `${minutes} min read`;
  }

  // ---- Copy buttons on code blocks ----
  document.querySelectorAll(".post pre").forEach((pre) => {
    if (pre.parentElement && pre.parentElement.classList.contains("code-block")) return;
    const wrap = document.createElement("div");
    wrap.className = "code-block";
    pre.parentNode.insertBefore(wrap, pre);
    wrap.appendChild(pre);

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "code-block__copy";
    btn.setAttribute("aria-label", "Copy code to clipboard");
    btn.textContent = "Copy";
    wrap.appendChild(btn);

    btn.addEventListener("click", async () => {
      const code = pre.querySelector("code");
      const text = (code ? code.innerText : pre.innerText).replace(/\n$/, "");
      try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          await navigator.clipboard.writeText(text);
        } else {
          const ta = document.createElement("textarea");
          ta.value = text;
          ta.style.position = "fixed";
          ta.style.top = "-9999px";
          document.body.appendChild(ta);
          ta.select();
          document.execCommand("copy");
          ta.remove();
        }
        btn.textContent = "Copied";
        btn.classList.add("is-copied");
        setTimeout(() => {
          btn.textContent = "Copy";
          btn.classList.remove("is-copied");
        }, 1400);
      } catch {
        btn.textContent = "Failed";
        setTimeout(() => { btn.textContent = "Copy"; }, 1400);
      }
    });
  });

  // ---- View count via GoatCounter (post pages) ----
  // Sign up at https://goatcounter.com and replace the code below with your site code.
  const GOATCOUNTER_CODE = "imitation-alpha";
  const viewsEl = document.querySelector("[data-views]");
  if (viewsEl && GOATCOUNTER_CODE) {
    const url = `https://${GOATCOUNTER_CODE}.goatcounter.com/counter/${encodeURIComponent(location.pathname)}.json`;
    fetch(url)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((d) => {
        const n = parseInt(d.count_unique ?? d.count ?? 0, 10);
        if (!Number.isFinite(n) || n <= 0) return;
        const label = viewsEl.dataset.viewsLabel || "views";
        viewsEl.textContent = `${n.toLocaleString()} ${label}`;
        viewsEl.removeAttribute("hidden");
        const dot = document.querySelector(".view-dot");
        if (dot) dot.removeAttribute("hidden");
      })
      .catch(() => { /* leave hidden — first visit, network error, or pre-signup */ });
  }

  // ---- Active TOC item (post pages) ----
  const tocLinks = document.querySelectorAll(".post__toc a[href^='#']");
  if (tocLinks.length && "IntersectionObserver" in window) {
    const linkMap = new Map();
    tocLinks.forEach((a) => linkMap.set(a.getAttribute("href").slice(1), a));
    const headings = Array.from(linkMap.keys())
      .map((id) => document.getElementById(id))
      .filter(Boolean);
    if (headings.length) {
      const obs = new IntersectionObserver(
        (entries) => entries.forEach((e) => {
          if (e.isIntersecting) {
            tocLinks.forEach((a) => a.classList.remove("is-active"));
            const link = linkMap.get(e.target.id);
            if (link) link.classList.add("is-active");
          }
        }),
        { rootMargin: "-25% 0px -65% 0px" }
      );
      headings.forEach((h) => obs.observe(h));
    }
  }
})();

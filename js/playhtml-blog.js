import { playhtml } from "https://unpkg.com/playhtml";

(function () {
  "use strict";

  const widget = document.querySelector("[data-playhtml-blog-widget]");
  if (!widget) return;

  const locale = widget.dataset.playhtmlLocale || "en";
  const labels = {
    en: {
      loading: "Loading readers",
      oneReader: "1 reader here now",
      manyReaders: (count) => `${count} readers here now`,
      unavailable: "Reader trace unavailable",
    },
    "zh-Hant": {
      loading: "讀者狀態載入中",
      oneReader: "目前 1 位讀者在這裡",
      manyReaders: (count) => `目前 ${count} 位讀者在這裡`,
      unavailable: "讀者足跡暫時無法使用",
    },
  };
  const text = labels[locale] || labels.en;

  const reactions = ["useful", "think", "reread"];
  const clicked = new Set();
  const countEls = new Map();

  const presenceCount = widget.querySelector(".playhtml-widget__presence-count");
  const presencePips = widget.querySelector("[data-presence-pips]");
  const buttons = Array.from(widget.querySelectorAll("[data-reaction]"));

  function normalizedPath() {
    return window.location.pathname
      .replace(/\/index\.html$/i, "/")
      .replace(/\.html$/i, "")
      .replace(/^\/+|\/+$/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9/-]+/g, "-")
      .replace(/-+/g, "-") || "blog";
  }

  function roomName() {
    return `arthur-blog-trace:${locale}:${normalizedPath()}`;
  }

  function anonymousIdentity() {
    const hue = Math.floor(Math.random() * 360);
    const color = `hsl(${hue}, 78%, 62%)`;
    const id = window.crypto?.randomUUID
      ? window.crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    return {
      publicKey: `reader-${id}`,
      playerStyle: {
        colorPalette: [color],
      },
      createdAt: Date.now(),
    };
  }

  function setStatus(message) {
    if (presenceCount) presenceCount.textContent = message;
  }

  function formatReaders(count) {
    if (count === 1) return text.oneReader;
    return text.manyReaders(count);
  }

  function renderCounts(data) {
    reactions.forEach((key) => {
      const value = Number(data && data[key]) || 0;
      const el = countEls.get(key);
      if (el) el.textContent = value.toLocaleString();
    });
  }

  function renderPresence(presences) {
    const readers = Array.from(presences.values());
    setStatus(formatReaders(Math.max(readers.length, 1)));
    if (!presencePips) return;

    presencePips.innerHTML = "";
    readers.slice(0, 8).forEach((presence) => {
      const pip = document.createElement("span");
      const color = presence.playerIdentity?.playerStyle?.colorPalette?.[0];
      pip.className = "playhtml-widget__presence-pip";
      if (presence.isMe) pip.classList.add("is-me");
      if (color) pip.style.setProperty("--pip-color", color);
      presencePips.appendChild(pip);
    });
  }

  function setUnavailable(error) {
    widget.classList.add("is-unavailable");
    setStatus(text.unavailable);
    buttons.forEach((button) => {
      button.disabled = true;
    });
    if (error) console.warn("[playhtml-blog]", error);
  }

  async function init() {
    setStatus(text.loading);

    const room = roomName();
    const identity = anonymousIdentity();
    widget.dataset.playhtmlSession = identity.publicKey;
    await playhtml.init({
      room,
      cursors: {
        enabled: true,
        room: () => room,
        enableChat: false,
        playerIdentity: identity,
        shouldRenderCursor: () => false,
      },
    });
    await playhtml.ready;

    const channel = playhtml.createPageData("reader-trace", {
      useful: 0,
      think: 0,
      reread: 0,
    });

    buttons.forEach((button) => {
      const key = button.dataset.reaction;
      const count = button.querySelector("[data-reaction-count]");
      if (!key || !reactions.includes(key)) return;
      if (count) countEls.set(key, count);

      button.addEventListener("click", () => {
        if (clicked.has(key)) return;
        clicked.add(key);
        button.setAttribute("aria-pressed", "true");
        channel.setData((draft) => {
          draft[key] = (Number(draft[key]) || 0) + 1;
        });
      });
    });

    renderCounts(channel.getData());
    channel.onUpdate(renderCounts);

    playhtml.presence.setMyPresence("blog-reader", {
      room,
      locale,
      path: normalizedPath(),
    });
    renderPresence(playhtml.presence.getPresences());
    playhtml.presence.onPresenceChange("blog-reader", renderPresence);
  }

  init().catch(setUnavailable);
})();

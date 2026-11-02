// DOM helpers shared by the views. Addon data is untrusted, so text always goes
// through textContent; innerHTML is only used for the static icons below.

export function h(tag, props, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(props || {})) {
    if (value == null || value === false) continue;
    if (key === "class") el.className = value;
    else if (key.startsWith("on") && typeof value === "function") {
      el.addEventListener(key.slice(2).toLowerCase(), value);
    } else if (key === "value") el.value = value;
    else el.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat(Infinity)) {
    if (child == null || child === false) continue;
    el.append(child instanceof Node ? child : String(child));
  }
  return el;
}

const ICONS = {
  back: '<path d="M15 5l-7 7 7 7"/>',
  close: '<path d="M6 6l12 12M18 6L6 18"/>',
  search: '<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/>',
  settings:
    '<circle cx="12" cy="12" r="3"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M5.3 18.7l2.1-2.1M16.6 7.4l2.1-2.1"/>',
  play: '<path d="M8 5.5v13l10.5-6.5z" fill="currentColor" stroke="none"/>',
  external: '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  trash: '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6"/>'
};

export function icon(name) {
  const span = document.createElement("span");
  span.className = "icon";
  span.setAttribute("aria-hidden", "true");
  span.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICONS[name]}</svg>`;
  return span;
}

export function brandMark() {
  const span = document.createElement("span");
  span.className = "brand-mark";
  span.setAttribute("aria-hidden", "true");
  span.innerHTML =
    '<svg viewBox="0 0 32 32"><rect x="5" y="6" width="5" height="18" rx="1.5" fill="currentColor"/><rect x="12" y="9" width="5" height="15" rx="1.5" fill="currentColor" opacity=".7"/><path d="M20 8.5l6 2-4.6 13.6-6-2z" fill="currentColor" opacity=".45"/><rect x="3" y="25.5" width="26" height="2.5" rx="1.25" fill="currentColor"/></svg>';
  return span;
}

export function spinner(label = "Loading") {
  return h("div", { class: "spinner", role: "status" }, h("span", { class: "visually-hidden" }, label));
}

let toastTimer = null;
export function toast(message, { action, onAction, duration = 3200 } = {}) {
  let el = document.querySelector(".toast");
  if (!el) {
    el = h("div", { class: "toast", role: "status", "aria-live": "polite" });
    document.body.append(el);
  }
  el.replaceChildren(
    h("span", {}, message),
    action
      ? h("button", { class: "toast-action", onclick: () => { el.classList.remove("show"); onAction?.(); } }, action)
      : null
  );
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), duration);
}

let activeSheet = null;
export function openSheet({ title, subtitle }) {
  closeSheet();
  const body = h("div", { class: "sheet-body" });
  const panel = h(
    "div",
    { class: "sheet", role: "dialog", "aria-modal": "true", "aria-label": title },
    h("div", { class: "sheet-handle" }),
    h(
      "div",
      { class: "sheet-head" },
      h("div", { class: "sheet-heading" }, h("h2", {}, title), subtitle ? h("p", {}, subtitle) : null),
      h("button", { class: "icon-btn", "aria-label": "Close", onclick: closeSheet }, icon("close"))
    ),
    body
  );
  const wrap = h("div", { class: "sheet-wrap" }, h("div", { class: "sheet-backdrop", onclick: closeSheet }), panel);
  document.body.append(wrap);
  document.body.classList.add("sheet-open");
  requestAnimationFrame(() => wrap.classList.add("open"));
  activeSheet = wrap;
  return { body, close: closeSheet };
}

export function closeSheet() {
  if (!activeSheet) return;
  const wrap = activeSheet;
  activeSheet = null;
  wrap.classList.remove("open");
  document.body.classList.remove("sheet-open");
  setTimeout(() => wrap.remove(), 260);
}

export function artImg(url, label, className = "") {
  const placeholder = () => h("div", { class: `art-fallback ${className}` }, h("span", {}, label || ""));
  if (!url) return placeholder();
  return h("img", {
    class: className,
    src: url,
    alt: "",
    loading: "lazy",
    decoding: "async",
    referrerpolicy: "no-referrer",
    onerror: (event) => event.target.replaceWith(placeholder())
  });
}

export function errorBlock(error, onRetry) {
  return h(
    "div",
    { class: "error-block" },
    h("p", {}, error?.message || String(error)),
    onRetry ? h("button", { class: "btn btn-ghost btn-sm", onclick: onRetry }, "Try again") : null
  );
}

const TYPE_LABELS = { movie: "Movies", series: "Series", tv: "TV", channel: "Channels", anime: "Anime", other: "Other" };
export function typeLabel(type) {
  const value = String(type || "");
  return TYPE_LABELS[value] || value.charAt(0).toUpperCase() + value.slice(1);
}

export function fmtTime(ms) {
  const total = Math.max(0, Math.floor((Number(ms) || 0) / 1000));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = String(total % 60).padStart(2, "0");
  return hours ? `${hours}:${String(minutes).padStart(2, "0")}:${seconds}` : `${minutes}:${seconds}`;
}

export function episodeLabel(video) {
  if (!video) return "";
  if (video.season != null && video.episode != null) {
    return `S${video.season} E${video.episode}${video.title ? ` · ${video.title}` : ""}`;
  }
  return video.title || "";
}

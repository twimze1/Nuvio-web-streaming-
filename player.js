// Full-screen player built on Safari's own <video>: it plays MP4/MOV and HLS
// natively, and its controls already include AirPlay, PiP and fullscreen.
import { h, icon, openSheet, closeSheet, toast, fmtTime, episodeLabel } from "./ui.js";
import * as nuvio from "./nuvio.js";
import * as addons from "./addons.js";
import { state, ensureProgress, recordProgress } from "./state.js";

const PUSH_INTERVAL_MS = 60 * 1000;
const MIN_SAVE_POSITION_MS = 10 * 1000;
const RESUME_MIN_MS = 30 * 1000;
const MAX_SUBTITLE_TRACKS = 6;

let els = null;
let current = null;
let lastPushAt = 0;
let lastPushedPosition = -1;
let subtitleUrls = [];

function build() {
  const video = h("video", { playsinline: true, "webkit-playsinline": true, controls: true, preload: "auto" });
  const title = h("strong");
  const subtitle = h("span");
  const notice = h("div", { class: "player-notice", hidden: true });
  const root = h(
    "div",
    { class: "player", hidden: true, role: "dialog", "aria-label": "Video player" },
    h(
      "div",
      { class: "player-bar" },
      h("button", { class: "icon-btn", "aria-label": "Close player", onclick: () => closePlayer() }, icon("close")),
      h("div", { class: "player-title" }, title, subtitle),
      h("button", { class: "btn btn-ghost btn-sm", onclick: () => openExternalSheet() }, icon("external"), "Open in…")
    ),
    h("div", { class: "player-stage" }, video),
    notice
  );
  document.body.append(root);

  video.addEventListener("loadedmetadata", resumeIfNeeded);
  video.addEventListener("timeupdate", () => saveProgress(false));
  video.addEventListener("pause", () => saveProgress(true));
  video.addEventListener("ended", () => saveProgress(true, true));
  video.addEventListener("error", showPlaybackError);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") saveProgress(true);
  });
  window.addEventListener("popstate", () => {
    if (current) closePlayer({ fromHistory: true });
  });
  els = { root, video, title, subtitle, notice };
}

// Must run inside the tap handler: iOS only starts playback with sound from a
// user gesture, so nothing here may await before video.play().
export function playStream(context) {
  if (!els) build();
  if (current) saveProgress(true);
  closeSheet();
  current = { ...context, resumeChecked: false };
  lastPushedPosition = -1;
  lastPushAt = 0;
  clearSubtitles();

  els.title.textContent = context.meta.name || "";
  els.subtitle.textContent = context.video ? episodeLabel(context.video) : context.streamLabel || "";
  els.notice.hidden = true;
  els.root.hidden = false;
  document.body.classList.add("playing");
  els.video.src = context.url;
  els.video.play()?.catch(() => {
    // Autoplay can be refused; the visible controls let the viewer start it.
  });
  history.pushState({ shelfPlayer: true }, "");
  loadSubtitles(current).catch(() => {});
}

export function closePlayer({ fromHistory = false } = {}) {
  if (!current) return;
  saveProgress(true);
  current = null;
  els.video.pause();
  els.video.removeAttribute("src");
  els.video.load();
  clearSubtitles();
  els.root.hidden = true;
  document.body.classList.remove("playing");
  // Cached views now show stale progress; they rebuild on next visit.
  state.version += 1;
  if (!fromHistory && history.state?.shelfPlayer) history.back();
}

function progressIdentity() {
  return {
    contentId: current.meta.id,
    contentType: current.type,
    videoId: current.videoId,
    season: current.video?.season ?? null,
    episode: current.video?.episode ?? null
  };
}

async function resumeIfNeeded() {
  if (!current || current.resumeChecked) return;
  current.resumeChecked = true;
  const token = current;
  const { byKey } = await ensureProgress();
  if (token !== current) return;
  const identity = progressIdentity();
  const saved = byKey.get(nuvio.progressKey(identity.contentId, identity.season, identity.episode));
  const duration = els.video.duration * 1000;
  if (!saved || saved.positionMs < RESUME_MIN_MS) return;
  if (Number.isFinite(duration) && saved.positionMs > duration * 0.95) return;
  els.video.currentTime = saved.positionMs / 1000;
  toast(`Resumed at ${fmtTime(saved.positionMs)}`, {
    action: "Start over",
    onAction: () => {
      els.video.currentTime = 0;
    },
    duration: 6000
  });
}

function saveProgress(force, ended = false) {
  if (!current || !els) return;
  const video = els.video;
  const durationMs = video.duration * 1000;
  if (!Number.isFinite(durationMs) || durationMs <= 0) return;
  const positionMs = ended ? durationMs : video.currentTime * 1000;
  if (positionMs < MIN_SAVE_POSITION_MS) return;
  if (!force && Date.now() - lastPushAt < PUSH_INTERVAL_MS) return;
  if (Math.abs(positionMs - lastPushedPosition) < 3000) return;
  lastPushAt = Date.now();
  lastPushedPosition = positionMs;
  const item = { ...progressIdentity(), positionMs, durationMs };
  recordProgress(item).catch(() => {});
  if (state.signedIn && state.profile) {
    nuvio.pushProgress(state.profile.index, item).catch((error) => {
      console.warn("Couldn't save progress to Nuvio", error);
    });
  }
}

function showPlaybackError() {
  if (!current) return;
  const code = els.video.error?.code;
  const reason =
    code === 4
      ? "Safari can't play this format. MKV files and some audio codecs (DTS, TrueHD) need another player."
      : code === 2
        ? "The stream stopped loading. The link may have expired."
        : "Safari couldn't play this stream.";
  els.notice.hidden = false;
  els.notice.replaceChildren(
    h("p", {}, reason),
    h(
      "div",
      { class: "notice-actions" },
      ...externalOptions(current.url).map((option) =>
        h("button", { class: "btn btn-ghost btn-sm", onclick: option.run }, option.label)
      ),
      h("button", { class: "btn btn-ghost btn-sm", onclick: () => closePlayer() }, "Pick another stream")
    )
  );
}

function externalOptions(url) {
  const open = (target) => () => {
    window.location.href = target;
  };
  return [
    { label: "VLC", run: open(`vlc-x-callback://x-callback-url/stream?url=${encodeURIComponent(url)}`) },
    { label: "Infuse", run: open(`infuse://x-callback-url/play?url=${encodeURIComponent(url)}`) },
    { label: "Outplayer", run: open(`outplayer://${url}`) },
    {
      label: "Copy link",
      run: async () => {
        try {
          await navigator.clipboard.writeText(url);
          toast("Link copied");
        } catch {
          toast("Couldn't copy the link");
        }
      }
    }
  ];
}

function openExternalSheet() {
  if (!current) return;
  const url = current.url;
  els.video.pause();
  const sheet = openSheet({ title: "Open in another player", subtitle: "The app must be installed on this iPhone." });
  sheet.body.append(
    h(
      "div",
      { class: "option-list" },
      ...externalOptions(url).map((option) =>
        h("button", { class: "option", onclick: () => { sheet.close(); option.run(); } }, option.label)
      )
    )
  );
}

// Subtitles: sidecar files on the stream plus any subtitle addons, converted to
// WebVTT (the only format Safari's <track> accepts) and attached as blob URLs.
const LANGUAGE_CODES = {
  en: ["eng", "en"], es: ["spa", "es"], fr: ["fre", "fra", "fr"], de: ["ger", "deu", "de"],
  it: ["ita", "it"], pt: ["por", "pob", "pt"], hr: ["hrv", "hr"], sr: ["srp", "scc", "sr"],
  bs: ["bos", "bs"], sl: ["slv", "sl"], sq: ["alb", "sqi", "sq"], nl: ["dut", "nld", "nl"],
  pl: ["pol", "pl"], ru: ["rus", "ru"], tr: ["tur", "tr"], ar: ["ara", "ar"], ro: ["rum", "ron", "ro"],
  hu: ["hun", "hu"], cs: ["cze", "ces", "cs"], el: ["gre", "ell", "el"], sv: ["swe", "sv"]
};
const CP1250_LANGUAGES = new Set(["hr", "sr", "bs", "sl", "pl", "cs", "hu", "ro", "sq"]);

function twoLetter(code) {
  const value = String(code || "").toLowerCase();
  for (const [short, aliases] of Object.entries(LANGUAGE_CODES)) {
    if (aliases.includes(value)) return short;
  }
  return value.length === 2 ? value : "";
}

function languageName(code) {
  const short = twoLetter(code);
  try {
    if (short) return new Intl.DisplayNames(["en"], { type: "language" }).of(short);
  } catch {
    // Fall through to the raw code.
  }
  return code || "Unknown";
}

function pickSubtitles(list) {
  const preferred = [...new Set([...(navigator.languages || []).map((l) => l.slice(0, 2).toLowerCase()), "en"])];
  const rank = (s) => {
    const index = preferred.indexOf(twoLetter(s.lang));
    return index < 0 ? preferred.length : index;
  };
  const perLanguage = new Map();
  const seenUrls = new Set();
  return list
    .filter((s) => s.url && !seenUrls.has(s.url) && seenUrls.add(s.url))
    .sort((a, b) => rank(a) - rank(b))
    .filter((s) => {
      const count = perLanguage.get(s.lang) || 0;
      perLanguage.set(s.lang, count + 1);
      return count < 2;
    })
    .slice(0, MAX_SUBTITLE_TRACKS);
}

function toVtt(text) {
  const clean = text.replace(/^﻿/, "").replace(/\r/g, "");
  if (/^WEBVTT/.test(clean)) return clean;
  return `WEBVTT\n\n${clean.replace(/(\d{1,2}:\d{2}:\d{2}),(\d{3})/g, "$1.$2")}`;
}

async function fetchSubtitle(url, lang) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const bytes = await res.arrayBuffer();
  let text;
  try {
    text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    const legacy = CP1250_LANGUAGES.has(twoLetter(lang)) ? "windows-1250" : "windows-1252";
    text = new TextDecoder(legacy).decode(bytes);
  }
  return URL.createObjectURL(new Blob([toVtt(text)], { type: "text/vtt" }));
}

async function loadSubtitles(context) {
  const found = (context.stream?.subtitles || [])
    .filter((s) => s?.url)
    .map((s) => ({ url: s.url, lang: s.lang || "und" }));
  const subtitleAddons = state.addons.filter((a) => addons.supports(a, "subtitles", context.type, context.videoId));
  const results = await Promise.allSettled(
    subtitleAddons.map((addon) => addons.getSubtitles(addon, context.type, context.videoId))
  );
  for (const result of results) {
    if (result.status === "fulfilled") {
      found.push(...result.value.map((s) => ({ url: s.url, lang: s.lang || "und" })));
    }
  }
  for (const subtitle of pickSubtitles(found)) {
    if (current !== context) return;
    try {
      const blobUrl = await fetchSubtitle(subtitle.url, subtitle.lang);
      if (current !== context) {
        URL.revokeObjectURL(blobUrl);
        return;
      }
      subtitleUrls.push(blobUrl);
      els.video.append(
        h("track", {
          kind: "subtitles",
          src: blobUrl,
          srclang: twoLetter(subtitle.lang) || "und",
          label: languageName(subtitle.lang)
        })
      );
    } catch {
      // Many subtitle hosts don't allow web apps to download files; skip those.
    }
  }
}

function clearSubtitles() {
  els?.video.querySelectorAll("track").forEach((track) => track.remove());
  subtitleUrls.forEach((url) => URL.revokeObjectURL(url));
  subtitleUrls = [];
}

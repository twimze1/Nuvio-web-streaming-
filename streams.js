// Stream picker: asks every addon that serves streams for this video and lists
// what Safari can play first.
import { h, openSheet, spinner, episodeLabel } from "./ui.js";
import * as addons from "./addons.js";
import { state } from "./state.js";
import { playStream } from "./player.js";

const SAFARI_UNFRIENDLY = /\.(mkv|avi|wmv|flv|webm)$/i;

function classify(stream) {
  if (stream.url) {
    const hints = stream.behaviorHints || {};
    const name = String(hints.filename || stream.url).split("?")[0];
    const warnings = [];
    if (SAFARI_UNFRIENDLY.test(name)) warnings.push("MKV/AVI rarely plays in Safari");
    else if (hints.notWebReady) warnings.push("May not play in a browser");
    if (hints.proxyHeaders) warnings.push("Needs special headers");
    if (location.protocol === "https:" && /^http:\/\//i.test(stream.url)) warnings.push("http:// link may be blocked");
    return { kind: "play", warnings };
  }
  if (stream.externalUrl) return { kind: "external" };
  if (stream.ytId) return { kind: "youtube" };
  if (stream.infoHash) return { kind: "torrent" };
  return { kind: "unknown" };
}

function streamText(stream) {
  return [stream.title, stream.description].filter(Boolean).join("\n");
}

export function openStreams({ type, meta, video }) {
  const videoId = video?.id || meta.behaviorHints?.defaultVideoId || meta.id;
  const sheet = openSheet({ title: meta.name || "Streams", subtitle: video ? episodeLabel(video) : meta.releaseInfo || "" });
  const list = h("div", { class: "stream-list" });
  sheet.body.append(list);

  const sources = state.addons.filter((addon) => addons.supports(addon, "stream", type, videoId));
  if (!sources.length) {
    list.append(
      h("p", { class: "muted pad" }, "None of your addons offer streams for this title. Add or enable a stream addon in Nuvio.")
    );
    return;
  }

  const context = { type, meta, video, videoId };
  for (const addon of sources) {
    const status = h("div", { class: "stream-status" }, spinner(), h("span", {}, "Searching…"));
    const group = h("section", { class: "stream-group" }, h("h3", {}, addon.name), status);
    list.append(group);
    addons
      .getStreams(addon, type, videoId)
      .then((streams) => fillGroup(group, status, addon, streams, context))
      .catch((error) => status.replaceChildren(h("span", { class: "muted" }, error.message)));
  }
}

function fillGroup(group, status, addon, streams, context) {
  const playable = [];
  const links = [];
  let torrents = 0;
  for (const stream of streams) {
    const info = classify(stream);
    if (info.kind === "play") playable.push({ stream, warnings: info.warnings });
    else if (info.kind === "external" || info.kind === "youtube") links.push(stream);
    else if (info.kind === "torrent") torrents += 1;
  }
  // Streams Safari should handle go first; the addon's own order is kept otherwise.
  playable.sort((a, b) => Number(a.warnings.length > 0) - Number(b.warnings.length > 0));

  const items = [
    ...playable.map(({ stream, warnings }) =>
      h(
        "button",
        {
          class: `stream${warnings.length ? " stream-risky" : ""}`,
          onclick: () =>
            playStream({ ...context, url: stream.url, stream, streamLabel: stream.name || addon.name })
        },
        h("div", { class: "stream-name" }, stream.name || addon.name),
        streamText(stream) ? h("div", { class: "stream-title" }, streamText(stream)) : null,
        warnings.length ? h("div", { class: "stream-warn" }, warnings.join(" · ")) : null
      )
    ),
    ...links.map((stream) =>
      h(
        "a",
        {
          class: "stream",
          href: stream.externalUrl || `https://www.youtube.com/watch?v=${encodeURIComponent(stream.ytId)}`,
          target: "_blank",
          rel: "noopener"
        },
        h("div", { class: "stream-name" }, stream.name || addon.name),
        h("div", { class: "stream-title" }, streamText(stream) || "Opens outside Shelf")
      )
    )
  ];

  const notes = [];
  if (torrents) {
    notes.push(`${torrents} torrent result${torrents === 1 ? "" : "s"} hidden. Safari can't play torrents.`);
  }
  if (!items.length && !torrents) notes.push("No streams found.");
  status.replaceWith(...items, ...notes.map((note) => h("p", { class: "muted small" }, note)));
  if (!items.length) group.classList.add("stream-group-empty");
}

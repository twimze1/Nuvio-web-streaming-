// App-wide state: who is signed in, the active profile, its addons, and the
// lazily loaded library and watch progress.
import * as nuvio from "./nuvio.js";
import * as addons from "./addons.js";
import { load, save } from "./store.js";

export const COMPLETED_RATIO = 0.92;

export const state = {
  signedIn: false,
  guest: false,
  profiles: [],
  profile: null,
  addons: [],
  // Bumped whenever cached views may show stale progress or account data.
  version: 0,
  libraryPromise: null,
  progressPromise: null,
  previews: new Map(),
  metas: new Map(),
  // Hashes visited in this tab, so Back can tell in-app history from none.
  navStack: []
};

export function extraAddonUrls() {
  return load("extraAddons", []);
}

export function setExtraAddonUrls(urls) {
  save("extraAddons", urls);
}

export async function loadAccount() {
  state.signedIn = nuvio.isSignedIn();
  state.guest = !state.signedIn && load("guest") === true;
  state.libraryPromise = null;
  state.progressPromise = null;
  state.metas.clear();
  state.version += 1;

  let accountUrls = [];
  if (state.signedIn) {
    state.profiles = await nuvio.getProfiles();
    const savedIndex = load("profile");
    state.profile =
      state.profiles.find((p) => p.index === savedIndex) ||
      (state.profiles.length === 1 ? state.profiles[0] : null);
    if (state.profile) accountUrls = await nuvio.getAddonUrls(state.profile);
  } else {
    state.profiles = [];
    state.profile = null;
  }

  const extras = extraAddonUrls();
  const extraKeys = new Set(extras.map(addons.addonKey));
  const seen = new Set();
  const urls = [];
  for (const url of [...accountUrls, ...extras]) {
    const key = addons.addonKey(url);
    if (!seen.has(key)) {
      seen.add(key);
      urls.push(url);
    }
  }
  state.addons = await Promise.all(urls.map((url) => addons.loadAddon(url)));
  state.addons.forEach((addon) => {
    addon.local = extraKeys.has(addon.key);
  });
}

export function selectProfile(profile) {
  save("profile", profile.index);
  state.profile = profile;
}

export function ensureLibrary() {
  if (!state.libraryPromise) {
    state.libraryPromise =
      state.signedIn && state.profile ? nuvio.getLibrary(state.profile.index) : Promise.resolve([]);
    state.libraryPromise.catch(() => {
      state.libraryPromise = null;
    });
  }
  return state.libraryPromise;
}

function indexProgress(list) {
  const byKey = new Map();
  const byContent = new Map();
  for (const item of list) {
    const key = nuvio.progressKey(item.contentId, item.season, item.episode);
    if (!byKey.has(key)) byKey.set(key, item);
    if (!byContent.has(item.contentId)) byContent.set(item.contentId, item);
  }
  return { list, byKey, byContent };
}

export function ensureProgress() {
  if (!state.progressPromise) {
    const pending =
      state.signedIn && state.profile ? nuvio.getProgress(state.profile.index) : Promise.resolve([]);
    const local = load(`progress.${state.profile?.index || "guest"}`, []);
    state.progressPromise = pending
      .catch(() => [])
      .then((remote) => {
        // Keep entries saved on this device that the server doesn't have yet.
        const keys = new Set(remote.map((p) => nuvio.progressKey(p.contentId, p.season, p.episode)));
        const merged = [
          ...remote,
          ...local.filter((p) => !keys.has(nuvio.progressKey(p.contentId, p.season, p.episode)))
        ];
        return indexProgress(merged.sort((a, b) => b.updatedAt - a.updatedAt));
      });
  }
  return state.progressPromise;
}

export async function recordProgress(item) {
  const entry = { ...item, updatedAt: Date.now() };
  const storageKey = `progress.${state.profile?.index || "guest"}`;
  const key = nuvio.progressKey(entry.contentId, entry.season, entry.episode);
  const local = load(storageKey, []).filter(
    (p) => nuvio.progressKey(p.contentId, p.season, p.episode) !== key
  );
  save(storageKey, [entry, ...local].slice(0, 200));
  const current = await ensureProgress();
  const list = [entry, ...current.list.filter((p) => nuvio.progressKey(p.contentId, p.season, p.episode) !== key)];
  state.progressPromise = Promise.resolve(indexProgress(list));
}

export function isCompleted(progress) {
  return progress.durationMs > 0 && progress.positionMs / progress.durationMs >= COMPLETED_RATIO;
}

export function rememberPreview(type, meta, addon) {
  const key = `${type}:${meta.id}`;
  if (!state.previews.has(key)) state.previews.set(key, { meta: { ...meta, type }, addon });
}

export function findAddonByBase(base) {
  if (!base) return null;
  const key = addons.addonKey(base);
  return state.addons.find((addon) => addon.key === key) || null;
}

// Ask the addon the item came from first, then every addon that declares meta
// support for this type and id. Falls back to the catalog preview.
export function resolveMeta(type, id, hint) {
  const cacheKey = `${type}:${id}`;
  if (!state.metas.has(cacheKey)) {
    const promise = (async () => {
      const candidates = [];
      if (hint && addons.supports(hint, "meta", type)) candidates.push(hint);
      for (const addon of state.addons) {
        if (addon !== hint && addons.supports(addon, "meta", type, id)) candidates.push(addon);
      }
      let lastError = null;
      for (const addon of candidates) {
        try {
          const meta = await addons.getMeta(addon, type, id);
          if (meta && (meta.name || meta.videos?.length)) return { meta: { ...meta, id: meta.id || id }, addon };
        } catch (error) {
          lastError = error;
        }
      }
      const preview = state.previews.get(cacheKey);
      if (preview) return { meta: preview.meta, addon: preview.addon, partial: true };
      throw lastError || new Error("None of your addons could describe this title.");
    })();
    state.metas.set(cacheKey, promise);
    promise.catch(() => state.metas.delete(cacheKey));
  }
  return state.metas.get(cacheKey);
}

// Episodes in watch order, specials (season 0) last.
export function sortedVideos(meta) {
  const videos = (Array.isArray(meta?.videos) ? meta.videos : [])
    .filter((v) => v?.id)
    .map((v, order) => {
      const season = v.season == null || v.season === "" ? null : Number(v.season);
      const episodeRaw = v.episode ?? v.number;
      const episode = episodeRaw == null || episodeRaw === "" ? null : Number(episodeRaw);
      return {
        id: String(v.id),
        title: v.title || v.name || "",
        season: Number.isFinite(season) ? season : null,
        episode: Number.isFinite(episode) ? episode : null,
        thumbnail: v.thumbnail || null,
        overview: v.overview || v.description || "",
        released: v.released || v.firstAired || null,
        order
      };
    });
  const seasonRank = (s) => (s == null ? -1 : s === 0 ? Number.MAX_SAFE_INTEGER : s);
  return videos.sort(
    (a, b) =>
      seasonRank(a.season) - seasonRank(b.season) ||
      (a.episode ?? a.order) - (b.episode ?? b.order) ||
      a.order - b.order
  );
}

export function findVideo(videos, progress) {
  if (!progress) return null;
  return (
    (progress.videoId && videos.find((v) => v.id === progress.videoId)) ||
    (progress.season != null &&
      progress.episode != null &&
      videos.find((v) => v.season === progress.season && v.episode === progress.episode)) ||
    null
  );
}

export function nextVideo(videos, current) {
  const index = videos.indexOf(current);
  if (index < 0) return null;
  return videos.slice(index + 1).find((v) => v.season !== 0) || null;
}

export function firstVideo(videos) {
  return videos.find((v) => v.season == null || v.season > 0) || videos[0] || null;
}

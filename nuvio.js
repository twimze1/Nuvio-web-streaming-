// Client for the Nuvio account service (a Supabase backend). It mirrors the
// calls the official Nuvio web/TV client makes: password sign-in, profiles,
// installed addons, saved library and watch progress.
import { load, save } from "./store.js";

// nuvio.tv publishes its public client settings (backend URL and publishable
// key) in this script. Reading it at runtime keeps keys out of this repo.
const OFFICIAL_CONFIG_URL = "https://nuvio.tv/config.js";
const CONFIG_TIMEOUT_MS = 10000;
const LIBRARY_PAGE_SIZE = 500;
// Older progress rows store seconds, newer ones milliseconds. Like the official
// client, a duration above eight hours means the pair is in milliseconds.
const AMBIGUOUS_SECONDS_LIMIT = 8 * 60 * 60;
const SYNTHETIC_EPISODE_PREFIX = "__nuvio_episode__:";

export class AuthError extends Error {}

let server = null;
let session = load("session");
let ownerId = load("owner");
let refreshing = null;

export const getServer = () => server;
export const isSignedIn = () => Boolean(session?.refresh);
export const accountEmail = () => session?.email || "";
export const customServer = () => load("customServer");

function trimUrl(value) {
  return String(value || "").trim().replace(/\/+$/, "");
}

function loadOfficialScript() {
  return new Promise((resolve, reject) => {
    if (window.__NUVIO_CONFIG__) {
      resolve(window.__NUVIO_CONFIG__);
      return;
    }
    const script = document.createElement("script");
    const timer = setTimeout(() => reject(new Error("nuvio.tv took too long to answer")), CONFIG_TIMEOUT_MS);
    script.src = OFFICIAL_CONFIG_URL;
    script.async = true;
    script.onload = () => {
      clearTimeout(timer);
      if (window.__NUVIO_CONFIG__) resolve(window.__NUVIO_CONFIG__);
      else reject(new Error("nuvio.tv didn't share its server settings"));
    };
    script.onerror = () => {
      clearTimeout(timer);
      reject(new Error("Couldn't reach nuvio.tv"));
    };
    document.head.append(script);
  });
}

export async function initServer() {
  const custom = customServer();
  if (custom?.url && custom?.key) {
    server = { url: custom.url, key: custom.key, custom: true };
    return server;
  }
  try {
    const config = await loadOfficialScript();
    const url = trimUrl(config.supabaseUrl);
    const key = String(config.supabaseAnonKey || "").trim();
    if (!url || !key) throw new Error("nuvio.tv's settings are missing the server address");
    server = { url, key, custom: false };
    save("officialServer", server);
  } catch (error) {
    const cached = load("officialServer");
    if (!cached) throw error;
    server = cached;
  }
  return server;
}

// Self-hosted Nuvio servers describe themselves at /.well-known/nuvio.
export async function useCustomServer(address) {
  signOut();
  if (!address) {
    save("customServer", null);
    server = null;
    return initServer();
  }
  const base = trimUrl(address);
  if (!/^https:\/\//i.test(base)) throw new Error("The server address must start with https://");
  const res = await fetch(`${base}/.well-known/nuvio`);
  if (!res.ok) throw new Error(`No Nuvio server answered at ${base} (HTTP ${res.status})`);
  const info = await res.json();
  if (!info.publishable_key) throw new Error("That server didn't share a publishable key");
  const custom = { url: trimUrl(info.backend_url || base), key: String(info.publishable_key) };
  save("customServer", custom);
  server = { ...custom, custom: true };
  return server;
}

async function authCall(path, body) {
  const res = await fetch(`${server.url}/auth/v1/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", apikey: server.key },
    body: JSON.stringify(body)
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const error = new Error(
      data.error_description || data.msg || data.message || data.error || `HTTP ${res.status}`
    );
    error.status = res.status;
    throw error;
  }
  return data;
}

function storeSession(data) {
  session = {
    access: data.access_token,
    refresh: data.refresh_token,
    expiresAt: data.expires_at
      ? data.expires_at * 1000
      : Date.now() + (Number(data.expires_in) || 3600) * 1000,
    email: data.user?.email || session?.email || ""
  };
  save("session", session);
}

export async function signIn(email, password) {
  if (!server) throw new Error("The Nuvio server isn't reachable right now");
  const data = await authCall("token?grant_type=password", { email, password });
  if (!data.access_token || !data.refresh_token) throw new Error("Nuvio didn't return a session");
  ownerId = null;
  save("owner", null);
  storeSession(data);
}

export function signOut() {
  session = null;
  ownerId = null;
  save("session", null);
  save("owner", null);
  save("profile", null);
}

function refreshSession() {
  if (!refreshing) {
    refreshing = authCall("token?grant_type=refresh_token", { refresh_token: session.refresh })
      .then(storeSession)
      .catch((error) => {
        if (error.status === 400 || error.status === 401) {
          signOut();
          throw new AuthError("Your Nuvio session expired. Sign in again.");
        }
        throw error;
      })
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

async function accessToken() {
  if (!session) throw new AuthError("Not signed in");
  if (Date.now() > session.expiresAt - 60_000) await refreshSession();
  return session.access;
}

async function rest(path, { method = "GET", body } = {}, retried = false) {
  const token = await accessToken();
  const res = await fetch(`${server.url}/rest/v1/${path}`, {
    method,
    headers: {
      apikey: server.key,
      Authorization: `Bearer ${token}`,
      ...(body === undefined ? {} : { "Content-Type": "application/json" })
    },
    body: body === undefined ? undefined : JSON.stringify(body)
  });
  if (res.status === 401 && !retried) {
    await refreshSession();
    return rest(path, { method, body }, true);
  }
  const text = await res.text();
  if (!res.ok) {
    let message = text;
    try {
      const parsed = JSON.parse(text);
      message = parsed.message || parsed.error || text;
    } catch {
      // Plain-text error body.
    }
    const error = new Error(message || `HTTP ${res.status}`);
    error.status = res.status;
    throw error;
  }
  return text ? JSON.parse(text) : null;
}

const rpc = (name, args = {}) => rest(`rpc/${name}`, { method: "POST", body: args });

async function getOwnerId() {
  if (!ownerId) {
    ownerId = await rpc("get_sync_owner");
    save("owner", ownerId);
  }
  return ownerId;
}

export async function getProfiles() {
  const rows = await rpc("sync_pull_profiles");
  const profiles = (Array.isArray(rows) ? rows : [])
    .map((row) => ({
      index: Math.max(1, Math.trunc(Number(row.profile_index) || 1)),
      name: row.name || `Profile ${row.profile_index}`,
      color: row.avatar_color_hex || "#4f7cff",
      avatarUrl: row.avatar_url || null,
      usesPrimaryAddons: row.uses_primary_addons === true
    }))
    .sort((a, b) => a.index - b.index);
  if (profiles.length) return profiles;
  return [{ index: 1, name: "Main", color: "#4f7cff", avatarUrl: null, usesPrimaryAddons: false }];
}

// Profiles can share the primary profile's addons; Nuvio then stores them
// under profile 1 only.
export async function getAddonUrls(profile) {
  const profileId = profile.index !== 1 && profile.usesPrimaryAddons ? 1 : profile.index;
  let rows;
  try {
    const owner = await getOwnerId();
    rows = await rest(
      `addons?user_id=eq.${encodeURIComponent(owner)}&profile_id=eq.${profileId}` +
        "&select=url,name,enabled,sort_order&order=sort_order.asc"
    );
  } catch (error) {
    if (error instanceof AuthError) throw error;
    rows = await rpc("sync_pull_addons", { p_profile_id: profileId });
  }
  return (Array.isArray(rows) ? rows : [])
    .filter((row) => row.enabled !== false)
    .map((row) => row.url || row.base_url)
    .filter(Boolean);
}

export async function getLibrary(profileIndex) {
  const rows = [];
  for (let offset = 0; offset < 10 * LIBRARY_PAGE_SIZE; offset += LIBRARY_PAGE_SIZE) {
    const page = await rpc("sync_pull_library", {
      p_profile_id: profileIndex,
      p_limit: LIBRARY_PAGE_SIZE,
      p_offset: offset
    });
    if (!Array.isArray(page)) break;
    rows.push(...page);
    if (page.length < LIBRARY_PAGE_SIZE) break;
  }
  return rows
    .filter((row) => row.content_id)
    .map((row) => ({
      id: row.content_id,
      type: row.content_type || "movie",
      name: row.name || "Untitled",
      poster: row.poster || null,
      posterShape: String(row.poster_shape || "poster").toLowerCase(),
      background: row.background || null,
      description: row.description || "",
      releaseInfo: row.release_info || "",
      addonBase: row.addon_base_url || null,
      addedAt: Number(row.added_at) || 0
    }))
    .sort((a, b) => b.addedAt - a.addedAt);
}

export function progressKey(contentId, season, episode) {
  return season != null && episode != null ? `${contentId}_s${season}e${episode}` : contentId;
}

function toNumberOrNull(value) {
  if (value == null || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function mapProgressRow(row) {
  let positionMs;
  let durationMs;
  if (row.position_ms != null || row.duration_ms != null) {
    positionMs = Number(row.position_ms) || 0;
    durationMs = Number(row.duration_ms) || 0;
  } else {
    const position = Number(row.position) || 0;
    const duration = Number(row.duration) || 0;
    const inMilliseconds = duration > AMBIGUOUS_SECONDS_LIMIT;
    positionMs = inMilliseconds ? position : position * 1000;
    durationMs = inMilliseconds ? duration : duration * 1000;
  }
  const lastWatched = Number(row.last_watched);
  let updatedAt = Date.parse(row.updated_at || "") || 0;
  if (Number.isFinite(lastWatched) && lastWatched > 0) {
    updatedAt = lastWatched > 1e12 ? lastWatched : lastWatched * 1000;
  }
  const videoId = String(row.video_id || "");
  const season = toNumberOrNull(row.season ?? row.season_number);
  const episode = toNumberOrNull(row.episode ?? row.episode_number);
  return {
    contentId: row.content_id,
    contentType: row.content_type || "movie",
    videoId: videoId && !videoId.startsWith(SYNTHETIC_EPISODE_PREFIX) ? videoId : null,
    season,
    episode: episode && episode > 0 ? episode : null,
    positionMs,
    durationMs,
    updatedAt
  };
}

export async function getProgress(profileIndex) {
  const rows = await rpc("sync_pull_watch_progress", { p_profile_id: profileIndex });
  return (Array.isArray(rows) ? rows : [])
    .filter((row) => row.content_id)
    .map(mapProgressRow)
    .sort((a, b) => b.updatedAt - a.updatedAt);
}

function clientId() {
  let id = load("clientId");
  if (!id) {
    id = crypto.randomUUID?.() || `shelf-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    save("clientId", id);
  }
  return id;
}

// sync_push_watch_progress upserts by progress key, so sending one entry
// leaves the rest of the profile's history alone.
export function pushProgress(profileIndex, item) {
  const entry = {
    content_id: item.contentId,
    content_type: item.contentType || "movie",
    video_id: item.videoId || item.contentId,
    season: item.season ?? null,
    episode: item.episode ?? null,
    position: Math.max(0, Math.trunc(item.positionMs)),
    duration: Math.max(0, Math.trunc(item.durationMs)),
    last_watched: Date.now(),
    progress_key: progressKey(item.contentId, item.season, item.episode)
  };
  return rpc("sync_push_watch_progress", {
    p_profile_id: profileIndex,
    p_entries: [entry],
    p_origin_client_id: clientId()
  });
}

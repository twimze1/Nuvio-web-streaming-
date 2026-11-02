// Client for the Stremio addon protocol, which Nuvio addons speak:
//   {base}/manifest.json
//   {base}/{resource}/{type}/{id}[/{extra}].json
const TIMEOUT_MS = 15000;
const DEFAULT_TTL_MS = 5 * 60 * 1000;
const responses = new Map();

export function splitAddonUrl(url) {
  const raw = String(url || "").trim().replace(/^stremio:\/\//i, "https://");
  const queryStart = raw.indexOf("?");
  const query = queryStart >= 0 ? raw.slice(queryStart) : "";
  const path = (queryStart >= 0 ? raw.slice(0, queryStart) : raw)
    .replace(/\/manifest\.json$/i, "")
    .replace(/\/+$/, "");
  return { path, query };
}

export function addonKey(url) {
  const { path, query } = splitAddonUrl(url);
  return (path + query).toLowerCase();
}

function describeFetchError(error) {
  if (error?.name === "AbortError") return "Timed out";
  if (error instanceof TypeError) return "Couldn't connect (offline, or the addon blocks web apps)";
  return error?.message || "Request failed";
}

export async function fetchJson(url, { ttl = DEFAULT_TTL_MS } = {}) {
  const hit = responses.get(url);
  if (hit && Date.now() - hit.at < ttl) return hit.promise;
  const promise = (async () => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
    try {
      const res = await fetch(url, { signal: controller.signal });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (error) {
      throw new Error(describeFetchError(error));
    } finally {
      clearTimeout(timer);
    }
  })();
  responses.set(url, { at: Date.now(), promise });
  promise.catch(() => responses.delete(url));
  return promise;
}

function normalizeResources(manifest) {
  return (manifest.resources || [])
    .map((resource) =>
      typeof resource === "string"
        ? { name: resource, types: manifest.types || null, idPrefixes: manifest.idPrefixes || null }
        : {
            name: resource?.name,
            types: resource?.types || manifest.types || null,
            idPrefixes: resource?.idPrefixes || manifest.idPrefixes || null
          }
    )
    .filter((resource) => resource.name);
}

export async function loadAddon(url) {
  const { path, query } = splitAddonUrl(url);
  let host = path;
  try {
    host = new URL(path).hostname;
  } catch {
    // Keep the raw text as the name.
  }
  const addon = {
    url,
    path,
    query,
    key: (path + query).toLowerCase(),
    name: host,
    logo: null,
    manifest: null,
    resources: [],
    catalogs: [],
    error: null
  };
  if (location.protocol === "https:" && /^http:\/\//i.test(path)) {
    addon.error = "Uses http://, which Safari blocks on secure sites";
    return addon;
  }
  try {
    const manifest = await fetchJson(`${path}/manifest.json${query}`, { ttl: 10 * 60 * 1000 });
    addon.manifest = manifest;
    addon.name = manifest.name || host;
    addon.logo = manifest.logo || null;
    addon.resources = normalizeResources(manifest);
    addon.catalogs = (manifest.catalogs || []).filter((catalog) => catalog?.type && catalog?.id);
  } catch (error) {
    addon.error = error.message;
  }
  return addon;
}

export function supports(addon, resourceName, type, id) {
  if (!addon?.manifest) return false;
  const resource = addon.resources.find((r) => r.name === resourceName);
  if (!resource) return false;
  if (type && resource.types && !resource.types.includes(type)) return false;
  if (id && resource.idPrefixes?.length && !resource.idPrefixes.some((p) => String(id).startsWith(p))) {
    return false;
  }
  return true;
}

export function catalogExtras(catalog) {
  const extra = Array.isArray(catalog.extra) ? catalog.extra : [];
  const names = new Set([...extra.map((e) => e.name), ...(catalog.extraSupported || [])]);
  const required = new Set([
    ...extra.filter((e) => e.isRequired).map((e) => e.name),
    ...(catalog.extraRequired || [])
  ]);
  const genre = extra.find((e) => e.name === "genre");
  return {
    search: names.has("search"),
    skip: names.has("skip"),
    genres: genre?.options || catalog.genres || [],
    required
  };
}

export const isBrowsable = (catalog) => catalogExtras(catalog).required.size === 0;

function resourceUrl(addon, resource, type, id, extra) {
  const enc = encodeURIComponent;
  const pairs = Object.entries(extra || {})
    .filter(([, value]) => value != null && value !== "")
    .map(([name, value]) => `${enc(name)}=${enc(value)}`);
  const extraPart = pairs.length ? `/${pairs.join("&")}` : "";
  return `${addon.path}/${resource}/${enc(type)}/${enc(id)}${extraPart}.json${addon.query}`;
}

export async function getCatalog(addon, catalog, extra) {
  const data = await fetchJson(resourceUrl(addon, "catalog", catalog.type, catalog.id, extra));
  return (Array.isArray(data?.metas) ? data.metas : []).filter((meta) => meta?.id);
}

export async function getMeta(addon, type, id) {
  const data = await fetchJson(resourceUrl(addon, "meta", type, id));
  return data?.meta || null;
}

export async function getStreams(addon, type, id) {
  const data = await fetchJson(resourceUrl(addon, "stream", type, id), { ttl: 60 * 1000 });
  return Array.isArray(data?.streams) ? data.streams.filter(Boolean) : [];
}

export async function getSubtitles(addon, type, id) {
  const data = await fetchJson(resourceUrl(addon, "subtitles", type, id));
  return Array.isArray(data?.subtitles) ? data.subtitles.filter((s) => s?.url) : [];
}

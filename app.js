// Boot and hash router. Browsing views (home, catalogs, search, details) are
// kept alive in a small cache so going back restores them instantly, scroll
// positions included.
import * as nuvio from "./nuvio.js";
import { h, brandMark, spinner, errorBlock, closeSheet } from "./ui.js";
import { state, loadAccount } from "./state.js";
import {
  homeView,
  catalogView,
  searchView,
  detailView,
  profilesView,
  loginView,
  settingsView
} from "./views.js";

const VIEW_CACHE_SIZE = 8;
const app = document.getElementById("app");
const viewCache = new Map();
const scrollPositions = new Map();
let currentHash = null;

const decode = (value) => {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
};

const routes = [
  { pattern: /^\/?$/, cache: true, render: () => homeView() },
  {
    pattern: /^\/catalog\/(\d+)\/([^/]+)\/([^/]+)$/,
    cache: true,
    render: (m) => catalogView({ addonIndex: Number(m[1]), type: decode(m[2]), catalogId: decode(m[3]) })
  },
  { pattern: /^\/search$/, cache: true, render: () => searchView() },
  {
    pattern: /^\/meta\/([^/]+)\/([^/]+)$/,
    cache: true,
    render: (m, query) => detailView({ type: decode(m[1]), id: decode(m[2]), query })
  },
  { pattern: /^\/profiles$/, render: () => profilesView() },
  { pattern: /^\/settings$/, open: true, render: () => settingsView() },
  { pattern: /^\/login$/, open: true, render: () => loginView() }
];

function trackHistory(hash) {
  const stack = state.navStack;
  if (stack.length > 1 && stack[stack.length - 2] === hash) stack.pop();
  else if (stack[stack.length - 1] !== hash) stack.push(hash);
}

function route({ fresh = false } = {}) {
  const hash = location.hash || "#/";
  const [path, queryString] = hash.slice(1).split("?");
  const query = Object.fromEntries(new URLSearchParams(queryString || ""));
  const match = routes.find((r) => r.pattern.test(path || "/")) || routes[0];

  if (!state.signedIn && !state.guest && !match.open) {
    location.replace("#/login");
    return;
  }
  if (state.signedIn && !state.profile && path !== "/profiles" && !match.open) {
    location.replace("#/profiles");
    return;
  }

  closeSheet();
  if (currentHash) scrollPositions.set(currentHash, window.scrollY);
  trackHistory(hash);
  currentHash = hash;

  const cached = viewCache.get(hash);
  let view;
  if (match.cache && !fresh && cached && cached.version === state.version) {
    view = cached.view;
  } else {
    view = match.render(path.match(match.pattern), query);
    if (match.cache) {
      viewCache.delete(hash);
      viewCache.set(hash, { view, version: state.version });
      while (viewCache.size > VIEW_CACHE_SIZE) viewCache.delete(viewCache.keys().next().value);
    }
    scrollPositions.delete(hash);
  }
  app.replaceChildren(view);
  window.scrollTo(0, scrollPositions.get(hash) || 0);
}

function splash(content) {
  app.replaceChildren(h("div", { class: "splash" }, h("div", { class: "auth-brand" }, brandMark(), h("span", {}, "Shelf")), content));
}

async function boot() {
  state.navStack = [];
  splash(spinner());
  try {
    await nuvio.initServer();
  } catch (error) {
    console.warn("Nuvio server unavailable", error);
  }
  try {
    await loadAccount();
  } catch (error) {
    if (error instanceof nuvio.AuthError) {
      await loadAccount().catch(() => {});
    } else {
      splash(errorBlock(new Error(`Couldn't load your account: ${error.message}`), () => location.reload()));
      return;
    }
  }
  window.addEventListener("hashchange", () => route());
  window.addEventListener("shelf:rerender", () => route({ fresh: true }));
  route();
}

boot();

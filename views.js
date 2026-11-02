// Screens. Each view function returns a detached element that the router
// mounts; slow data (catalogs, meta) fills in after the view is on screen.
import { h, icon, brandMark, spinner, artImg, errorBlock, typeLabel, fmtTime, toast } from "./ui.js";
import * as nuvio from "./nuvio.js";
import * as addons from "./addons.js";
import { load, save } from "./store.js";
import {
  state,
  loadAccount,
  selectProfile,
  ensureLibrary,
  ensureProgress,
  isCompleted,
  rememberPreview,
  findAddonByBase,
  resolveMeta,
  sortedVideos,
  findVideo,
  nextVideo,
  firstVideo,
  extraAddonUrls,
  setExtraAddonUrls
} from "./state.js";
import { openStreams } from "./streams.js";

const ROW_LIMIT = 30;
const CONTINUE_LIMIT = 20;

// ---------- shared pieces ----------

export function goBack() {
  if (state.navStack.length > 1) history.back();
  else location.replace("#/");
}

function rerender() {
  window.dispatchEvent(new CustomEvent("shelf:rerender"));
}

function topBar({ title, back = false, actions = [], overlay = false }) {
  return h(
    "header",
    { class: `topbar${overlay ? " topbar-overlay" : ""}` },
    back
      ? h("button", { class: "icon-btn", "aria-label": "Back", onclick: goBack }, icon("back"))
      : h("a", { class: "brand", href: "#/", "aria-label": "Shelf home" }, brandMark(), h("span", {}, "Shelf")),
    title ? h("h1", { class: "topbar-title" }, title) : h("div", { class: "topbar-fill" }),
    h("div", { class: "topbar-actions" }, ...actions)
  );
}

function safeColor(value) {
  return /^#[0-9a-f]{3,8}$/i.test(String(value || "")) ? value : "#4f7cff";
}

function avatar(profile, size = "md") {
  const initial = () =>
    h("span", { class: `avatar avatar-${size}`, style: `--avatar:${safeColor(profile.color)}` }, (profile.name || "?").charAt(0).toUpperCase());
  if (!profile.avatarUrl || !/^https:\/\//i.test(profile.avatarUrl)) return initial();
  return h("img", {
    class: `avatar avatar-${size}`,
    src: profile.avatarUrl,
    alt: "",
    referrerpolicy: "no-referrer",
    onerror: (event) => event.target.replaceWith(initial())
  });
}

export function metaHref(type, id, addon) {
  const index = addon ? state.addons.indexOf(addon) : -1;
  return `#/meta/${encodeURIComponent(type)}/${encodeURIComponent(id)}${index >= 0 ? `?a=${index}` : ""}`;
}

function posterCard(meta, fallbackType, addon) {
  const type = meta.type || fallbackType;
  rememberPreview(type, meta, addon);
  const shape = ["landscape", "square"].includes(String(meta.posterShape).toLowerCase())
    ? String(meta.posterShape).toLowerCase()
    : "poster";
  return h(
    "a",
    { class: `card card-${shape}`, href: metaHref(type, meta.id, addon) },
    h("div", { class: "card-art" }, artImg(meta.poster, meta.name)),
    h("div", { class: "card-title" }, meta.name || "")
  );
}

function skeletonCards(count, shape = "poster") {
  return Array.from({ length: count }, () =>
    h("div", { class: `card card-${shape} skeleton`, "aria-hidden": "true" }, h("div", { class: "card-art" }), h("div", { class: "card-title" }))
  );
}

const lazyTasks = new WeakMap();
const lazyObserver = new IntersectionObserver(
  (entries) => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      lazyObserver.unobserve(entry.target);
      const task = lazyTasks.get(entry.target);
      lazyTasks.delete(entry.target);
      task?.();
    }
  },
  { rootMargin: "800px 0px" }
);

function whenNear(element, task) {
  lazyTasks.set(element, task);
  lazyObserver.observe(element);
}

function rowSection({ title, tag, href, shape = "poster" }) {
  const scroller = h("div", { class: "scroller" }, skeletonCards(8, shape));
  const section = h(
    "section",
    { class: "row" },
    h(
      "div",
      { class: "row-head" },
      h("h2", {}, title, tag ? h("span", { class: "row-tag" }, tag) : null),
      href ? h("a", { class: "see-all", href }, "See all") : null
    ),
    scroller
  );
  return { section, scroller };
}

// ---------- home ----------

export function homeView() {
  const browsable = state.addons.filter((addon) => addon.catalogs.some(addons.isBrowsable));
  const broken = state.addons.filter((addon) => addon.error);
  const actions = [
    h("a", { class: "icon-btn", href: "#/search", "aria-label": "Search" }, icon("search")),
    state.signedIn && state.profile
      ? h("a", { class: "avatar-btn", href: "#/profiles", "aria-label": `Switch profile (now ${state.profile.name})` }, avatar(state.profile, "sm"))
      : null,
    h("a", { class: "icon-btn", href: "#/settings", "aria-label": "Settings" }, icon("settings"))
  ];
  const root = h("div", { class: "view home" }, topBar({ actions }));

  if (!state.addons.length) {
    root.append(
      h(
        "div",
        { class: "empty" },
        h("h2", {}, "No addons yet"),
        h(
          "p",
          {},
          state.signedIn
            ? "This Nuvio profile has no addons installed. Install your collection addon in the Nuvio app, or add its manifest link here."
            : "Add your collection addon's manifest link to start browsing."
        ),
        h("a", { class: "btn btn-primary", href: "#/settings" }, "Add an addon")
      )
    );
    return root;
  }

  let filter = load("homeFilter", "all");
  if (filter !== "all" && !browsable.some((addon) => addon.key === filter)) filter = "all";
  const sections = h("div", { class: "sections" });

  const chips = h(
    "div",
    { class: "chips", role: "tablist", "aria-label": "Show catalogs from" },
    [{ key: "all", name: "All" }, ...browsable].map((addon) =>
      h(
        "button",
        {
          class: "chip",
          role: "tab",
          "aria-selected": String(addon.key === filter),
          "data-key": addon.key,
          onclick: () => {
            filter = addon.key;
            save("homeFilter", filter);
            chips.querySelectorAll(".chip").forEach((chip) => chip.setAttribute("aria-selected", String(chip.dataset.key === filter)));
            renderSections();
            window.scrollTo({ top: 0 });
          }
        },
        addon.name
      )
    )
  );
  if (browsable.length > 1) root.append(chips);
  root.append(sections);

  function renderSections() {
    sections.replaceChildren();
    if (filter === "all") sections.append(...[continueRow(), libraryRow()].filter(Boolean));
    for (const addon of browsable) {
      if (filter !== "all" && addon.key !== filter) continue;
      for (const catalog of addon.catalogs.filter(addons.isBrowsable)) sections.append(catalogRow(addon, catalog));
    }
    if (filter === "all" && broken.length) {
      sections.append(
        h(
          "div",
          { class: "notice" },
          h("strong", {}, `${broken.length} addon${broken.length === 1 ? "" : "s"} didn't load`),
          h("ul", {}, broken.map((addon) => h("li", {}, `${addon.name}: ${addon.error}`)))
        )
      );
    }
  }
  renderSections();
  return root;
}

function catalogRow(addon, catalog) {
  const index = state.addons.indexOf(addon);
  const { section, scroller } = rowSection({
    title: catalog.name || catalog.id,
    tag: typeLabel(catalog.type),
    href: `#/catalog/${index}/${encodeURIComponent(catalog.type)}/${encodeURIComponent(catalog.id)}`
  });
  const load = () =>
    addons
      .getCatalog(addon, catalog)
      .then((metas) => {
        if (!metas.length) {
          section.remove();
          return;
        }
        scroller.replaceChildren(...metas.slice(0, ROW_LIMIT).map((meta) => posterCard(meta, catalog.type, addon)));
      })
      .catch((error) =>
        scroller.replaceChildren(
          errorBlock(new Error(`${addon.name}: ${error.message}`), () => {
            scroller.replaceChildren(...skeletonCards(8));
            load();
          })
        )
      );
  whenNear(section, load);
  return section;
}

function libraryRow() {
  if (!state.signedIn) return null;
  const { section, scroller } = rowSection({ title: "Your library" });
  whenNear(section, () =>
    ensureLibrary()
      .then((items) => {
        if (!items.length) {
          section.remove();
          return;
        }
        scroller.replaceChildren(
          ...items.slice(0, 60).map((item) => posterCard(item, item.type, findAddonByBase(item.addonBase)))
        );
      })
      .catch(() => section.remove())
  );
  return section;
}

function continueRow() {
  const { section, scroller } = rowSection({ title: "Continue watching", shape: "landscape" });
  scroller.replaceChildren(...skeletonCards(3, "landscape"));
  ensureProgress()
    .then(({ list }) => {
      const latest = [];
      const seen = new Set();
      for (const item of list) {
        if (seen.has(item.contentId)) continue;
        seen.add(item.contentId);
        const episodic = item.season != null || item.episode != null;
        // Finished movies drop out; finished episodes may have a next one.
        if (isCompleted(item) && !episodic) continue;
        latest.push(item);
        if (latest.length >= CONTINUE_LIMIT) break;
      }
      if (!latest.length) {
        section.remove();
        return;
      }
      scroller.replaceChildren(...latest.map(continueCard));
    })
    .catch(() => section.remove());
  return section;
}

function continueCard(progress) {
  const art = h("div", { class: "card-art" }, h("div", { class: "art-fallback" }));
  const title = h("div", { class: "card-title" }, "");
  const sub = h("div", { class: "card-sub" }, "");
  const bar = h("div", { class: "progress" }, h("span", { style: `width:${progressPercent(progress)}%` }));
  const card = h("a", { class: "card card-landscape card-continue", href: metaHref(progress.contentType, progress.contentId) }, art, bar, title, sub);
  resolveMeta(progress.contentType, progress.contentId)
    .then(({ meta, addon }) => {
      card.href = metaHref(progress.contentType, progress.contentId, addon);
      title.textContent = meta.name || "";
      art.replaceChildren(artImg(meta.background || meta.poster, meta.name));
      const videos = progress.contentType === "movie" ? [] : sortedVideos(meta);
      const watched = findVideo(videos, progress);
      if (watched && isCompleted(progress)) {
        const next = nextVideo(videos, watched);
        if (!next) {
          card.remove();
          return;
        }
        sub.textContent = `Up next · S${next.season} E${next.episode}`;
        bar.remove();
      } else if (watched) {
        sub.textContent = `S${watched.season} E${watched.episode} · ${fmtTime(progress.durationMs - progress.positionMs)} left`;
      } else if (isCompleted(progress)) {
        card.remove();
      } else if (progress.durationMs) {
        sub.textContent = `${fmtTime(progress.durationMs - progress.positionMs)} left`;
      }
    })
    .catch(() => card.remove());
  return card;
}

function progressPercent(progress) {
  if (!progress?.durationMs) return 0;
  return Math.max(2, Math.min(100, Math.round((progress.positionMs / progress.durationMs) * 100)));
}

// ---------- catalog ----------

export function catalogView({ addonIndex, type, catalogId }) {
  const addon = state.addons[addonIndex];
  const catalog = addon?.catalogs.find((c) => c.type === type && c.id === catalogId);
  if (!catalog) {
    return h("div", { class: "view" }, topBar({ back: true, title: "Not found" }), h("p", { class: "muted pad" }, "This catalog isn't available anymore."));
  }
  const extras = addons.catalogExtras(catalog);
  const grid = h("div", { class: "grid" });
  const sentinel = h("div", { class: "grid-sentinel" }, spinner());
  const seen = new Set();
  let genre = null;
  let loading = false;
  let done = false;
  let generation = 0;

  async function loadMore() {
    if (loading || done) return;
    loading = true;
    const mine = generation;
    try {
      const extra = {};
      if (genre) extra.genre = genre;
      if (seen.size && extras.skip) extra.skip = seen.size;
      const metas = await addons.getCatalog(addon, catalog, extra);
      if (mine !== generation) return;
      const fresh = metas.filter((meta) => !seen.has(meta.id));
      fresh.forEach((meta) => seen.add(meta.id));
      grid.append(...fresh.map((meta) => posterCard(meta, catalog.type, addon)));
      if (!fresh.length || !extras.skip) {
        done = true;
        sentinel.replaceChildren(seen.size ? "" : h("p", { class: "muted" }, "Nothing here."));
      }
    } catch (error) {
      if (mine === generation) {
        done = true;
        sentinel.replaceChildren(
          errorBlock(error, () => {
            done = false;
            sentinel.replaceChildren(spinner());
            loadMore();
          })
        );
      }
    } finally {
      if (mine === generation) loading = false;
    }
    // The observer only fires on changes, so keep filling a short page.
    if (mine === generation && !done && sentinel.isConnected && sentinel.getBoundingClientRect().top < innerHeight + 800) {
      loadMore();
    }
  }

  function reset() {
    generation += 1;
    seen.clear();
    grid.replaceChildren();
    loading = false;
    done = false;
    sentinel.replaceChildren(spinner());
    loadMore();
  }

  new IntersectionObserver((entries) => entries.some((e) => e.isIntersecting) && loadMore(), {
    rootMargin: "800px 0px"
  }).observe(sentinel);

  const genrePicker = extras.genres.length
    ? h(
        "label",
        { class: "select-wrap" },
        h("span", { class: "visually-hidden" }, "Genre"),
        h(
          "select",
          {
            class: "select",
            onchange: (event) => {
              genre = event.target.value || null;
              reset();
            }
          },
          h("option", { value: "" }, "All genres"),
          extras.genres.map((g) => h("option", { value: g }, g))
        )
      )
    : null;

  loadMore();
  return h(
    "div",
    { class: "view" },
    topBar({ back: true, title: catalog.name || catalog.id }),
    h("div", { class: "catalog-head" }, h("span", { class: "muted" }, `${addon.name} · ${typeLabel(catalog.type)}`), genrePicker),
    grid,
    sentinel
  );
}

// ---------- search ----------

export function searchView() {
  const searchable = [];
  for (const addon of state.addons) {
    for (const catalog of addon.catalogs) {
      if (addons.catalogExtras(catalog).search) searchable.push({ addon, catalog });
    }
  }
  const input = h("input", {
    class: "search-input",
    type: "search",
    placeholder: "Search your addons",
    enterkeyhint: "search",
    autocapitalize: "off",
    autocomplete: "off",
    spellcheck: "false",
    "aria-label": "Search"
  });
  const results = h(
    "div",
    { class: "sections" },
    h("p", { class: "muted pad" }, searchable.length ? "Search across every addon that supports it." : "None of your addons support search.")
  );
  let timer = null;
  let generation = 0;

  function run(query) {
    generation += 1;
    const mine = generation;
    if (!query || !searchable.length) return;
    let pending = searchable.length;
    let shown = 0;
    const finish = () => {
      pending -= 1;
      if (!pending && !shown && mine === generation) {
        results.replaceChildren(h("p", { class: "muted pad" }, `No results for "${query}".`));
      }
    };
    results.replaceChildren(
      ...searchable.map(({ addon, catalog }) => {
        const { section, scroller } = rowSection({ title: catalog.name || addon.name, tag: `${typeLabel(catalog.type)} · ${addon.name}` });
        addons
          .getCatalog(addon, catalog, { search: query })
          .then((metas) => {
            if (mine !== generation) return;
            if (!metas.length) section.remove();
            else {
              shown += 1;
              scroller.replaceChildren(...metas.slice(0, ROW_LIMIT).map((meta) => posterCard(meta, catalog.type, addon)));
            }
          })
          .catch(() => section.remove())
          .finally(finish);
        return section;
      })
    );
  }

  input.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(() => run(input.value.trim()), 450);
  });
  const form = h(
    "form",
    {
      class: "search-form",
      role: "search",
      onsubmit: (event) => {
        event.preventDefault();
        clearTimeout(timer);
        run(input.value.trim());
        input.blur();
      }
    },
    icon("search"),
    input
  );
  setTimeout(() => input.focus(), 60);
  return h("div", { class: "view" }, topBar({ back: true, title: "Search" }), form, results);
}

// ---------- detail ----------

const SINGULAR = { movie: "Movie", series: "Series", tv: "TV", channel: "Channel" };

export function detailView({ type, id, query }) {
  const hint = query.a != null ? state.addons[Number(query.a)] : null;
  const body = h("div", { class: "detail-loading" }, spinner());
  const root = h("div", { class: "view detail" }, topBar({ back: true, overlay: true }), body);
  const render = () =>
    Promise.all([resolveMeta(type, id, hint), ensureProgress()])
      .then(([{ meta, addon, partial }, progress]) => body.replaceWith(renderDetail(type, meta, addon, progress, partial)))
      .catch((error) =>
        body.replaceChildren(
          errorBlock(error, () => {
            body.replaceChildren(spinner());
            render();
          })
        )
      );
  render();
  return root;
}

function shortEpisode(video) {
  if (video.season != null && video.episode != null) return `S${video.season} E${video.episode}`;
  return video.title || "";
}

function primaryAction(meta, videos, progress) {
  if (!videos.length) {
    const saved = progress.byKey.get(meta.id);
    const resume = saved && !isCompleted(saved) && saved.positionMs > 30000;
    return { video: null, label: resume ? `Resume · ${fmtTime(saved.positionMs)}` : "Play" };
  }
  const latest = progress.byContent.get(meta.id);
  const watched = findVideo(videos, latest);
  if (watched && !isCompleted(latest)) return { video: watched, label: `Resume ${shortEpisode(watched)}` };
  const next = watched && nextVideo(videos, watched);
  if (next) return { video: next, label: `Play ${shortEpisode(next)}` };
  const first = firstVideo(videos);
  return { video: first, label: first ? `Play ${shortEpisode(first)}` : "Play" };
}

function renderDetail(type, meta, addon, progress, partial) {
  const videos = type === "movie" ? [] : sortedVideos(meta);
  const action = primaryAction(meta, videos, progress);
  const facts = [
    meta.releaseInfo || meta.year,
    meta.runtime,
    meta.imdbRating ? `★ ${meta.imdbRating}` : null,
    SINGULAR[type] || typeLabel(type)
  ].filter(Boolean);
  const genres = Array.isArray(meta.genres) ? meta.genres : [];

  return h(
    "div",
    { class: "detail-content" },
    h(
      "div",
      { class: "hero" },
      meta.background ? artImg(meta.background, "", "hero-bg") : null,
      h("div", { class: "hero-fade" })
    ),
    h(
      "div",
      { class: "detail-main" },
      h(
        "div",
        { class: "detail-top" },
        h("div", { class: "detail-poster" }, artImg(meta.poster, meta.name)),
        h("div", { class: "detail-heading" }, h("h1", {}, meta.name || "Untitled"), facts.length ? h("p", { class: "detail-facts" }, facts.join(" · ")) : null)
      ),
      h(
        "div",
        { class: "detail-actions" },
        h(
          "button",
          { class: "btn btn-primary btn-play", onclick: () => openStreams({ type, meta, video: action.video }) },
          icon("play"),
          action.label
        )
      ),
      partial ? h("p", { class: "muted small" }, "Only basic info is available; none of your addons returned full details.") : null,
      meta.description ? h("p", { class: "detail-desc" }, meta.description) : null,
      genres.length ? h("div", { class: "tags" }, genres.slice(0, 6).map((g) => h("span", { class: "tag" }, g))) : null,
      addon ? h("p", { class: "muted small" }, `Details from ${addon.name}`) : null,
      videos.length ? episodesSection(type, meta, videos, progress, action.video) : null
    )
  );
}

function seasonName(season) {
  if (season == null) return "Episodes";
  return season === 0 ? "Specials" : `Season ${season}`;
}

function episodesSection(type, meta, videos, progress, focusVideo) {
  const seasons = [...new Set(videos.map((v) => v.season))];
  let selected = focusVideo ? focusVideo.season : seasons[0];
  const list = h("div", { class: "episodes" });
  const tabs = h(
    "div",
    { class: "chips season-tabs", role: "tablist", "aria-label": "Seasons" },
    seasons.map((season) =>
      h(
        "button",
        {
          class: "chip",
          role: "tab",
          "aria-selected": String(season === selected),
          onclick: (event) => {
            selected = season;
            tabs.querySelectorAll(".chip").forEach((chip) => chip.setAttribute("aria-selected", String(chip === event.currentTarget)));
            show();
          }
        },
        seasonName(season)
      )
    )
  );
  const now = Date.now();

  function episodeRow(video) {
    const saved = progress.byKey.get(nuvio.progressKey(meta.id, video.season, video.episode));
    const released = video.released ? new Date(video.released) : null;
    const upcoming = released && released.getTime() > now;
    const date = released && !Number.isNaN(released.getTime())
      ? released.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })
      : "";
    return h(
      "button",
      {
        class: `episode${upcoming ? " episode-upcoming" : ""}${video === focusVideo ? " episode-focus" : ""}`,
        onclick: () => openStreams({ type, meta, video })
      },
      h(
        "div",
        { class: "episode-thumb" },
        artImg(video.thumbnail, video.episode != null ? `E${video.episode}` : ""),
        saved ? h("div", { class: "progress" }, h("span", { style: `width:${progressPercent(saved)}%` })) : null
      ),
      h(
        "div",
        { class: "episode-text" },
        h("div", { class: "episode-title" }, `${video.episode != null ? `${video.episode}. ` : ""}${video.title || `Episode ${video.episode ?? ""}`}`),
        h(
          "div",
          { class: "episode-meta" },
          [upcoming ? `Coming ${date}` : date, saved && isCompleted(saved) ? "Watched" : null].filter(Boolean).join(" · ")
        ),
        video.overview ? h("p", { class: "episode-overview" }, video.overview) : null
      )
    );
  }

  function show() {
    list.replaceChildren(...videos.filter((v) => v.season === selected).map(episodeRow));
  }
  show();
  return h("section", { class: "episodes-section" }, seasons.length > 1 ? tabs : h("h2", {}, seasonName(seasons[0])), list);
}

// ---------- profiles ----------

export function profilesView() {
  const grid = h(
    "div",
    { class: "profiles" },
    state.profiles.map((profile) =>
      h(
        "button",
        {
          class: `profile${state.profile?.index === profile.index ? " profile-active" : ""}`,
          onclick: async (event) => {
            event.currentTarget.classList.add("profile-loading");
            selectProfile(profile);
            try {
              await loadAccount();
              location.hash = "#/";
            } catch (error) {
              toast(error.message);
            }
          }
        },
        avatar(profile, "lg"),
        h("span", {}, profile.name)
      )
    )
  );
  return h(
    "div",
    { class: "view" },
    topBar({ back: Boolean(state.profile), title: "Who's watching?" }),
    grid
  );
}

// ---------- sign in ----------

export function loginView() {
  const server = nuvio.getServer();
  const email = h("input", { id: "email", type: "email", autocomplete: "username", inputmode: "email", autocapitalize: "off", spellcheck: "false", required: true });
  const password = h("input", { id: "password", type: "password", autocomplete: "current-password", required: true });
  const error = h("p", { class: "form-error", role: "alert", hidden: true });
  const submit = h("button", { class: "btn btn-primary btn-block", type: "submit" }, "Sign in");

  const form = h(
    "form",
    {
      class: "auth-form",
      onsubmit: async (event) => {
        event.preventDefault();
        error.hidden = true;
        submit.disabled = true;
        submit.textContent = "Signing in…";
        try {
          await nuvio.signIn(email.value.trim(), password.value);
          save("guest", null);
          await loadAccount();
          location.hash = state.profile ? "#/" : "#/profiles";
        } catch (err) {
          error.textContent = err.message === "Invalid login credentials" ? "That email and password don't match a Nuvio account." : err.message;
          error.hidden = false;
          submit.disabled = false;
          submit.textContent = "Sign in";
        }
      }
    },
    h("label", { for: "email" }, "Email"),
    email,
    h("label", { for: "password" }, "Password"),
    password,
    error,
    submit
  );

  return h(
    "div",
    { class: "view auth" },
    h(
      "div",
      { class: "auth-card" },
      h("div", { class: "auth-brand" }, brandMark(), h("span", {}, "Shelf")),
      h("h1", {}, "Sign in with your Nuvio account"),
      h("p", { class: "muted" }, "Your profiles, addons, library and progress come straight from Nuvio."),
      server
        ? form
        : errorBlock(new Error("Can't reach the Nuvio server right now."), () => location.reload()),
      h(
        "div",
        { class: "auth-links" },
        h(
          "button",
          {
            class: "link-btn",
            onclick: async () => {
              save("guest", true);
              await loadAccount();
              location.hash = state.addons.length ? "#/" : "#/settings";
            }
          },
          "Use without an account"
        ),
        h("a", { class: "link-btn", href: "#/settings" }, "Server settings")
      ),
      h("p", { class: "fineprint" }, "Unofficial web client. Not affiliated with Nuvio. Your session stays in this browser.")
    )
  );
}

// ---------- settings ----------

export function settingsView() {
  const server = nuvio.getServer();
  const custom = nuvio.customServer();
  const sections = [];

  if (state.signedIn) {
    sections.push(
      settingsSection(
        "Account",
        h("p", {}, "Signed in as ", h("strong", {}, nuvio.accountEmail() || "your Nuvio account")),
        state.profile ? h("div", { class: "setting-row" }, avatar(state.profile, "sm"), h("span", {}, state.profile.name), h("a", { class: "btn btn-ghost btn-sm", href: "#/profiles" }, "Switch")) : null,
        h(
          "button",
          {
            class: "btn btn-ghost",
            onclick: async () => {
              nuvio.signOut();
              await loadAccount();
              location.hash = "#/login";
            }
          },
          "Sign out"
        )
      )
    );
  } else {
    sections.push(
      settingsSection(
        "Account",
        h("p", { class: "muted" }, "Not signed in. Only addons added on this device are used."),
        h(
          "button",
          {
            class: "btn btn-primary",
            onclick: () => {
              save("guest", null);
              state.guest = false;
              location.hash = "#/login";
            }
          },
          "Sign in to Nuvio"
        )
      )
    );
  }

  const addonList = state.addons.length
    ? h(
        "ul",
        { class: "addon-list" },
        state.addons.map((addon) =>
          h(
            "li",
            { class: "addon-item" },
            addon.logo ? artImg(addon.logo, "", "addon-logo") : h("span", { class: "addon-logo art-fallback" }),
            h(
              "div",
              { class: "addon-text" },
              h("strong", {}, addon.name),
              h(
                "span",
                { class: addon.error ? "error-text small" : "muted small" },
                addon.error ||
                  [
                    addon.local ? "Added on this device" : "From Nuvio",
                    `${addon.catalogs.length} catalog${addon.catalogs.length === 1 ? "" : "s"}`,
                    addon.resources.some((r) => r.name === "stream") ? "streams" : null
                  ]
                    .filter(Boolean)
                    .join(" · ")
              )
            ),
            addon.local
              ? h(
                  "button",
                  {
                    class: "icon-btn",
                    "aria-label": `Remove ${addon.name}`,
                    onclick: async () => {
                      setExtraAddonUrls(extraAddonUrls().filter((url) => addons.addonKey(url) !== addon.key));
                      await loadAccount();
                      rerender();
                    }
                  },
                  icon("trash")
                )
              : null
          )
        )
      )
    : h("p", { class: "muted" }, "No addons loaded.");

  const addInput = h("input", { type: "url", placeholder: "https://…/manifest.json", autocapitalize: "off", spellcheck: "false", "aria-label": "Addon manifest link", required: true });
  const addError = h("p", { class: "form-error", role: "alert", hidden: true });
  const addForm = h(
    "form",
    {
      class: "inline-form",
      onsubmit: async (event) => {
        event.preventDefault();
        addError.hidden = true;
        const url = addInput.value.trim();
        const probe = await addons.loadAddon(url);
        if (probe.error) {
          addError.textContent = `Couldn't load that addon: ${probe.error}`;
          addError.hidden = false;
          return;
        }
        setExtraAddonUrls([...extraAddonUrls().filter((u) => addons.addonKey(u) !== probe.key), url]);
        await loadAccount();
        toast(`Added ${probe.name}`);
        rerender();
      }
    },
    addInput,
    h("button", { class: "btn btn-primary", type: "submit" }, icon("plus"), "Add")
  );

  sections.push(
    settingsSection(
      "Addons",
      h("p", { class: "muted small" }, "Addons installed in Nuvio load automatically. You can also add one just for this device."),
      addonList,
      addForm,
      addError
    )
  );

  const serverInput = h("input", { type: "url", placeholder: "https://your-nuvio-server.example", value: custom?.url || "", autocapitalize: "off", spellcheck: "false", "aria-label": "Self-hosted server address" });
  const serverError = h("p", { class: "form-error", role: "alert", hidden: true });
  sections.push(
    settingsSection(
      "Nuvio server",
      h("p", { class: "muted small" }, server ? `Using ${custom ? "your server" : "the official server"}: ${server.url}` : "Not connected."),
      h(
        "form",
        {
          class: "inline-form",
          onsubmit: async (event) => {
            event.preventDefault();
            serverError.hidden = true;
            try {
              await nuvio.useCustomServer(serverInput.value.trim());
              await loadAccount();
              location.hash = "#/login";
            } catch (error) {
              serverError.textContent = error.message;
              serverError.hidden = false;
            }
          }
        },
        serverInput,
        h("button", { class: "btn btn-ghost", type: "submit" }, "Use")
      ),
      serverError,
      custom
        ? h(
            "button",
            {
              class: "btn btn-ghost btn-sm",
              onclick: async () => {
                await nuvio.useCustomServer("");
                await loadAccount();
                location.hash = "#/login";
              }
            },
            "Switch back to the official server"
          )
        : h("p", { class: "muted small" }, "Leave this alone unless you run a self-hosted Nuvio server. Changing it signs you out.")
    )
  );

  sections.push(
    settingsSection(
      "About",
      h("p", { class: "muted small" }, "Shelf is an unofficial web client for Nuvio accounts and Stremio-style addons. It isn't affiliated with Nuvio and hosts no media: everything you see comes from your own addons."),
      h("p", { class: "muted small" }, "Safari plays MP4 and HLS streams. For MKV files, use “Open in…” in the player to hand the stream to VLC or Infuse.")
    )
  );

  return h("div", { class: "view settings" }, topBar({ back: true, title: "Settings" }), ...sections);
}

function settingsSection(title, ...children) {
  return h("section", { class: "settings-section" }, h("h2", {}, title), ...children);
}

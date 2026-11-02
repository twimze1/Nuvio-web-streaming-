# Shelf

An unofficial web client for your Nuvio account, made for Safari on iPhone. Sign in with
your Nuvio email and password and you get your profiles, installed addons, saved library
and Continue Watching. Browse your addons' catalogs and play their streams in Safari.

Shelf is a static site (plain HTML, CSS and JavaScript, no build step), so it runs on
GitHub Pages. It is not affiliated with Nuvio and hosts no media.

## Put it on GitHub Pages

1. On github.com, create a new **public** repository (for example `shelf`).
2. Upload every file in this folder to it (on the repo page: **Add file → Upload files**,
   then select all the files). There are no subfolders, so this works from an iPhone too.
3. In the repo, open **Settings → Pages**. Under **Build and deployment**, choose
   **Deploy from a branch**, branch `main`, folder `/ (root)`, and save.
4. After a minute the site is live at `https://<your-username>.github.io/<repo-name>/`.

## Use it on iPhone

1. Open the site in Safari and sign in with your Nuvio email and password.
2. Tap the Share button, then **Add to Home Screen**. It then opens full screen like an app.

## What plays in Safari

- **Plays:** MP4/MOV (H.264 or HEVC, AAC audio) and HLS (`.m3u8`) streams.
- **Usually doesn't:** MKV/AVI files, DTS or TrueHD audio. In the player, tap **Open in…**
  to hand the stream to VLC, Infuse or Outplayer instead.
- **Never:** torrent results. They are hidden.
- Addons and streams must use `https://`. Safari blocks `http://` links on a secure site.

## How it works

- `nuvio.js` talks to the Nuvio account service. The server address and public key are
  read at runtime from `https://nuvio.tv/config.js`, so no keys live in this repo. A
  self-hosted Nuvio server can be set in Settings.
- `addons.js` speaks the Stremio addon protocol (`manifest`, `catalog`, `meta`,
  `stream`, `subtitles`).
- Watch progress is saved back to your Nuvio profile, so it shows up in the Nuvio apps.
- Your session stays in this browser's local storage. Sign out in Settings to remove it.

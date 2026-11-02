// Small wrapper around localStorage. Storage can be unavailable (private mode,
// blocked site data), so every read has a fallback and every write is optional.
const PREFIX = "shelf.";

export function load(key, fallback = null) {
  try {
    const raw = localStorage.getItem(PREFIX + key);
    return raw == null ? fallback : JSON.parse(raw);
  } catch {
    return fallback;
  }
}

export function save(key, value) {
  try {
    if (value == null) localStorage.removeItem(PREFIX + key);
    else localStorage.setItem(PREFIX + key, JSON.stringify(value));
  } catch {
    // The app keeps working for this visit without persistence.
  }
}

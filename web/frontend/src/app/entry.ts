export type Entry = "technical" | "leader";
const preferenceKey = "batfish-entry-preference";

export function preferredEntryPath() {
  try {
    return localStorage.getItem(preferenceKey) === "leader"
      ? "/leader/overview"
      : "/";
  } catch {
    return "/";
  }
}

export function chooseEntry(entry: Entry) {
  try {
    localStorage.setItem(preferenceKey, entry);
  } catch {
    // The current navigation still works when storage is unavailable.
  }
}

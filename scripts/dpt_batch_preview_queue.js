/*
Run this in the browser console on any Dota2ProTracker page.

It fetches the /heroes index, builds the same hero URL queue used by the batch
userscript, prints a preview of the first 20 heroes, and copies the full queue
JSON to your clipboard when possible.
*/

(async () => {
  const HEROES_URL = "https://dota2protracker.com/heroes";
  const origin = "https://dota2protracker.com";

  const normalizeHeroUrl = (url) => {
    const parsed = new URL(url, location.origin);
    return `${parsed.origin}${parsed.pathname}`;
  };

  const extractHeroUrlsFromLinks = (rootDocument) =>
    [...rootDocument.querySelectorAll('a[href*="/hero/"]')]
      .map((anchor) => normalizeHeroUrl(anchor.href))
      .filter((url) => /^https:\/\/dota2protracker\.com\/hero\/[^/]+$/.test(url));

  const extractHeroUrlsFromButtons = (rootDocument) =>
    [...rootDocument.querySelectorAll('[data-track-view="heroes-hero-grid"] button[title]')]
      .map((button) => String(button.getAttribute("title") || "").trim())
      .filter(Boolean)
      .map((heroName) => `${origin}/hero/${encodeURIComponent(heroName)}`);

  const formatHeroName = (url) => {
    const slug = url.split("/hero/")[1] || "";
    return decodeURIComponent(slug).replace(/_/g, " ");
  };

  let queue = [];
  if (location.pathname === "/heroes") {
    queue = extractHeroUrlsFromLinks(document);
    if (!queue.length) {
      queue = extractHeroUrlsFromButtons(document);
    }
  }

  if (!queue.length) {
    const response = await fetch(HEROES_URL, { credentials: "include" });
    const markup = await response.text();
    const parsed = new DOMParser().parseFromString(markup, "text/html");
    queue = extractHeroUrlsFromLinks(parsed);
    if (!queue.length) {
      queue = extractHeroUrlsFromButtons(parsed);
    }
  }

  const uniqueQueue = [...new Set(queue)];
  const preview = uniqueQueue.slice(0, 20).map((url, index) => ({
    index,
    hero: formatHeroName(url),
    url,
  }));

  console.log(`[dpt-batch] Found ${uniqueQueue.length} hero URLs.`);
  console.table(preview);
  console.log("[dpt-batch] Full queue:", uniqueQueue);

  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(JSON.stringify(uniqueQueue, null, 2));
      console.log("[dpt-batch] Copied full queue JSON to clipboard.");
    } catch (error) {
      console.warn("[dpt-batch] Could not copy queue to clipboard.", error);
    }
  }
})();

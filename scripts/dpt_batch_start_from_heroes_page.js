/*
Run this in the browser console on https://dota2protracker.com/heroes after
installing scripts/dpt_batch_export.user.js in Tampermonkey/Violentmonkey.

It scrapes the currently rendered hero links from the live /heroes page,
stores them as the full batch queue, and then navigates to the first hero so
the userscript can take over the export process.
*/

(() => {
  const STORAGE_KEY = "dpt_batch_export_state_v1";
  const origin = "https://dota2protracker.com";

  const heroNames = [...document.querySelectorAll('[data-track-view="heroes-hero-grid"] button[title]')]
    .map((button) => String(button.getAttribute("title") || "").trim())
    .filter(Boolean);

  const queue = heroNames.map(
    (heroName) => `${origin}/hero/${encodeURIComponent(heroName)}`
  );

  const uniqueQueue = [...new Set(queue)];
  if (!uniqueQueue.length) {
    console.error(
      "[dpt-batch] Could not find any hero buttons on the live /heroes page."
    );
    return;
  }

  const state = {
    active: true,
    running: false,
    mode: "all",
    minRoleMatches: 150,
    index: 0,
    queue: uniqueQueue,
    completed: [],
    startedAt: new Date().toISOString(),
    error: null,
  };

  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  console.log(`[dpt-batch] Seeded ${uniqueQueue.length} hero URLs from /heroes.`, state);
  console.log("[dpt-batch] First 10 hero URLs:", uniqueQueue.slice(0, 10));

  const firstUrl = uniqueQueue[0].startsWith(origin)
    ? uniqueQueue[0]
    : `${origin}/hero/Tidehunter`;
  location.href = firstUrl;
})();

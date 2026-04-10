/*
Run this in the browser console on any Dota2ProTracker hero page after
installing scripts/dpt_batch_export.user.js in Tampermonkey/Violentmonkey.

It seeds the batch-export state and lets the userscript export all visible role
tabs for the current hero only. This is the safest first test.
*/

(() => {
  const STORAGE_KEY = "dpt_batch_export_state_v1";
  const origin = "https://dota2protracker.com";
  const currentUrl = `${location.origin}${location.pathname}`;

  const state = {
    active: true,
    running: false,
    index: 0,
    mode: "single",
    minRoleMatches: 150,
    queue: [currentUrl.startsWith(origin) ? currentUrl : `${origin}/hero/Tidehunter`],
    completed: [],
    startedAt: new Date().toISOString(),
    error: null,
  };

  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  console.log("[dpt-batch] Batch state initialized.", state);
  console.log(
    `[dpt-batch] Start page: ${currentUrl.startsWith(origin) ? currentUrl : `${origin}/hero/Tidehunter`}`
  );
  console.log(
    "[dpt-batch] The userscript will export all visible role tabs for this hero after the page reloads."
  );
  location.reload();
})();

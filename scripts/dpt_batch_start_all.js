/*
Run this in the browser console on any Dota2ProTracker hero page after
installing scripts/dpt_batch_export.user.js in Tampermonkey/Violentmonkey.

It seeds the batch-export state for the full hero crawl. The userscript will
fetch the /heroes list, navigate hero-by-hero, click through each visible role
tab, and download one HTML export per hero-role view.
*/

(() => {
  const STORAGE_KEY = "dpt_batch_export_state_v1";

  const state = {
    active: true,
    running: false,
    mode: "all",
    minRoleMatches: 150,
    index: 0,
    queue: [],
    completed: [],
    startedAt: new Date().toISOString(),
    error: null,
  };

  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  console.log("[dpt-batch] Full batch state initialized.", state);
  console.log("[dpt-batch] The userscript will build the full /heroes queue after reload.");
  location.reload();
})();

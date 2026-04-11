/*
Run this in the browser console on any Dota2ProTracker hero page after
installing scripts/dpt_batch_export.user.js in Tampermonkey/Violentmonkey.

It resumes the existing all-heroes batch state after an error or interruption.
If no prior state exists, it does nothing.
*/

(() => {
  const STORAGE_KEY = "dpt_batch_export_state_v1";
  const raw = localStorage.getItem(STORAGE_KEY);

  if (!raw) {
    console.log("[dpt-batch] No existing batch state found to resume.");
    return;
  }

  const state = JSON.parse(raw);
  state.active = true;
  state.running = false;
  state.error = null;

  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  console.log("[dpt-batch] Resuming batch state.", state);
  location.reload();
})();

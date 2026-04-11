// ==UserScript==
// @name         D2PT Batch Hero Export
// @namespace    https://dota2protracker.com/
// @version      0.1
// @description  Export Dota2ProTracker hero matchup HTML for many heroes in sequence.
// @match        https://dota2protracker.com/hero/*
// @grant        none
// ==/UserScript==

(function () {
  "use strict";

  const STORAGE_KEY = "dpt_batch_export_state_v1";
  const HEROES_URL = "https://dota2protracker.com/heroes";
  const STATUS_ID = "dpt-batch-status";
  const DEFAULT_MIN_ROLE_MATCHES = 150;
  const WAIT_TIMEOUT_MS = 30000;
  const POLL_MS = 500;
  const NEXT_PAGE_DELAY_MS = 2500;

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();
  window.__dptBatchUserscriptLoaded = true;

  const roleNames = ["Carry", "Mid", "Offlane", "Support", "Hard Support"];
  const roleNamesBySpecificity = [...roleNames].sort(
    (left, right) => right.length - left.length
  );

  const loadState = () => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (error) {
      console.error("[dpt-batch] Failed to read state", error);
      return null;
    }
  };

  const saveState = (state) => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  };

  const ensureStatusNode = () => {
    let node = document.getElementById(STATUS_ID);
    if (node) return node;

    node = document.createElement("div");
    node.id = STATUS_ID;
    node.style.position = "fixed";
    node.style.right = "12px";
    node.style.bottom = "12px";
    node.style.zIndex = "2147483647";
    node.style.maxWidth = "360px";
    node.style.padding = "10px 12px";
    node.style.borderRadius = "10px";
    node.style.background = "rgba(8, 20, 28, 0.92)";
    node.style.color = "#fff";
    node.style.font = "12px/1.4 monospace";
    node.style.boxShadow = "0 8px 24px rgba(0, 0, 0, 0.35)";
    node.style.border = "1px solid rgba(255,255,255,0.12)";
    document.body.appendChild(node);
    return node;
  };

  const setStatus = (message, tone = "info") => {
    const node = ensureStatusNode();
    const colors = {
      info: "#7dd3fc",
      success: "#86efac",
      warn: "#fde68a",
      error: "#fca5a5",
    };
    node.style.borderColor = colors[tone] || colors.info;
    node.innerHTML = `<div style="color:${colors[tone] || colors.info};font-weight:700;margin-bottom:4px;">DPT Batch</div><div>${message}</div>`;
  };

  const stopState = (state, reason) => {
    state.active = false;
    state.error = reason;
    saveState(state);
    setStatus(reason, "error");
    console.error("[dpt-batch]", reason);
  };

  const isVisible = (element) => {
    if (!element) return false;
    const rect = element.getBoundingClientRect();
    const style = window.getComputedStyle(element);
    return rect.width > 0 && rect.height > 0 && style.display !== "none" && style.visibility !== "hidden";
  };

  const detectHeroName = () => {
    const heading = document.querySelector('[data-track-view="hero-role-stats"] h2');
    if (heading) {
      const spans = [...heading.querySelectorAll("span")]
        .map((node) => clean(node.textContent))
        .filter(Boolean);
      if (spans.length) return spans[0];
    }

    const heroTitle = document.querySelector('div.text-\\[32px\\]');
    if (heroTitle) return clean(heroTitle.textContent);

    const match = window.location.pathname.match(/\/hero\/([^/?#]+)/);
    return match ? decodeURIComponent(match[1]) : "unknown_hero";
  };

  const detectRoleName = () => {
    const heading = document.querySelector('[data-track-view="hero-role-stats"] h2');
    const text = clean(heading ? heading.innerText : "");
    return roleNamesBySpecificity.find((role) => text.endsWith(role)) || "Unknown";
  };

  const findMatchupsTab = () => {
    const candidates = [...document.querySelectorAll("button, a, div")];
    return candidates.find((element) => clean(element.textContent) === "Matchups & Synergies" && isVisible(element));
  };

  const findRoleButtons = () => {
    const seen = new Set();
    return [...document.querySelectorAll("button")]
      .filter((button) => isVisible(button))
      .map((button) => {
        const roleImage = button.querySelector("img[alt]");
        const roleName = roleImage ? clean(roleImage.getAttribute("alt")) : "";
        if (!roleNames.includes(roleName)) return null;

        const text = clean(button.innerText);
        const numbers = [...text.matchAll(/\b\d[\d,]*\b/g)].map((match) =>
          Number.parseInt(match[0].replace(/,/g, ""), 10)
        );
        const matchCount = numbers.length ? numbers[0] : null;
        const top = button.getBoundingClientRect().top;
        return {
          button,
          roleName,
          matchCount,
          top,
          active:
            button.className.includes("bg-white/20") ||
            button.className.includes("border-white/20") ||
            /Most Played/i.test(text),
        };
      })
      .filter(Boolean)
      .sort((left, right) => left.top - right.top)
      .filter((entry) => {
        if (seen.has(entry.roleName)) return false;
        seen.add(entry.roleName);
        return true;
      })
      .sort(
        (left, right) =>
          roleNames.indexOf(left.roleName) - roleNames.indexOf(right.roleName)
      );
  };

  const findMatchupTables = () =>
    [...document.querySelectorAll('[data-track-view="hero-matchups"] .matchup-table')];

  const countRows = (titlePrefix) => {
    const table = findMatchupTables().find((element) => {
      const title = clean(element.querySelector(":scope > div")?.textContent);
      return title.startsWith(titlePrefix);
    });
    return table ? table.querySelectorAll(".tbody > div").length : 0;
  };

  const waitForMatchupData = async () => {
    const startedAt = Date.now();
    while (Date.now() - startedAt < WAIT_TIMEOUT_MS) {
      const matchupRows = countRows("Matchups");
      const synergyRows = countRows("Synergies");
      if (matchupRows > 0 && synergyRows > 0) {
        return { matchupRows, synergyRows };
      }
      await sleep(POLL_MS);
    }
    throw new Error("Timed out waiting for matchup and synergy rows to load.");
  };

  const waitForRoleView = async (roleName, previousSignature = null) => {
    const startedAt = Date.now();
    while (Date.now() - startedAt < WAIT_TIMEOUT_MS) {
      const currentRole = detectRoleName();
      const matchupRows = countRows("Matchups");
      const synergyRows = countRows("Synergies");
      const noData = /not enough data/i.test(
        clean(document.querySelector('[data-track-view="hero-matchups"]')?.innerText)
      );
      const signature = `${currentRole}|${matchupRows}|${synergyRows}|${noData}`;

      if (
        currentRole === roleName &&
        signature !== previousSignature &&
        (matchupRows > 0 || synergyRows > 0 || noData)
      ) {
        await sleep(1200);
        return { matchupRows, synergyRows, noData, signature };
      }

      await sleep(POLL_MS);
    }
    throw new Error(`Timed out waiting for the ${roleName} role view to load.`);
  };

  const downloadText = (filename, text) => {
    const blob = new Blob([text], { type: "text/html;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  const normalizeHeroUrl = (url) => {
    const parsed = new URL(url, window.location.origin);
    return `${parsed.origin}${parsed.pathname}`;
  };

  const fetchHeroQueue = async () => {
    const response = await fetch(HEROES_URL, { credentials: "include" });
    const markup = await response.text();
    const parsed = new DOMParser().parseFromString(markup, "text/html");

    const urls = [...parsed.querySelectorAll('a[href^="/hero/"]')]
      .map((anchor) => normalizeHeroUrl(anchor.href))
      .filter((url) => /^https:\/\/dota2protracker\.com\/hero\/[^/]+$/.test(url));

    return [...new Set(urls)];
  };

  const getCurrentHeroUrl = () => normalizeHeroUrl(window.location.href);

  const exportCurrentPage = async (state) => {
    setStatus("Opening Matchups & Synergies and waiting for rows...", "info");
    const tab = findMatchupsTab();
    if (tab) {
      tab.click();
      await sleep(1000);
    }

    const counts = await waitForMatchupData();
    const heroName = detectHeroName();
    const roleName = detectRoleName();
    const slugHero = heroName.replace(/[^\w.-]+/g, "_");
    const slugRole = roleName.replace(/[^\w.-]+/g, "_");
    const filename = `dpt_${slugHero}_${slugRole}.html`;

    downloadText(filename, document.body.outerHTML);

    state.completed = state.completed || [];
    state.completed.push({
      hero: heroName,
      role: roleName,
      url: normalizeHeroUrl(window.location.href),
      filename,
      matchupRows: counts.matchupRows,
      synergyRows: counts.synergyRows,
      noData: false,
      exportedAt: new Date().toISOString(),
    });
    saveState(state);

    setStatus(
      `Exported ${heroName} ${roleName}<br>matchups=${counts.matchupRows}, synergies=${counts.synergyRows}`,
      "success"
    );
    console.log("[dpt-batch] Exported", {
      hero: heroName,
      role: roleName,
      filename,
      matchupRows: counts.matchupRows,
      synergyRows: counts.synergyRows,
    });
  };

  const exportAllRolesForCurrentHero = async (state) => {
    const tab = findMatchupsTab();
    if (tab) {
      tab.click();
      await sleep(1000);
    }

    const requestedMinRoleMatches = Number(state.minRoleMatches);
    const minRoleMatches = Number.isFinite(requestedMinRoleMatches)
      ? requestedMinRoleMatches
      : DEFAULT_MIN_ROLE_MATCHES;
    const visibleRoleButtons = findRoleButtons();
    const roleButtons = visibleRoleButtons.filter(
      (entry) => (entry.matchCount ?? 0) >= minRoleMatches
    );
    const skippedRoles = visibleRoleButtons.filter(
      (entry) => (entry.matchCount ?? 0) < minRoleMatches
    );
    const heroName = detectHeroName();
    if (!roleButtons.length) {
      const skipRecord = {
        hero: heroName,
        url: normalizeHeroUrl(window.location.href),
        reason: `No roles met the ${minRoleMatches} match threshold.`,
        visibleRoles: skippedRoles.map((entry) => ({
          role: entry.roleName,
          matchCount: entry.matchCount,
        })),
        skippedAt: new Date().toISOString(),
      };
      state.skipped = state.skipped || [];
      state.skipped.push(skipRecord);
      saveState(state);
      setStatus(
        `Skipped ${heroName}<br>no roles met threshold=${minRoleMatches}`,
        "warn"
      );
      console.log("[dpt-batch] Skipped hero with no eligible roles", skipRecord);
      await sleep(1200);
      return;
    }

    if (skippedRoles.length) {
      console.log(
        "[dpt-batch] Skipping low-sample roles",
        skippedRoles.map((entry) => ({
          role: entry.roleName,
          matchCount: entry.matchCount,
        }))
      );
    }

    for (const roleEntry of roleButtons) {
      const currentRole = detectRoleName();
      const currentSignature = `${currentRole}|${countRows("Matchups")}|${countRows("Synergies")}`;
      const alreadyDone = (state.completed || []).some(
        (entry) =>
          entry.url === normalizeHeroUrl(window.location.href) &&
          entry.hero === heroName &&
          entry.role === roleEntry.roleName
      );

      if (!alreadyDone) {
        if (currentRole !== roleEntry.roleName) {
          setStatus(
            `Switching ${heroName} to ${roleEntry.roleName}<br>matches=${roleEntry.matchCount ?? "?"}<br>threshold=${minRoleMatches}`,
            "info"
          );
          roleEntry.button.click();
          await waitForRoleView(roleEntry.roleName, currentSignature);
        } else {
          await sleep(500);
        }

        const counts = await waitForRoleView(roleEntry.roleName, null).catch(() => ({
          matchupRows: countRows("Matchups"),
          synergyRows: countRows("Synergies"),
          noData: /not enough data/i.test(
            clean(document.querySelector('[data-track-view="hero-matchups"]')?.innerText)
          ),
        }));

        const roleName = detectRoleName();
        const slugHero = heroName.replace(/[^\w.-]+/g, "_");
        const slugRole = roleName.replace(/[^\w.-]+/g, "_");
        const filename = `dpt_${slugHero}_${slugRole}.html`;
        downloadText(filename, document.body.outerHTML);

        state.completed = state.completed || [];
        state.completed.push({
          hero: heroName,
          role: roleName,
          url: normalizeHeroUrl(window.location.href),
          filename,
          matchupRows: counts.matchupRows,
          synergyRows: counts.synergyRows,
          noData: Boolean(counts.noData),
          exportedAt: new Date().toISOString(),
        });
        saveState(state);

        setStatus(
          `Exported ${heroName} ${roleName}<br>matches=${roleEntry.matchCount ?? "?"}<br>matchups=${counts.matchupRows}, synergies=${counts.synergyRows}${counts.noData ? "<br>not enough data" : ""}`,
          counts.noData ? "warn" : "success"
        );
        console.log("[dpt-batch] Exported role", {
          hero: heroName,
          role: roleName,
          filename,
          matchupRows: counts.matchupRows,
          synergyRows: counts.synergyRows,
          noData: Boolean(counts.noData),
        });

        await sleep(1200);
      }
    }
  };

  const navigateToCurrentTarget = (state) => {
    const targetUrl = state.queue[state.index];
    if (!targetUrl) {
      state.active = false;
      saveState(state);
      setStatus("Completed all heroes.", "success");
      console.log("[dpt-batch] Completed all heroes.");
      return;
    }

    const currentUrl = normalizeHeroUrl(window.location.href);
    if (currentUrl !== targetUrl) {
      setStatus(`Navigating to ${targetUrl}`, "info");
      console.log("[dpt-batch] Navigating to", targetUrl);
      window.location.href = targetUrl;
    }
  };

  const run = async () => {
    const state = loadState();
    if (!state || !state.active) return;

    if (state.running) return;
    state.running = true;
    saveState(state);

    try {
      if (!Array.isArray(state.queue) || state.queue.length === 0) {
        if (state.mode === "all") {
          setStatus(`Building hero queue from ${HEROES_URL}`, "info");
          console.log("[dpt-batch] Building hero queue from", HEROES_URL);
          state.queue = await fetchHeroQueue();
        } else {
          state.queue = [getCurrentHeroUrl()];
        }
        state.index = state.index || 0;
        saveState(state);
      }

      const targetUrl = state.queue[state.index];
      if (!targetUrl) {
        state.active = false;
        state.running = false;
        saveState(state);
        setStatus("No remaining heroes.", "warn");
        console.log("[dpt-batch] No remaining heroes.");
        return;
      }

      setStatus(
        `Mode=${state.mode || "single"}<br>Min role matches=${state.minRoleMatches ?? DEFAULT_MIN_ROLE_MATCHES}<br>Progress=${state.index + 1}/${state.queue.length}<br>Target=${targetUrl}`,
        "info"
      );

      const currentUrl = normalizeHeroUrl(window.location.href);
      if (currentUrl !== targetUrl) {
        state.running = false;
        saveState(state);
        navigateToCurrentTarget(state);
        return;
      }

      if (state.mode === "single" || state.mode === "all") {
        await exportAllRolesForCurrentHero(state);
      } else {
        const alreadyDone = (state.completed || []).some((entry) => entry.url === currentUrl);
        if (!alreadyDone) {
          await exportCurrentPage(state);
        } else {
          console.log("[dpt-batch] Already exported", currentUrl);
        }
      }

      state.index += 1;
      state.running = false;
      saveState(state);

      if (state.index >= state.queue.length) {
        state.active = false;
        saveState(state);
        setStatus("Finished queue.", "success");
        console.log("[dpt-batch] Finished queue.");
        return;
      }

      const nextUrl = state.queue[state.index];
      setStatus(`Next hero in ${NEXT_PAGE_DELAY_MS}ms<br>${nextUrl}`, "info");
      console.log("[dpt-batch] Next hero in", NEXT_PAGE_DELAY_MS, "ms:", nextUrl);
      setTimeout(() => {
        window.location.href = nextUrl;
      }, NEXT_PAGE_DELAY_MS);
    } catch (error) {
      state.running = false;
      stopState(state, String(error));
    }
  };

  window.addEventListener("load", () => {
    setTimeout(() => {
      run().catch((error) => console.error("[dpt-batch] Unhandled error", error));
    }, 1000);
  });
})();

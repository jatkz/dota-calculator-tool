/*
Run this in the browser console on a Dota2ProTracker hero page.

It clicks the "Matchups & Synergies" tab if available, waits for the matchup
rows to exist, then downloads the current page body HTML as a file that can be
parsed by scripts/parse_dpt_matchups.py.
*/

(async () => {
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const clean = (value) => String(value || "").replace(/\s+/g, " ").trim();

  const isVisible = (element) => {
    if (!element) return false;
    const rect = element.getBoundingClientRect();
    const style = window.getComputedStyle(element);
    return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none";
  };

  const roleNames = ["Carry", "Mid", "Offlane", "Support", "Hard Support"];

  const detectHeroName = () => {
    const heading = document.querySelector('[data-track-view="hero-role-stats"] h2');
    if (heading) {
      const spans = [...heading.querySelectorAll("span")].map((node) => clean(node.textContent)).filter(Boolean);
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
    return roleNames.find((role) => text.endsWith(role)) || "Unknown";
  };

  const findMatchupsTab = () => {
    const candidates = [...document.querySelectorAll("button, a, div")];
    return candidates.find((element) => {
      const text = clean(element.textContent);
      return text === "Matchups & Synergies" && isVisible(element);
    });
  };

  const countRows = (titlePrefix) => {
    const tables = [...document.querySelectorAll('[data-track-view="hero-matchups"] .matchup-table')];
    const table = tables.find((element) => {
      const title = clean(element.querySelector(":scope > div")?.textContent);
      return title.startsWith(titlePrefix);
    });
    if (!table) return 0;
    return table.querySelectorAll(".tbody > div").length;
  };

  const waitForMatchupData = async (timeoutMs = 30000) => {
    const startedAt = Date.now();
    while (Date.now() - startedAt < timeoutMs) {
      const container = document.querySelector('[data-track-view="hero-matchups"]');
      const matchupRows = countRows("Matchups");
      const synergyRows = countRows("Synergies");
      if (container && matchupRows > 0 && synergyRows > 0) {
        return { matchupRows, synergyRows };
      }
      await sleep(500);
    }
    throw new Error("Timed out waiting for matchup and synergy rows to load.");
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

  const heroName = detectHeroName();
  const roleName = detectRoleName();
  const slugHero = heroName.replace(/[^\w.-]+/g, "_");
  const slugRole = roleName.replace(/[^\w.-]+/g, "_");
  const filename = `dpt_${slugHero}_${slugRole}.html`;

  const tab = findMatchupsTab();
  if (tab) {
    tab.click();
    await sleep(1000);
  }

  const counts = await waitForMatchupData();
  downloadText(filename, document.body.outerHTML);

  console.log("Downloaded D2PT HTML", {
    hero: heroName,
    role: roleName,
    filename,
    matchupRows: counts.matchupRows,
    synergyRows: counts.synergyRows,
    url: window.location.href,
  });
})();

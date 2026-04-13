# D2PT Batch Workflow

This is the recommended workflow for exporting matchup/synergy HTML from
Dota2ProTracker in Edge and importing it into this repo.

## 1. Start the full export run

Make sure the installed userscript in Edge matches:

- [scripts/dpt_batch_export.user.js](/home/jaredt/projects/dota-calculator-tool/scripts/dpt_batch_export.user.js)

Then:

1. Open any hero page on `https://dota2protracker.com/hero/...`
2. In DevTools Console, clear any old state:

```js
localStorage.removeItem("dpt_batch_export_state_v1")
```

3. Paste the contents of:

- [scripts/dpt_batch_start_all.js](/home/jaredt/projects/dota-calculator-tool/scripts/dpt_batch_start_all.js)

4. When Edge asks about multiple downloads, click `Allow`

The userscript will:

- fetch the hero list
- navigate hero by hero
- export all visible role tabs with at least `150` matches
- skip lower-sample roles

## 2. Resume after an interruption

If the run pauses or errors, open a hero page and paste:

- [scripts/dpt_batch_resume.js](/home/jaredt/projects/dota-calculator-tool/scripts/dpt_batch_resume.js)

This resumes from saved progress instead of starting over.

## 3. Import the downloaded HTML files

From the repo root in WSL:

```bash
.venv/bin/python scripts/import_dpt_exports.py
```

That command will auto-detect likely download folders and prefer:

- `/mnt/c/Users/jtoku/Downloads/dpt-batch`

If you want to point at a specific folder explicitly:

```bash
.venv/bin/python scripts/import_dpt_exports.py /mnt/c/Users/jtoku/Downloads/dpt-batch
```

Preview only:

```bash
.venv/bin/python scripts/import_dpt_exports.py --dry-run /mnt/c/Users/jtoku/Downloads/dpt-batch
```

## 4. Output files

Imported data is merged into:

- [dpt_matchups_synergies.json](/home/jaredt/projects/dota-calculator-tool/dpt_matchups_synergies.json)

Import summaries are written to:

- [outputs/dpt_import_summary.json](/home/jaredt/projects/dota-calculator-tool/outputs/dpt_import_summary.json)

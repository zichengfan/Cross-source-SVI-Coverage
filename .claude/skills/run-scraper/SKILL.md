---
name: run-scraper
description: Run a provider coverage scrape detached in a tmux session so it survives disconnects. Use for any pilot or full-extent coverage run, which take minutes to many hours.
---

# run-scraper

Coverage scrapes are long-running (a city pilot is minutes; a full-country
extent is many hours). **Always run them detached in a `tmux` session** so the
run survives an SSH disconnect or the agent session ending.

## 1. Pick the command

All providers use `fetch-provider`.

Always **dry-run first** to size the job:

```bash
.venv/bin/python -m coverage_acquisition.cli fetch-provider \
  --provider <key> --bbox <min_lon> <min_lat> <max_lon> <max_lat> \
  --output-root data/raw --dry-run
```

## 2. Launch in tmux

One named session per provider run. `tee` the output to a log so progress is
inspectable (the runner prints its manifest JSON on completion):

```bash
tmux new-session -d -s scrape-<key> \
  "cd /data2/shared/Cross-source-SVI-Coverage && \
   MPLCONFIGDIR=/tmp/mpl .venv/bin/python -m coverage_acquisition.cli fetch-provider \
     --provider <key> --bbox <min_lon> <min_lat> <max_lon> <max_lat> \
     --output-root data/raw --run-label <label> \
     2>&1 | tee data/raw/<key>_<label>.log"
```

Use provider defaults unless the provider subplan says otherwise. Do not run
many large scrapes against the same host at once.

## 3. Monitor

```bash
tmux ls                                  # list running scrapes
tmux capture-pane -t scrape-<key> -p | tail -20
tail -f data/raw/<key>_<label>.log
```

The session **ends automatically** when the scrape finishes; the log file and
the output directory persist. Done = session gone + `manifest.json` written.

## 4. Outputs

`data/raw/<key>_coverage/<run_label>/` contains the stored source responses and
`manifest.json`.

## 5. After the scrape

Rasterize the result to the z14 binary-presence COG and register it in the STAC
catalog — see the `rasterize-coverage` skill. Keep the point/vector data in
`data/intermediate/`; the raster is the published product.

## Sequencing

Run a **pilot** (a small city bbox) end-to-end first and confirm the COG looks
right, *then* launch the full-extent run. Full-extent runs are the long ones
that most need tmux.

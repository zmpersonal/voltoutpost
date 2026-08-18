# VoltOutpost.com — U.S. Home Energy Resilience Index

Static GitHub Pages site with a scheduled data refresh.

## What the index uses
- NLR PVWatts v8 for standardized 10 kW solar production and monthly seasonality.
- U.S. EIA monthly residential electricity prices by state.
- OpenFEMA Disaster Declarations Summaries as a historical county-level exposure proxy.

## First deployment
1. Upload **all files**, including the hidden `.github` folder, to the repository root.
2. GitHub → Settings → Pages → Source: **GitHub Actions**.
3. Set the custom domain to `voltoutpost.com`.
4. Add repository secrets under Settings → Secrets and variables → Actions:
   - `NLR_API_KEY` — free developer key for PVWatts. The updater falls back to `DEMO_KEY`, but a personal key is strongly recommended for the full city batch.
   - `EIA_API_KEY` — free EIA API key. If omitted, the updater retains the bundled starter electricity-rate values.
5. Go to Actions → **Update resilience index and deploy** → Run workflow.

OpenFEMA requires no API key. If any upstream request fails, the updater preserves the previous/starter value rather than blanking the site.

## Schedule
The index refresh workflow runs every Monday. PVWatts itself does not necessarily change weekly; the schedule also picks up newly available EIA and FEMA data while keeping the publishing workflow simple.

## Backlink / attribution strategy
The downloadable CSV/JSON are intended to be citable. Publishers may cite the “VoltOutpost U.S. Home Energy Resilience Index” with a link to the dataset page.

## InHouse Wellness link
There is exactly one `inhousewellness.com` link in the checked-in site, and it appears only on the homepage. The generator/updater does not add it to city or state pages.

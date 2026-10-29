# PricePal Web

A separate web application for live product lookup and price history across ten retailers. Retailer catalogues vary: some specialize in phones and computers, while others focus on appliances, furniture, home and DIY products. The original Python desktop project is not modified.

## Run locally on Windows

Open PowerShell in this folder:

```powershell
py -3.9 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Then open <http://127.0.0.1:5000>. Stop the server with Ctrl+C. The SQLite database is created as `pricepal-web.sqlite3` beside `app.py`.

## Implemented now

- Live concurrent search adapters for Shpresa, 3V Fejzo, Neptun, Globe, Aza, Megatek, Gjirafa50, Ozone, German Computers, and GoTech.
- Site-specific result parsing: Globe's public product suggestion API; Aza's public category listings; Megatek's visible catalogue; Gjirafa50's result page; Ozone's PrestaShop search page; German Computers' shop results; and GoTech's WooCommerce search. Search terms are not restricted to phones: each store returns matching products from the categories it actually carries.
- Product accessory filtering for device searches, typo tolerance for common brand names, independent store failure handling, result sorting, and links to the actual retailer pages.
- SQLite product, retailer, offer, and timestamped price-observation tables. Repeated identical checks are coalesced for one hour; actual price and availability changes are recorded immediately.
- One-time import of the desktop project's copied `PriceHistory.csv` into the new database; imported observations keep their historical date and are labeled `Desktop CSV`.
- Side-by-side comparison of up to four selected listings, saved point-in-time snapshots, history chart and observation table, CSV history import/export, browser-session wishlist, target/drop/low/stock/change alert rules, alert state controls, and in-app notifications.
- Responsive dark interface with accessible labels, focus styling, and reduced-motion support.

The CSV importer accepts the desktop history fields (`Site` or `Store`, `Product Name`, `Price (Lekë)` or `Price`, `URL`, `Date`, `Time`). Later manual imports are labeled as CSV import in the observation source. The bundled baseline is a copy; the original desktop `PriceHistory.csv` is never changed.

## Data and deployment boundaries

- Retailer requests are real network requests. Search may fail or return incomplete results if a retailer is down, changes its endpoint, blocks automated traffic, or omits a price. Aza and Megatek search their publicly accessible catalogues/category listings rather than restricted search URLs, so coverage there depends on which matching products their current catalogue pages expose. A successful result is an observed listing, not a guarantee that checkout price, stock, shipping, or warranty is current. Verify at the retailer.
- A browser session is used for guest wishlist and alert ownership. There is no login/account system yet; this is not suitable for private multi-user data as-is.
- Alerts are evaluated when a fresh matching observation is collected by a search. No scheduled worker is configured, so the app does not monitor prices while idle. E-mail delivery and browser push are not configured.
- The admin/import interface is limited to a user-selected CSV import. There is no protected product administration, job dashboard, or approval workflow yet.
- SQLite requires persistent writable storage and is suited to local/single-instance use. For a public multi-instance deployment, use PostgreSQL, authenticated accounts, CSRF protections, rate limiting, migrations, and a scheduled worker. Do not deploy this Flask development server directly to production.
- Retailer collection should be reviewed against each retailer's current terms and applicable rules before public deployment. Add feeds or written permission where required.

## Production-style local server

After installing requirements, run Waitress instead of Flask's development server:

```powershell
$env:PRICEPAL_SECRET_KEY = (python -c "import secrets; print(secrets.token_hex(32))")
python -m waitress --listen=127.0.0.1:5000 app:app
```

For local use, a signing key is generated once in the ignored `.secret_key` file so guest lists survive app restarts. For a public deployment, set a stable `PRICEPAL_SECRET_KEY` in the hosting environment and set `PRICEPAL_DB` to a persistent disk path. This starter is not yet a production-ready public multi-user service; see the deployment boundaries above.

## Public API deployment (Render starter)

The KeliXel site is static, so it cannot execute this Flask API itself. `render.yaml` describes a separate Render web service with Gunicorn, a `/health` check, and a persistent disk for SQLite. The persistent disk requires a paid Render web-service plan; without persistent storage, saved history and alerts can disappear when the service restarts. Review current Render pricing before creating the service.

1. Push this `PricePalWeb` folder to a GitHub repository. Keep `.secret_key`, `.env`, and SQLite files out of Git; `.gitignore` already excludes them.
2. In Render, create a Blueprint from that repository and review the service plan and disk shown from `render.yaml` before confirming creation.
3. Wait for the service to deploy, then open its `/health` URL. It should return JSON with `"ok": true`.
4. Add a custom domain such as `api.kelixel.com` in Render and create the DNS record Render specifies in Cloudflare. Wait for HTTPS to become active.
5. Edit the website's `PricePal/config.js` and set `window.PRICEPAL_API_BASE` to `"https://api.kelixel.com"`. Upload the updated website files to the Cloudflare site.
6. Confirm `PRICEPAL_ALLOWED_ORIGINS` includes both `https://kelixel.com` and `https://www.kelixel.com`. These are set in the Blueprint. Keep `PRICEPAL_SECRET_KEY` generated by Render and do not publish it.

The web frontend sends session cookies to the API and the API allows credentialed requests only from the configured KeliXel origins. The current deployment is still a single-instance SQLite starter; before scaling it to multiple instances or adding private user accounts, migrate to PostgreSQL and add authentication, CSRF protection, and rate limits. Review each retailer's current terms before public scraping.

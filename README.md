# PricePal — Albanian Store Price Finder

PricePal is a Python application for checking product prices at three Albanian online stores: Shpresa.al, 3vFejzo.al, and Neptun.al. It provides a Tkinter desktop interface and a command-line mode, lets you compare current results, and can keep a local history of prices you choose to save.

## Features

- Search all three stores in one run, or select a single store in the desktop app.
- Select the exact product when a store returns multiple matching listings.
- Filter common accessories out of device searches so phone or computer searches focus on the product itself.
- Compare the cheapest and most expensive prices returned for a query, with links to the store pages.
- Open a result's product page from the desktop results table.
- Save results on demand and review saved prices over time.
- Plot price history by store and show each store's latest saved price.
- Match common product names despite small spelling variations and parse Albanian Lek price formats.

## Stores and search implementation

- **Shpresa.al** — queries the public WooCommerce Store API and reads product prices and permalinks from its response.
- **3vFejzo.al** — checks structured product data and page content using Requests and BeautifulSoup.
- **Neptun.al** — uses the store's product search endpoint and prefers a discounted price when one is available.

Store websites and their endpoints can change. A search may return no result or fail if a store changes its response format, blocks requests, or has a temporary outage. Use the product link to verify the current price and stock before buying.

## Price history

Results are saved only after you choose **Save to history** in the desktop app or answer **yes** to the CLI save prompt. Records are appended to `PriceHistory.csv` with these columns:

- Store
- Product name
- Price in Lekë
- Product URL
- Date
- Time

Keep this CSV to preserve your own history. The charts are based on the records in this file; PricePal does not run scheduled background checks.

## Requirements

- Python 3.9 or newer
- Internet access for live store searches
- Tkinter (normally included with the Windows Python installer)

Install the Python packages from PowerShell in the project folder:

```powershell
python -m pip install requests beautifulsoup4 pandas matplotlib seaborn
```

## Run

Launch the desktop GUI:

```powershell
python main.py
```

Launch the command-line interface:

```powershell
python main.py --cli
```

## Desktop workflow

1. Enter a product name.
2. Choose **Compare all** or **One store**. For one store, select it from the store list.
3. If the store finds several matching products, choose the exact listing you want.
4. Review prices and product links. Double-click a row to open its store page.
5. Choose **Save to history** if you want those results recorded.
6. Open **Price history** to review past observations and charts.

## Command-line menu

- **Search products** — search one selected store and optionally save the result.
- **Price Comparison** — query all stores and report the lowest and highest returned prices.
- **Price History** — choose a saved product and display its history chart.

## Project files

- `main.py` — search orchestration, price comparison, CSV storage, charting, and CLI entry point; launches the GUI by default.
- `gui.py` — Tkinter desktop interface, product selection dialog, results table, and history charts.
- `shpresa.py`, `fejzo.py`, `neptun.py` — store-specific search and price parsing.
- `scraper_utils.py` — query normalization, product matching, accessory filtering, product selection, and price parsing.
- `PriceHistory.csv` — local saved price observations.

The compiled `PricePal.exe` is excluded from this repository. Run the source with the steps above, or distribute a built executable separately if needed.

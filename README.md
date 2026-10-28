# PricePal

PricePal is a Python desktop app for finding and comparing product prices from Albanian online stores. It can also save price observations locally and chart the price history.

## Features

- Search products from Shpresa.al, 3vFejzo.al, and Neptun.al.
- Choose a matching product when a store returns multiple results; accessory results are filtered from ordinary device searches.
- Compare the lowest and highest prices returned by the selected stores.
- Save store, product, price, URL, date, and time to `PriceHistory.csv`.
- View saved price history and recent prices by store in the desktop interface.
- Run either the desktop GUI or the command-line interface.

## Requirements

- Python 3.9 or later
- Internet access for live store searches

Install the Python packages from PowerShell in the project folder:

```powershell
python -m pip install requests beautifulsoup4 pandas matplotlib seaborn
```

Tkinter is included with most standard Windows Python installations. If Python reports that Tkinter is missing, install a Python distribution that includes the Tcl/Tk feature.

## Run PricePal

Start the desktop interface:

```powershell
python main.py
```

Start the command-line interface:

```powershell
python main.py --cli
```

## Project files

- `main.py` — search orchestration, price comparison, CSV history, charts, and CLI entry point.
- `gui.py` — Tkinter desktop interface.
- `shpresa.py`, `fejzo.py`, `neptun.py` — store-specific search and price extraction.
- `scraper_utils.py` — shared product matching, accessory filtering, and price parsing.
- `PriceHistory.csv` — local saved price observations.

## Notes

Prices and product availability can change. Store websites may also change their pages or endpoints, which can require scraper updates. PricePal reports the prices returned by each store at search time; verify the final price and availability on the linked store page.

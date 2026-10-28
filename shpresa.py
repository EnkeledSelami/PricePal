import requests

from scraper_utils import (
    canonicalize_search_query, choose_product, parse_price, product_name_matches,
)


STORE_API = "https://shpresa.al/wp-json/wc/store/v1/products"
TIMEOUT_SECONDS = 12


def search_shpresa(product_name, product_selector=None):
    # The public WooCommerce Store API already returns matching product names
    # and prices, so there is no need to load a browser for this search.
    try:
        query = canonicalize_search_query(product_name)
        response = requests.get(
            STORE_API,
            params={
                "search": query,
                "per_page": 100,
                "_fields": "name,permalink,type,prices",
            },
            headers={"User-Agent": "Mozilla/5.0 (compatible; PricePal/1.0)"},
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        records = response.json()
        matches = []
        for record in records:
            title = (record.get("name") or "").strip()
            url = record.get("permalink")
            if title and url and product_name_matches(query, title):
                matches.append((title, url, record))

        selected = choose_product(
            [(title, url) for title, url, _ in matches], "Shpresa", product_name,
            selector=product_selector,
        )
        if not selected:
            return None, None
        title, url = selected
        record = next((item for name, link, item in matches
                       if name == title and link == url), {})
        prices = record.get("prices") or {}
        amount = prices.get("price")
        if not amount and prices.get("price_range"):
            amount = prices["price_range"].get("min_amount")
        price = parse_price(amount)
        if price is None:
            print(f"Could not read a price for '{title}' on Shpresa.")
            return None, None
        return price, url
    except (requests.RequestException, ValueError) as exc:
        print(f"Could not reach Shpresa while searching for '{product_name}': {exc}")
        return None, None

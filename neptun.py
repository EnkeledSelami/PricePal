import requests

from scraper_utils import (
    canonicalize_search_query, choose_product, parse_price, product_name_matches,
)


BASE_URL = "https://www.neptun.al"
SEARCH_API = BASE_URL + "/Product/SearchProductsAutocomplete"
TIMEOUT_SECONDS = 12


def _current_price(record):
    """Use Neptun's sale price where available; otherwise the regular price."""
    for key in ("WebshopDiscountPrice", "DiscountPrice", "RegularPrice"):
        price = parse_price(record.get(key))
        if price is not None and price > 0:
            return price
    return None


def search_neptun(product_name, product_selector=None):
    # This is the endpoint used by Neptun's own Angular search. Asking for 100
    # results returns all product variants, unlike its five-item autocomplete.
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; PricePal/1.0)",
        "FROM-ANGULAR": "true",
        "Origin": BASE_URL,
        "Referer": BASE_URL + "/",
    })
    try:
        session.get(BASE_URL + "/", timeout=TIMEOUT_SECONDS)
        query = canonicalize_search_query(product_name)
        response = session.post(
            SEARCH_API,
            json={
                "term": query,
                "page": 1,
                "itemsPerPage": 100,
                "sort": 4,
            },
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        result_data = payload.get("ProductsResult", payload)
        records = result_data.get("results", [])

        matches = []
        for record in records:
            title = (record.get("Title") or record.get("ShortTitle") or "").strip()
            href = record.get("Url")
            if title and href and product_name_matches(query, title):
                url = href if href.startswith("http") else BASE_URL + href
                matches.append((title, url, record))

        # Only names are shown before selection; the chosen record's price is
        # used after the user chooses a specific storage/color variant.
        selected = choose_product(
            [(title, url) for title, url, _ in matches], "Neptun", product_name,
            selector=product_selector,
        )
        if not selected:
            return None, None
        title, url = selected
        record = next((item for name, link, item in matches
                       if name == title and link == url), {})
        price = _current_price(record)
        if price is None:
            print(f"Could not read a price for '{title}' on Neptun.")
            return None, None
        return price, url
    except (requests.RequestException, ValueError) as exc:
        print(f"Could not reach Neptun while searching for '{product_name}': {exc}")
        return None, None
    finally:
        session.close()

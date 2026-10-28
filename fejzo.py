import json
from urllib.parse import urlencode, urljoin

import requests
from bs4 import BeautifulSoup

from scraper_utils import (
    canonicalize_search_query, choose_product, parse_price, product_name_matches,
)


BASE_URL = "https://3vfejzo.al"
TIMEOUT_SECONDS = 12


def _price_from_html(html, product_name):
    """Read Fejzo's Product offer from server-rendered JSON-LD."""
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string or script.get_text())
        except (TypeError, ValueError):
            continue

        stack = [data]
        while stack:
            item = stack.pop()
            if isinstance(item, list):
                stack.extend(item)
                continue
            if not isinstance(item, dict):
                continue

            kind = item.get("@type", [])
            if isinstance(kind, str):
                kind = [kind]
            if any("Product" in value for value in kind):
                name = item.get("name", "")
                if name and name.casefold() == product_name.casefold():
                    offers = item.get("offers", [])
                    if isinstance(offers, dict):
                        offers = [offers]
                    for offer in offers:
                        if isinstance(offer, dict):
                            price = parse_price(offer.get("price", offer.get("lowPrice")))
                            if price is not None:
                                return price
            stack.extend(item.values())

    # Fallback for a future markup change that removes the Product JSON-LD.
    for element in soup.select('[itemprop="price"], meta[property*="price"]'):
        price = parse_price(element.get("content") or element.get_text(" ", strip=True))
        if price is not None:
            return price
    return None


def search_3vfejzo(product_name, product_selector=None):
    # Fejzo renders search results and Product JSON-LD on the server, so this
    # scraper does not need to launch Selenium/Chrome at all.
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; PricePal/1.0)"})
    try:
        query = canonicalize_search_query(product_name)
        search_url = BASE_URL + "/search?" + urlencode({"q": query})
        response = session.get(search_url, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        products = []
        for link in soup.select('a[href*="/product/"]'):
            title_element = link.select_one("h3")
            title = title_element.get_text(" ", strip=True) if title_element else ""
            if title and product_name_matches(query, title):
                products.append((title, urljoin(BASE_URL, link.get("href", ""))))

        selected = choose_product(products, "3V Fejzo", product_name, selector=product_selector)
        if not selected:
            return None, None
        title, product_url = selected

        product_response = session.get(product_url, timeout=TIMEOUT_SECONDS)
        product_response.raise_for_status()
        price = _price_from_html(product_response.text, title)
        if price is None:
            print(f"Could not read a price for '{title}' on 3V Fejzo.")
            return None, None
        return price, product_url
    except requests.RequestException as exc:
        print(f"Could not reach 3V Fejzo while searching for '{product_name}': {exc}")
        return None, None
    finally:
        session.close()

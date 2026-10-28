"""Shared helpers for the PricePal store scrapers."""

import re
from difflib import get_close_matches, SequenceMatcher


COMMON_PRODUCT_WORDS = (
    "iphone", "ipad", "macbook", "samsung", "galaxy", "xiaomi", "redmi",
    "pixel", "playstation", "airpods", "dyson", "nintendo", "oneplus",
    "huawei", "honor", "realme", "motorola", "lenovo", "asus", "sony",
)


def canonicalize_search_query(query):
    """Correct common one-character misspellings in product and brand names."""
    words = re.findall(r"[a-z0-9]+", (query or "").casefold())
    canonical = []
    for word in words:
        if len(word) >= 5:
            match = get_close_matches(word, COMMON_PRODUCT_WORDS, n=1, cutoff=0.80)
            if match:
                word = match[0]
        canonical.append(word)
    return " ".join(canonical)


def product_name_matches(query, title):
    """Match all query words, allowing a single typo in longer words."""
    query_words = re.findall(r"[a-z0-9]+", canonicalize_search_query(query))
    title_words = re.findall(r"[a-z0-9]+", (title or "").casefold())
    remaining = list(title_words)
    for word in query_words:
        exact = next((i for i, candidate in enumerate(remaining) if candidate == word), None)
        if exact is not None:
            remaining.pop(exact)
            continue
        if len(word) < 5:
            return False
        fuzzy = [(SequenceMatcher(None, word, candidate).ratio(), i)
                 for i, candidate in enumerate(remaining) if len(candidate) >= 5]
        if not fuzzy:
            return False
        score, index = max(fuzzy)
        if score < 0.80:
            return False
        remaining.pop(index)
    return bool(query_words)


def parse_price(value):
    """Parse whole-lek prices such as 54,990 L or 54.990 Lekë."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    digits = re.sub(r"[^0-9]", "", str(value).replace("\xa0", " "))
    return float(digits) if digits else None


def choose_product(products, store_name, product_name, selector=None):
    """Deduplicate links and return the chosen (title, URL), or None."""
    unique, seen = [], set()
    accessory_terms = (
        "case", "cover", "protector", "tempered glass", "screen glass", "screen protector",
        "lens protector", "charger", "charging cable", "cable", "adapter", "power bank",
        "holder", "mount", "stand", "sleeve", "pouch", "skin", "strap", "headphones",
        "earbuds", "airpods", "keyboard", "mouse", "stylus", "pen", "remote control",
        "xham mbrojtes", "xhami mbrojtes", "xham", "mbrojtes",
    )
    query = re.sub(r"[^a-z0-9]+", " ", (product_name or "").casefold()).strip()
    accessory_query = any(term in query for term in accessory_terms)
    for title, url in products:
        clean_title = title.strip()
        normalized_title = re.sub(r"[^a-z0-9]+", " ", clean_title.casefold())
        is_accessory = any(term in normalized_title for term in accessory_terms)
        if is_accessory and not accessory_query:
            continue
        if url and url not in seen:
            seen.add(url)
            unique.append((clean_title, url))
    if not unique:
        print("No matching products found for '{}' on {}.".format(product_name, store_name))
        return None
    if len(unique) == 1:
        return unique[0]
    if selector is not None:
        return selector(unique, store_name, product_name)
    print("Available products in {} for {}:".format(store_name, product_name))
    for number, (title, _) in enumerate(unique, 1):
        print("{}. {}".format(number, title))
    print("0. Cancel")
    while True:
        try:
            choice = int(input("Enter the number corresponding to the product: "))
            if choice == 0:
                return None
            if 1 <= choice <= len(unique):
                return unique[choice - 1]
        except ValueError:
            pass
        print("Invalid selection. Please enter a listed number.")

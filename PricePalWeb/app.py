from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import secrets
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, render_template, request, session
from flask_cors import CORS

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("PRICEPAL_DB", ROOT / "pricepal-web.sqlite3"))
TIMEOUT = 12
STORES = {
    "Shpresa": "https://shpresa.al",
    "3V Fejzo": "https://3vfejzo.al",
    "Neptun": "https://www.neptun.al",
    "Globe": "https://globe.al",
    "Aza": "https://www.azaelectronics.com",
    "Megatek": "https://www.megateksa.com/sq/",
    "Gjirafa50": "https://gjirafa50.com",
    "Ozone": "https://ozone.al",
    "German Computers": "https://www.germancomputers.al",
    "GoTech": "https://gotech.al",
}
app = Flask(__name__)
def persistent_secret_key():
    configured=os.environ.get("PRICEPAL_SECRET_KEY")
    if configured:
        return configured
    secret_file=ROOT/".secret_key"
    try:
        return secret_file.read_text(encoding="utf-8").strip()
    except OSError:
        value=secrets.token_hex(32)
        try:
            secret_file.write_text(value,encoding="utf-8")
        except OSError:
            pass
        return value

app.secret_key = persistent_secret_key()
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE=os.environ.get("SESSION_COOKIE_SAMESITE", "Lax"),
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true",
)
_allowed_origins = [
    origin.strip()
    for origin in os.environ.get(
        "PRICEPAL_ALLOWED_ORIGINS",
        "https://kelixel.com,https://www.kelixel.com,http://127.0.0.1:5001,http://localhost:5001",
    ).split(",")
    if origin.strip()
]
CORS(app, resources={r"/api/*": {"origins": _allowed_origins}}, supports_credentials=True)
_search_lock = threading.Lock()
_last_search = {}


def db():
    con = sqlite3.connect(DB_PATH, timeout=20)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS products(
          id INTEGER PRIMARY KEY, name TEXT NOT NULL, brand TEXT DEFAULT '', model TEXT DEFAULT '',
          normalized TEXT NOT NULL UNIQUE, category TEXT DEFAULT 'Technology', image_url TEXT DEFAULT '', created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS retailers(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, url TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS offers(
          id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products(id), retailer_id INTEGER NOT NULL REFERENCES retailers(id),
          url TEXT NOT NULL, latest_price REAL NOT NULL, currency TEXT NOT NULL DEFAULT 'ALL', availability TEXT DEFAULT 'unknown',
          checked_at TEXT NOT NULL, UNIQUE(retailer_id,url)
        );
        CREATE TABLE IF NOT EXISTS observations(
          id INTEGER PRIMARY KEY, offer_id INTEGER NOT NULL REFERENCES offers(id), price REAL NOT NULL,
          currency TEXT NOT NULL, observed_at TEXT NOT NULL, source TEXT NOT NULL, availability TEXT DEFAULT 'unknown'
        );
        CREATE INDEX IF NOT EXISTS obs_offer_date ON observations(offer_id,observed_at);
        CREATE TABLE IF NOT EXISTS comparisons(
          id INTEGER PRIMARY KEY, owner TEXT NOT NULL, query TEXT NOT NULL, snapshot TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS wishlist(
          id INTEGER PRIMARY KEY, owner TEXT NOT NULL, product_id INTEGER NOT NULL REFERENCES products(id),
          offer_id INTEGER REFERENCES offers(id), note TEXT DEFAULT '', target_price REAL, created_at TEXT NOT NULL,
          UNIQUE(owner,product_id,offer_id)
        );
        CREATE TABLE IF NOT EXISTS alerts(
          id INTEGER PRIMARY KEY, owner TEXT NOT NULL, product_id INTEGER NOT NULL REFERENCES products(id),
          offer_id INTEGER REFERENCES offers(id), kind TEXT NOT NULL, threshold REAL, active INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS notifications(
          id INTEGER PRIMARY KEY, owner TEXT NOT NULL, alert_id INTEGER NOT NULL REFERENCES alerts(id),
          message TEXT NOT NULL, created_at TEXT NOT NULL, read_at TEXT, dedupe_key TEXT UNIQUE NOT NULL
        );
        CREATE TABLE IF NOT EXISTS app_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        for name, url in STORES.items():
            con.execute("INSERT OR IGNORE INTO retailers(name,url) VALUES(?,?)", (name, url))


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def canonical_store(value):
    token=" ".join(re.findall(r"[a-z0-9]+",(value or "").casefold()))
    return {"shpresa":"Shpresa","3vfejzo":"3V Fejzo","3 v fejzo":"3V Fejzo","neptun":"Neptun","globe":"Globe","aza":"Aza","megatek":"Megatek","megateksa":"Megatek","gjirafa50":"Gjirafa50","gjirafa":"Gjirafa50","ozone":"Ozone","german computers":"German Computers","gotech":"GoTech"}.get(token)


def parse_history_datetime(date_value, time_value="00:00:00"):
    raw=f"{(date_value or '').strip()} {(time_value or '00:00:00').strip()}"
    for fmt in ("%Y-%m-%d %H:%M:%S","%m/%d/%Y %H:%M:%S","%d/%m/%Y %H:%M:%S"):
        try:
            return datetime.strptime(raw,fmt).replace(tzinfo=timezone.utc).isoformat(timespec="seconds")
        except ValueError:
            pass
    return now_iso()


def normalize(text):
    return " ".join(re.findall(r"[a-z0-9]+", (text or "").casefold()))


COMMON = ("iphone", "ipad", "macbook", "samsung", "galaxy", "xiaomi", "redmi", "pixel", "playstation", "airpods", "dyson", "nintendo", "oneplus", "huawei", "honor", "realme", "motorola", "lenovo", "asus", "sony")
ACCESSORIES = ("case", "cover", "protector", "tempered glass", "screen glass", "screen protector", "lens protector", "charger", "charging cable", "cable", "adapter", "power bank", "holder", "mount", "stand", "sleeve", "pouch", "skin", "strap", "headphones", "earbuds", "keyboard", "mouse", "stylus", "xham mbrojtes", "xhami mbrojtes")
# Some phone-accessory titles omit the word "case" entirely. These brand/family
# tokens are used only when the search itself names a phone rather than the token.
PHONE_ACCESSORY_FAMILIES = ("pitaka", "pitatap", "nillkin", "benks", "wiwu", "grxplore", "camshield", "iceblade", "armorgrid", "armorair", "armorpro", "green lion", "rimowa")


def canonical_query(query):
    words = normalize(query).split()
    for i, word in enumerate(words):
        if len(word) >= 5:
            close = max(((SequenceMatcher(None, word, known).ratio(), known) for known in COMMON), default=(0, word))
            if close[0] >= .8:
                words[i] = close[1]
    return " ".join(words)


def match_tokens(value):
    """Normalize common spelling/spacing variants into comparable tokens."""
    tokens = normalize(value).split()
    expanded = []
    for token in tokens:
        # Retailers variously write MiniLED, Mini Led, or Mini-LED.
        expanded.extend(("mini", "led") if token in {"miniled", "minileds"} else [token])
    return expanded


def matches(query, title):
    qw, tw = match_tokens(canonical_query(query)), match_tokens(title)
    if not qw:
        return False
    remaining = list(tw)
    for word in qw:
        found = next((i for i, candidate in enumerate(remaining) if candidate == word), None)
        if found is not None:
            remaining.pop(found)
            continue
        fuzzy = [(SequenceMatcher(None, word, item).ratio(), i) for i, item in enumerate(remaining) if len(item) >= 5]
        if len(word) < 5 or not fuzzy or max(fuzzy)[0] < .80:
            return False
        remaining.pop(max(fuzzy)[1])
    return True


def parse_price(value):
    if value is None:
        return None
    if isinstance(value, (float, int)):
        price = float(value)
    else:
        # Retail sources display whole Lek with separators; keep decimal JSON values intact.
        raw = str(value).replace("\xa0", " ").strip()
        digits = re.sub(r"[^0-9]", "", raw)
        price = float(digits) if digits else None
    return price if price and price > 0 else None


def parse_alert_threshold(value):
    """Parse the UI's comma-grouped threshold while preserving EUR cents."""
    if value is None or isinstance(value, bool):
        return None
    try:
        raw = str(value).replace(",", "").replace("\u00a0", "").strip()
        if not re.fullmatch(r"\d+(?:\.\d{1,2})?", raw):
            return None
        amount = float(raw)
        return amount if amount > 0 else None
    except (TypeError, ValueError):
        return None


def is_accessory(title, query):
    q, t = normalize(query), normalize(title)
    if any(normalize(term) in q for term in ACCESSORIES):
        return False
    return any(normalize(term) in t for term in ACCESSORIES) or ("iphone" in q and any(normalize(term) in t for term in PHONE_ACCESSORY_FAMILIES))


def product_category(title):
    t = title.casefold()
    for words, category in [(("iphone", "galaxy", "pixel", "redmi", "smartphone", "phone"), "Smartphones"), (("macbook", "laptop", "notebook", "zenbook", "thinkpad", "vivobook"), "Laptops"), (("ipad", "tablet", "tab s"), "Tablets"), (("tv", "television", "oled", "qled"), "TVs"), (("playstation", "xbox", "nintendo"), "Gaming")]:
        if any(word in t for word in words):
            return category
    return "Technology"


def http_session():
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0 (compatible; PricePal/2.0; +https://kelixel.com)"})
    return s


def fetch_shpresa(query):
    s = http_session()
    response = s.get("https://shpresa.al/wp-json/wc/store/v1/products", params={"search": canonical_query(query), "per_page": 100, "_fields": "name,permalink,type,prices,images"}, timeout=TIMEOUT)
    response.raise_for_status()
    out = []
    for record in response.json():
        title, url = (record.get("name") or "").strip(), record.get("permalink")
        if not title or not url or not matches(query, title) or is_accessory(title, query):
            continue
        prices = record.get("prices") or {}
        raw = prices.get("price") or ((prices.get("price_range") or {}).get("min_amount"))
        # WooCommerce Store API amounts may be minor units; the currency precision is supplied alongside.
        price = parse_price(raw)
        minor = int(prices.get("currency_minor_unit", 0) or 0)
        if price and minor and isinstance(raw, str) and raw.isdigit():
            price /= 10 ** minor
        imgs = record.get("images") or []
        out.append({"store":"Shpresa","title":title,"url":url,"price":price,"currency":"ALL","image":imgs[0].get("src", "") if imgs else "","availability":"unknown"})
    return out


def fetch_neptun(query):
    s = http_session()
    base = "https://www.neptun.al"
    s.headers.update({"FROM-ANGULAR":"true","Origin":base,"Referer":base+"/"})
    s.get(base + "/", timeout=TIMEOUT)
    response = s.post(base + "/Product/SearchProductsAutocomplete", json={"term":canonical_query(query),"page":1,"itemsPerPage":100,"sort":4}, timeout=TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    data = payload.get("ProductsResult", payload)
    out = []
    for item in data.get("results", []):
        title = (item.get("Title") or item.get("ShortTitle") or "").strip()
        href = item.get("Url")
        if not title or not href or not matches(query, title) or is_accessory(title, query):
            continue
        price = next((parse_price(item.get(key)) for key in ("WebshopDiscountPrice","DiscountPrice","RegularPrice") if parse_price(item.get(key))), None)
        url = href if href.startswith("http") else urljoin(base, href)
        out.append({"store":"Neptun","title":title,"url":url,"price":price,"currency":"ALL","image":item.get("ImageUrl") or item.get("Image") or "","availability":"unknown"})
    return out


def walk_json(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_json(child)


def product_jsonld_price(html, expected_title):
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string or script.get_text())
        except (TypeError, ValueError):
            continue
        for item in walk_json(data):
            typ = item.get("@type", [])
            if isinstance(typ, str):
                typ = [typ]
            if not any("Product" in x for x in typ):
                continue
            title = item.get("name") or ""
            if title and normalize(title) != normalize(expected_title):
                continue
            offers = item.get("offers") or []
            if isinstance(offers, dict):
                offers = [offers]
            for offer in offers:
                if isinstance(offer, dict):
                    amount = offer.get("price") or offer.get("lowPrice") or (offer.get("priceSpecification") or {}).get("price")
                    price = parse_price(amount)
                    if price:
                        currency = offer.get("priceCurrency") or (offer.get("priceSpecification") or {}).get("priceCurrency") or "ALL"
                        availability = (offer.get("availability") or "unknown").rsplit("/",1)[-1].casefold()
                        return price, currency, availability
    for el in soup.select('[itemprop="price"],meta[property*="price"]'):
        price = parse_price(el.get("content") or el.get_text(" ", strip=True))
        if price:
            return price, "ALL", "unknown"
    return None, "ALL", "unknown"


def fetch_fejzo(query):
    s = http_session()
    base = "https://3vfejzo.al"
    response = s.get(base + "/search?" + urlencode({"q":canonical_query(query)}), timeout=TIMEOUT)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    links, seen = [], set()
    for a in soup.select('a[href*="/product/"]'):
        h = a.get("href", "")
        title_el = a.select_one("h3")
        title = title_el.get_text(" ", strip=True) if title_el else a.get_text(" ", strip=True)
        url = urljoin(base, h)
        if title and url not in seen and matches(query,title) and not is_accessory(title,query):
            seen.add(url)
            links.append((title,url))
    def detail(pair):
        title,url=pair
        try:
            page=s.get(url,timeout=TIMEOUT)
            page.raise_for_status()
            price,currency,availability=product_jsonld_price(page.text,title)
            return {"store":"3V Fejzo","title":title,"url":url,"price":price,"currency":currency,"image":"","availability":availability}
        except requests.RequestException:
            return {"store":"3V Fejzo","title":title,"url":url,"price":None,"currency":"ALL","image":"","availability":"unknown","price_error":"Price unavailable"}
    with ThreadPoolExecutor(max_workers=5) as pool:
        return list(pool.map(detail, links[:8]))


def parse_site_price(text, currency="ALL"):
    text=(text or "").replace("\xa0"," ")
    if currency=="EUR":
        m=re.search(r"(?:€|EUR)\s*([0-9][0-9., ]*)|([0-9][0-9., ]*)\s*(?:€|EUR)",text,re.I)
        if m:
            raw=(m.group(1) or m.group(2)).replace(" ","")
            if "," in raw and "." in raw:
                raw=raw.replace(",","") if raw.rfind(".")>raw.rfind(",") else raw.replace(".","").replace(",",".")
            elif "," in raw:
                raw=raw.replace(",",".") if len(raw.rsplit(",",1)[-1]) in (1,2) else raw.replace(",","")
            try:
                amount=float(raw)
                return amount if amount>0 else None
            except ValueError:
                return None
    m=re.search(r"(?:ALL|Lek(?:ë|e)?|\bL)\s*([0-9][0-9., ]*)|([0-9][0-9., ]*)\s*(?:ALL|Lek(?:ë|e)?|\bL\b)",text,re.I)
    return parse_price((m.group(1) or m.group(2))) if m else None


def html_store_results(store, query, url, currency="ALL", card_selectors=()):
    response=http_session().get(url,timeout=TIMEOUT)
    response.raise_for_status()
    soup=BeautifulSoup(response.text,"html.parser")
    cards=[]
    for selector in card_selectors:
        cards=soup.select(selector)
        if cards: break
    if not cards:
        seen=set()
        for anchor in soup.select('a[href*="/product/"],a[href*="/p/"],a[href*="/products/"],a[href*="product_id"],a[href*="route=product/product"],a[href*="/catalog/product/view"],a[href$=".html"]'):
            node=anchor
            for _ in range(5):
                if not getattr(node,"parent",None): break
                node=node.parent
                if getattr(node,"name",None) in ("article","li") or (node.get("class") and any(any(k in str(c).casefold() for k in ("product","e-loop-item","item-product")) for c in node.get("class"))): break
            if id(node) not in seen:
                seen.add(id(node));cards.append(node)
    out=[];seen_urls=set()
    for card in cards[:100]:
        candidates=card.select('a[href*="/product/"],a[href*="/p/"],a[href*="/products/"],a[href*="product_id"],a[href*="route=product/product"],a[href*="/catalog/product/view"],a[href$=".html"]')
        a=next((x for x in candidates if x.get_text(" ",strip=True) and "quickview" not in x.get("href","").casefold() and "add-to-cart" not in x.get("href","").casefold()),None) or next((x for x in candidates if "quickview" not in x.get("href","").casefold()),None) or card.select_one("a[href]")
        if not a: continue
        title_el=card.select_one(".woocommerce-loop-product__title,.product_name,.product-title,.product-name,.name,.o_wsale_products_item_title,h2,h3,h4") or next((x for x in candidates if x.get("title")),a)
        title=title_el.get_text(" ",strip=True)
        product_url=urljoin(response.url,a.get("href",""))
        if not title or product_url in seen_urls or not matches(query,title) or is_accessory(title,query): continue
        seen_urls.add(product_url)
        price=None
        nodes=card.select(".price-new,.current-price,.special-price,.price .amount,.woocommerce-Price-amount,[itemprop=price],meta[itemprop=price],.oe_currency_value,.product-price,.product-price-and-shipping .price")
        for node in nodes:
            if node.find_parent(class_=re.compile(r"old|regular|del|original",re.I)) or node.find_parent("del"): continue
            price=parse_site_price(node.get("content") or node.get("data-price") or node.get_text(" ",strip=True),currency)
            if price: break
        if not price: price=parse_site_price(card.get_text(" ",strip=True),currency)
        img=card.select_one("img")
        out.append({"store":store,"title":title,"url":product_url,"price":price,"currency":currency,"image":(img.get("src") or img.get("data-src") or "") if img else "","availability":"unknown"})
    return out


def fetch_globe(query):
    response=http_session().get("https://globe.al/api/products/search/suggestions",params={"q":canonical_query(query)},timeout=TIMEOUT)
    response.raise_for_status();out=[]
    for item in response.json().get("products",[]):
        title=(item.get("name") or "").strip();pid=item.get("id")
        if not title or not pid or not matches(query,title) or is_accessory(title,query): continue
        price=parse_price(item.get("offerPrice") or item.get("salePrice") or item.get("price"))
        out.append({"store":"Globe","title":title,"url":"https://globe.al/products/"+str(pid),"price":price,"currency":"ALL","image":item.get("image") or "","availability":"in stock" if item.get("stock") else "unknown"})
    return out


def fetch_aza(query):
    # Aza disallows automated search URLs. Use its public product categories instead.
    q=normalize(query)
    groups=[
        (("iphone","samsung","galaxy","xiaomi","phone","telefon","smartphone","celular"),"/telefonia/celular"),
        (("macbook","laptop","notebook","thinkpad","zenbook","vivobook"),"/laptop"),
        (("ipad","tablet","tab"),"/apple"),
        (("tv","television","oled","qled"),"/tvs"),
        (("fridge","refrigerator","frigorifer"),"/frigorifere"),
        (("air conditioner","kondicioner","clima"),"/kondicioner"),
        (("headphone","earbud","kufje"),"/headphones"),
    ]
    path="/apple" if "iphone" in q else next((path for words,path in groups if any(w in q for w in words)),"/")
    return html_store_results("Aza",query,"https://www.azaelectronics.com"+path,"ALL",(".product",))


def fetch_megatek(query):
    # Magento's public catalogue search endpoint returns category-appropriate
    # products (home, appliances, furniture, garden/DIY and technology).
    url="https://www.megateksa.com/sq/catalogsearch/result/?"+urlencode({"q":canonical_query(query)})
    return html_store_results("Megatek",query,url,"ALL",("li.product-item",".product-item"))


def fetch_gjirafa50(query):
    return html_store_results("Gjirafa50",query,"https://gjirafa50.com/search?"+urlencode({"q":canonical_query(query)}),"EUR",("article.product",".product-card",".product-item","[data-product-id]"))


def fetch_ozone(query):
    # Ozone uses PrestaShop. Its live search page returns .js-product-miniature
    # cards with product links ending in .html and prices in Lekë.
    return html_store_results("Ozone",query,"https://ozone.al/search?"+urlencode({"controller":"search","s":canonical_query(query)}),"ALL",(".js-product-miniature",".product-miniature"))


def fetch_german_computers(query):
    base="https://www.germancomputers.al"
    # The live Nuxt storefront handles search from the site root. /shop?search=
    # is ignored and returns an unfiltered catalogue, so use its actual `s` query.
    response=http_session().get(base+"/?"+urlencode({"s":canonical_query(query),"post_type":"product"}),timeout=TIMEOUT)
    response.raise_for_status();soup=BeautifulSoup(response.text,"html.parser");out=[];seen=set()
    for a in soup.select('a[href*="/product/"]'):
        title=a.get_text(" ",strip=True)
        url=urljoin(base,a.get("href",""))
        if not title or url in seen or not matches(query,title) or is_accessory(title,query): continue
        seen.add(url);node=a;price=None
        for _ in range(6):
            node=node.parent
            if not getattr(node,"get_text",None): break
            price_nodes=node.select(".price,.oe_currency_value,[itemprop=price],.product-price")
            for el in price_nodes:
                price=parse_site_price(el.get("content") or el.get_text(" ",strip=True),"ALL")
                if price: break
            if not price: price=parse_site_price(node.get_text(" ",strip=True),"ALL")
            if price: break
        img=a.select_one("img") or (node.select_one("img") if getattr(node,"select_one",None) else None)
        out.append({"store":"German Computers","title":title,"url":url,"price":price,"currency":"ALL","image":(img.get("src") or img.get("data-src") or "") if img else "","availability":"unknown"})
    return out


def fetch_gotech(query):
    params=urlencode({"s":canonical_query(query),"post_type":"product","dgwt_wcas":"1"})
    return html_store_results("GoTech",query,"https://gotech.al/?"+params,"ALL",("li.product",".product-small",".product-card",".product"))


ADAPTERS = {"Shpresa":fetch_shpresa,"3V Fejzo":fetch_fejzo,"Neptun":fetch_neptun,"Globe":fetch_globe,"Aza":fetch_aza,"Megatek":fetch_megatek,"Gjirafa50":fetch_gjirafa50,"Ozone":fetch_ozone,"German Computers":fetch_german_computers,"GoTech":fetch_gotech}


def upsert_observation(item):
    if not item.get("price"):
        return None, None
    stamp=now_iso()
    with db() as con:
        norm=normalize(item["title"])
        product=con.execute("SELECT id FROM products WHERE normalized=?",(norm,)).fetchone()
        if not product:
            brand=(item["title"].split() or [""])[0]
            con.execute("INSERT OR IGNORE INTO products(name,brand,normalized,category,image_url,created_at) VALUES(?,?,?,?,?,?)",(item["title"],brand,norm,product_category(item["title"]),item.get("image", ""),stamp))
            product=con.execute("SELECT id FROM products WHERE normalized=?",(norm,)).fetchone()
        retailer=con.execute("SELECT id FROM retailers WHERE name=?",(item["store"],)).fetchone()
        cur=con.execute("SELECT id,latest_price,availability FROM offers WHERE retailer_id=? AND url=?",(retailer["id"],item["url"])).fetchone()
        if cur:
            offer_id=cur["id"]
            con.execute("UPDATE offers SET product_id=?,latest_price=?,currency=?,availability=?,checked_at=? WHERE id=?",(product["id"],item["price"],item["currency"],item["availability"],stamp,offer_id))
        else:
            cur=con.execute("INSERT INTO offers(product_id,retailer_id,url,latest_price,currency,availability,checked_at) VALUES(?,?,?,?,?,?,?)",(product["id"],retailer["id"],item["url"],item["price"],item["currency"],item["availability"],stamp))
            offer_id=cur.lastrowid
        previous=con.execute("SELECT price,availability FROM observations WHERE offer_id=? ORDER BY observed_at DESC LIMIT 1",(offer_id,)).fetchone()
        # Avoid bloating history with repeated unchanged quotes from the same search.
        if not previous or float(previous["price"]) != float(item["price"]) or previous["availability"] != item["availability"] or (datetime.now(timezone.utc)-datetime.fromisoformat(con.execute("SELECT observed_at FROM observations WHERE offer_id=? ORDER BY observed_at DESC LIMIT 1",(offer_id,)).fetchone()[0])).total_seconds()>3600:
            con.execute("INSERT INTO observations(offer_id,price,currency,observed_at,source,availability) VALUES(?,?,?,?,?,?)",(offer_id,item["price"],item["currency"],stamp,item["store"],item["availability"]))
        item.update({"product_id":product["id"],"offer_id":offer_id,"checked_at":stamp})
        evaluate_alerts(con,item)
    return item["product_id"],item["offer_id"]


def evaluate_alerts(con,item):
    rows=con.execute("SELECT * FROM alerts WHERE active=1 AND product_id=? AND (offer_id IS NULL OR offer_id=?)",(item["product_id"],item["offer_id"])).fetchall()
    for alert in rows:
        old=con.execute("SELECT price,availability FROM observations WHERE offer_id=? AND observed_at<? ORDER BY observed_at DESC LIMIT 1",(item["offer_id"],item["checked_at"])).fetchone()
        price=float(item["price"]); kind=alert["kind"]; threshold=alert["threshold"]
        triggered=(kind=="target" and threshold is not None and price<=threshold)
        if old and kind=="drop" and threshold and price <= float(old["price"])*(1-float(threshold)/100): triggered=True
        if old and kind=="low":
            historical=con.execute("SELECT MIN(price) FROM observations WHERE offer_id=? AND observed_at<?",(item["offer_id"],item["checked_at"])).fetchone()[0]
            triggered=historical is not None and price<float(historical)
        if old and kind=="back_in_stock": triggered=old["availability"] in ("outofstock","soldout") and item["availability"]=="instock"
        if old and kind=="change": triggered=abs(price-float(old["price"]))/max(float(old["price"]),1)>=.01
        if triggered:
            dedupe=hashlib.sha256(f"{alert['id']}:{item['offer_id']}:{item['checked_at'][:13]}:{kind}".encode()).hexdigest()
            msg=f"{item['title']} at {item['store']} is now {price:,.0f} {item['currency']} ({kind.replace('_',' ')} alert)."
            con.execute("INSERT OR IGNORE INTO notifications(owner,alert_id,message,created_at,dedupe_key) VALUES(?,?,?,?,?)",(alert["owner"],alert["id"],msg,item["checked_at"],dedupe))


def owner_id():
    if "owner" not in session:
        session["owner"] = secrets.token_urlsafe(24)
    return session["owner"]


def safe_live_item(item):
    return {key:item.get(key) for key in ("store","title","url","price","currency","image","availability","checked_at","product_id","offer_id","price_error")}


@app.get("/")
def index():
    owner_id()
    return render_template("index.html")


@app.get("/health")
def health():
    with db() as con:
        con.execute("SELECT 1").fetchone()
    return jsonify({"ok":True,"database":"sqlite","time":now_iso()})


@app.post("/api/search")
def api_search():
    payload=request.get_json(silent=True) or {}
    query=(payload.get("query") or "").strip()[:120]
    if len(query)<2:
        return jsonify({"error":"Enter at least two characters."}),400
    requested_stores=payload.get("stores")
    if requested_stores is not None and not isinstance(requested_stores,list):
        return jsonify({"error":"Choose one or more retailers."}),400
    selected_stores=[name for name in ADAPTERS if requested_stores is None or name in set(requested_stores)]
    if not selected_stores:
        return jsonify({"error":"Choose at least one retailer before searching."}),400
    # Per-session cooldown prevents accidental repeat hammering while allowing live search.
    token=owner_id()
    with _search_lock:
        last=_last_search.get(token,0)
        if datetime.now().timestamp()-last<1.2:
            return jsonify({"error":"Please wait a moment before searching again."}),429
        _last_search[token]=datetime.now().timestamp()
    results=[]; errors=[]
    with ThreadPoolExecutor(max_workers=len(selected_stores)) as pool:
        futures={pool.submit(ADAPTERS[name],query):name for name in selected_stores}
        for future in as_completed(futures):
            store=futures[future]
            try:
                items=future.result()
                for item in items:
                    if item.get("price"):
                        upsert_observation(item)
                    results.append(safe_live_item(item))
            except Exception as exc:
                errors.append({"store":store,"message":str(exc)[:240]})
    results.sort(key=lambda x:(x["price"] is None,x["price"] or float("inf"),x["store"],x["title"].casefold()))
    with db() as con:
        current=[x for x in results if x.get("price")]
        con.execute("INSERT INTO comparisons(owner,query,snapshot,created_at) VALUES(?,?,?,?)",(token,query,json.dumps(current,ensure_ascii=False),now_iso()))
    return jsonify({"query":query,"canonical_query":canonical_query(query),"stores":selected_stores,"results":results,"errors":errors,"checked_at":now_iso(),"notice":"Live retailer listings; verify variant, delivery and stock on the retailer page before purchase."})


@app.get("/api/history")
def api_history():
    query=(request.args.get("query") or "").strip()
    days=max(0,min(int(request.args.get("days",90) or 90),3650))
    with db() as con:
        params=[]; cond=""
        if query:
            cond="WHERE lower(p.name) LIKE ?"; params.append(f"%{query.casefold()}%")
        if days:
            cond+=(" AND " if cond else "WHERE ")+"o.observed_at>=?"; params.append((datetime.now(timezone.utc)-timedelta(days=days)).isoformat())
        rows=con.execute(f"SELECT o.id,o.price,o.currency,o.observed_at,o.source,p.id product_id,p.name product_name,of.url,of.availability FROM observations o JOIN offers of ON of.id=o.offer_id JOIN products p ON p.id=of.product_id {cond} ORDER BY o.observed_at",params).fetchall()
    return jsonify([dict(r) for r in rows])


@app.get("/api/comparisons")
def api_comparisons():
    with db() as con:
        rows=con.execute("SELECT id,query,snapshot,created_at FROM comparisons WHERE owner=? ORDER BY id DESC LIMIT 60",(owner_id(),)).fetchall()
    return jsonify([{**dict(r),"snapshot":json.loads(r["snapshot"])} for r in rows])


@app.post("/api/comparisons")
def save_comparison():
    p=request.get_json(silent=True) or {}; items=p.get("items") or []; query=(p.get("query") or "Comparison").strip()[:120]
    if not isinstance(items,list) or not items or len(items)>40: return jsonify({"error":"Select some live offers first."}),400
    with db() as con:
        con.execute("INSERT INTO comparisons(owner,query,snapshot,created_at) VALUES(?,?,?,?)",(owner_id(),query,json.dumps(items,ensure_ascii=False),now_iso()))
    return jsonify({"ok":True})


@app.get("/api/wishlist")
def get_wishlist():
    with db() as con:
        rows=con.execute("SELECT w.id,w.note,w.target_price,w.created_at,p.name product_name,p.category,of.url,of.latest_price,of.currency,of.checked_at,r.name retailer FROM wishlist w JOIN products p ON p.id=w.product_id LEFT JOIN offers of ON of.id=w.offer_id LEFT JOIN retailers r ON r.id=of.retailer_id WHERE w.owner=? ORDER BY w.id DESC",(owner_id(),)).fetchall()
    return jsonify([dict(r) for r in rows])


@app.post("/api/wishlist")
def add_wishlist():
    p=request.get_json(silent=True) or {}; pid=int(p.get("product_id") or 0); oid=int(p.get("offer_id") or 0) or None
    if not pid: return jsonify({"error":"Choose a product from live search results."}),400
    target=parse_price(p.get("target_price"))
    with db() as con:
        con.execute("INSERT OR IGNORE INTO wishlist(owner,product_id,offer_id,note,target_price,created_at) VALUES(?,?,?,?,?,?)",(owner_id(),pid,oid,(p.get("note") or "")[:300],target,now_iso()))
    return jsonify({"ok":True})


@app.delete("/api/wishlist/<int:item_id>")
def del_wishlist(item_id):
    with db() as con: con.execute("DELETE FROM wishlist WHERE id=? AND owner=?",(item_id,owner_id()))
    return jsonify({"ok":True})


@app.get("/api/alerts")
def get_alerts():
    with db() as con:
        alerts=con.execute("SELECT a.id,a.kind,a.threshold,a.active,a.created_at,p.name product_name,o.url,r.name retailer,o.latest_price,o.currency FROM alerts a JOIN products p ON p.id=a.product_id LEFT JOIN offers o ON o.id=a.offer_id LEFT JOIN retailers r ON r.id=o.retailer_id WHERE a.owner=? ORDER BY a.id DESC",(owner_id(),)).fetchall()
        notes=con.execute("SELECT id,message,created_at,read_at FROM notifications WHERE owner=? ORDER BY id DESC LIMIT 30",(owner_id(),)).fetchall()
    return jsonify({"alerts":[dict(x) for x in alerts],"notifications":[dict(x) for x in notes]})


@app.post("/api/alerts")
def add_alert():
    p=request.get_json(silent=True) or {}; pid=int(p.get("product_id") or 0); oid=int(p.get("offer_id") or 0) or None; kind=p.get("kind")
    if not pid or kind not in ("target","drop","low","back_in_stock","change"):
        return jsonify({"error":"Select a product and a supported alert type."}),400
    threshold=parse_alert_threshold(p.get("threshold")) if kind=="target" else p.get("threshold")
    if kind=="target" and not threshold: return jsonify({"error":"Enter a valid target price."}),400
    if kind=="drop":
        try: threshold=max(1,min(90,float(threshold)))
        except (TypeError,ValueError): return jsonify({"error":"Enter a drop percentage between 1 and 90."}),400
    with db() as con:
        con.execute("INSERT INTO alerts(owner,product_id,offer_id,kind,threshold,created_at) VALUES(?,?,?,?,?,?)",(owner_id(),pid,oid,kind,threshold,now_iso()))
    return jsonify({"ok":True,"note":"Alerts are evaluated when fresh retailer observations are collected. Background checks require a configured scheduler."})


@app.patch("/api/alerts/<int:alert_id>")
def toggle_alert(alert_id):
    active=1 if (request.get_json(silent=True) or {}).get("active") else 0
    with db() as con: con.execute("UPDATE alerts SET active=? WHERE id=? AND owner=?",(active,alert_id,owner_id()))
    return jsonify({"ok":True})


@app.delete("/api/alerts/<int:alert_id>")
def remove_alert(alert_id):
    with db() as con: con.execute("DELETE FROM alerts WHERE id=? AND owner=?",(alert_id,owner_id()))
    return jsonify({"ok":True})


@app.post("/api/notifications/read")
def read_notifications():
    with db() as con: con.execute("UPDATE notifications SET read_at=? WHERE owner=? AND read_at IS NULL",(now_iso(),owner_id()))
    return jsonify({"ok":True})


@app.post("/api/import/csv")
def import_csv():
    upload=request.files.get("file")
    if not upload or not upload.filename.lower().endswith(".csv"):
        return jsonify({"error":"Choose a CSV file."}),400
    try:
        text=upload.stream.read(1_500_001).decode("utf-8-sig")
        if len(text)>1_500_000: raise ValueError("File is too large.")
        reader=csv.DictReader(io.StringIO(text)); count=0
        for row in reader:
            store=canonical_store(row.get("Site") or row.get("Store") or "")
            name=(row.get("Product Name") or row.get("Product") or "").strip()
            price=parse_price(row.get("Price (Lekë)") or row.get("Price") or row.get("Price (ALL)"))
            url=(row.get("URL") or "").strip()
            if store not in STORES or not name or not price or not url or urlparse(url).scheme!="https": continue
            olddt=parse_history_datetime(row.get("Date"),row.get("Time"))
            item={"store":store,"title":name,"url":url,"price":price,"currency":"ALL","availability":"unknown","image":""}
            with db() as con:
                norm=normalize(name)
                product=con.execute("SELECT id FROM products WHERE normalized=?",(norm,)).fetchone()
                if not product:
                    con.execute("INSERT OR IGNORE INTO products(name,brand,normalized,category,created_at) VALUES(?,?,?,?,?)",(name,(name.split() or [""])[0],norm,product_category(name),olddt))
                    product=con.execute("SELECT id FROM products WHERE normalized=?",(norm,)).fetchone()
                retailer=con.execute("SELECT id FROM retailers WHERE name=?",(store,)).fetchone()
                offer=con.execute("SELECT id,checked_at FROM offers WHERE retailer_id=? AND url=?",(retailer["id"],url)).fetchone()
                if offer:
                    oid=offer["id"]
                    if olddt >= offer["checked_at"]:
                        con.execute("UPDATE offers SET product_id=?,latest_price=?,currency='ALL',checked_at=? WHERE id=?",(product["id"],price,olddt,oid))
                else:
                    oid=con.execute("INSERT INTO offers(product_id,retailer_id,url,latest_price,currency,availability,checked_at) VALUES(?,?,?,?,'ALL','unknown',?)",(product["id"],retailer["id"],url,price,olddt)).lastrowid
                con.execute("INSERT INTO observations(offer_id,price,currency,observed_at,source,availability) VALUES(?,?,'ALL',?,'CSV import','unknown')",(oid,price,olddt))
                count+=1
        return jsonify({"ok":True,"imported":count,"message":f"Imported {count} usable historical rows."})
    except (UnicodeDecodeError,csv.Error,ValueError) as exc:
        return jsonify({"error":f"Could not import CSV: {exc}"}),400


@app.get("/api/summary")
def summary():
    with db() as con:
        return jsonify({"products":con.execute("SELECT COUNT(*) FROM products").fetchone()[0],"offers":con.execute("SELECT COUNT(*) FROM offers").fetchone()[0],"observations":con.execute("SELECT COUNT(*) FROM observations").fetchone()[0],"wishlist":con.execute("SELECT COUNT(*) FROM wishlist WHERE owner=?",(owner_id(),)).fetchone()[0],"alerts":con.execute("SELECT COUNT(*) FROM alerts WHERE owner=? AND active=1",(owner_id(),)).fetchone()[0]})


def bootstrap_legacy_history():
    """Import a copied desktop history once; never writes back to the desktop file."""
    source = ROOT / "data" / "PriceHistory.csv"
    with db() as con:
        done = con.execute("SELECT value FROM app_meta WHERE key='legacy_csv_imported'").fetchone()
        if done:
            return
        if source.exists():
            with source.open("r", encoding="utf-8-sig", newline="") as fh:
                for row in csv.DictReader(fh):
                    store=canonical_store(row.get("Site") or row.get("Store") or "")
                    name=(row.get("Product Name") or row.get("Product") or "").strip()
                    price=parse_price(row.get("Price (Lekë)") or row.get("Price") or row.get("Price (ALL)"))
                    url=(row.get("URL") or "").strip()
                    if store not in STORES or not name or not price or urlparse(url).scheme!="https":
                        continue
                    observed=parse_history_datetime(row.get("Date"),row.get("Time"))
                    norm=normalize(name)
                    product=con.execute("SELECT id FROM products WHERE normalized=?",(norm,)).fetchone()
                    if not product:
                        con.execute("INSERT OR IGNORE INTO products(name,brand,normalized,category,created_at) VALUES(?,?,?,?,?)",(name,(name.split() or [""])[0],norm,product_category(name),observed))
                        product=con.execute("SELECT id FROM products WHERE normalized=?",(norm,)).fetchone()
                    retailer=con.execute("SELECT id FROM retailers WHERE name=?",(store,)).fetchone()
                    offer=con.execute("SELECT id,checked_at FROM offers WHERE retailer_id=? AND url=?",(retailer["id"],url)).fetchone()
                    if offer:
                        oid=offer["id"]
                        if observed>=offer["checked_at"]:
                            con.execute("UPDATE offers SET product_id=?,latest_price=?,currency='ALL',checked_at=? WHERE id=?",(product["id"],price,observed,oid))
                    else:
                        oid=con.execute("INSERT INTO offers(product_id,retailer_id,url,latest_price,currency,availability,checked_at) VALUES(?,?,?,?,'ALL','unknown',?)",(product["id"],retailer["id"],url,price,observed)).lastrowid
                    con.execute("INSERT INTO observations(offer_id,price,currency,observed_at,source,availability) VALUES(?,?,'ALL',?,'Desktop CSV','unknown')",(oid,price,observed))
        con.execute("INSERT OR REPLACE INTO app_meta(key,value) VALUES('legacy_csv_imported',?)",(now_iso(),))


init_db()
bootstrap_legacy_history()
if __name__ == "__main__":
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "5000")), debug=False, threaded=True)

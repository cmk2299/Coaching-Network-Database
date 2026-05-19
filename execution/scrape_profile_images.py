#!/usr/bin/env python3
"""
Scrape profile images from Transfermarkt for network contacts.
Falls back to Wikipedia if no TM image found.

Output: data/profile_images.json
  { "Name": "https://img.url/...", ... }
"""

import json
import time
import re
import os
import sys
from urllib.request import Request, urlopen
from urllib.parse import quote
from html.parser import HTMLParser

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
CACHE_DIR = "/tmp/cache/images"
os.makedirs(CACHE_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

DELAY = 3  # seconds between requests


class TMImageParser(HTMLParser):
    """Extract profile image URL from Transfermarkt profile page."""
    def __init__(self):
        super().__init__()
        self.image_url = None
        self.in_header = False
        self.in_photo = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        # TM uses data-header-tag or specific img classes for the profile image
        if tag == "div" and "data-header-tag" in attrs_dict:
            self.in_header = True
        if tag == "div" and "photo-container" in attrs_dict.get("class", ""):
            self.in_photo = True
        # Look for the main profile image
        if tag == "img" and (self.in_header or self.in_photo):
            src = attrs_dict.get("src", "")
            data_src = attrs_dict.get("data-src", "")
            url = data_src or src
            if url and "images" in url and "default" not in url.lower() and "placeholder" not in url.lower():
                # Get the higher-res version by modifying the URL
                # TM uses different size suffixes like /small/, /medium/, /big/
                url = url.replace("/small/", "/medium/").replace("/mini/", "/medium/")
                if not self.image_url:
                    self.image_url = url

    def handle_endtag(self, tag):
        if tag == "div":
            self.in_header = False
            self.in_photo = False


def fetch_url(url, cache_key=None):
    """Fetch URL with caching."""
    if cache_key:
        cache_path = os.path.join(CACHE_DIR, cache_key + ".html")
        if os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()

    try:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
            if cache_key:
                with open(cache_path, "w", encoding="utf-8") as f:
                    f.write(html)
            return html
    except Exception as e:
        print(f"  ERROR fetching {url}: {e}", file=sys.stderr)
        return None


def get_tm_image(tm_url, name):
    """Get profile image from Transfermarkt."""
    if not tm_url:
        return None

    # Normalize URL
    if tm_url.startswith("/"):
        tm_url = "https://www.transfermarkt.de" + tm_url

    cache_key = f"tm_{name.replace(' ', '_').lower()}"
    html = fetch_url(tm_url, cache_key)
    if not html:
        return None

    # Try parsing with our custom parser
    parser = TMImageParser()
    try:
        parser.feed(html)
    except Exception:
        pass

    if parser.image_url:
        return parser.image_url

    # Fallback: regex for og:image meta tag
    og_match = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html)
    if og_match:
        url = og_match.group(1)
        if "default" not in url.lower() and "placeholder" not in url.lower():
            return url

    # Fallback: any profile image pattern
    img_match = re.search(r'(https://img\.a\.transfermarkt\.technology/portrait/[^"\']+)', html)
    if img_match:
        return img_match.group(1)

    return None


def get_wikipedia_image(name):
    """Try to get profile image from Wikipedia (German first, then English)."""
    for lang in ["de", "en"]:
        try:
            # Use Wikipedia API to get page images
            api_url = f"https://{lang}.wikipedia.org/w/api.php?action=query&titles={quote(name)}&prop=pageimages&format=json&pithumbsize=200"
            req = Request(api_url, headers={"User-Agent": "FootballCoachesDB/1.0"})
            with urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                pages = data.get("query", {}).get("pages", {})
                for pid, page in pages.items():
                    if pid == "-1":
                        continue
                    thumb = page.get("thumbnail", {}).get("source")
                    if thumb:
                        # Get higher res version
                        thumb = re.sub(r'/\d+px-', '/300px-', thumb)
                        return thumb
        except Exception:
            pass
        time.sleep(1)
    return None


def main():
    # Load network data
    network_path = os.path.join(DATA_DIR, "blessin_full_network.json")
    with open(network_path, "r") as f:
        network = json.load(f)

    # Load existing results if any
    output_path = os.path.join(DATA_DIR, "profile_images.json")
    if os.path.exists(output_path):
        with open(output_path, "r") as f:
            images = json.load(f)
    else:
        images = {}

    # Also scrape center person
    center_url = network.get("center_info", {}).get("tm_url")
    center_name = network.get("center", "Alexander Blessin")
    if center_name not in images and center_url:
        print(f"Scraping center: {center_name}")
        img = get_tm_image(center_url, center_name)
        if img:
            images[center_name] = img
            print(f"  ✓ TM image found")
        else:
            img = get_wikipedia_image(center_name)
            if img:
                images[center_name] = img
                print(f"  ✓ Wikipedia image found")
            else:
                print(f"  ✗ No image found")
        time.sleep(DELAY)

    # Process contacts
    contacts = network["contacts"]
    total = len(contacts)
    found = 0
    skipped = 0

    for i, c in enumerate(contacts):
        name = c["name"]
        if name in images:
            skipped += 1
            continue

        tm_url = c.get("tm_url", "")
        print(f"[{i+1}/{total}] {name}...", end=" ", flush=True)

        # Try TM first
        img = get_tm_image(tm_url, name)
        if img:
            images[name] = img
            found += 1
            print(f"✓ TM")
        else:
            # Try Wikipedia
            img = get_wikipedia_image(name)
            if img:
                images[name] = img
                found += 1
                print(f"✓ Wikipedia")
            else:
                print(f"✗")

        # Save incrementally
        if (i + 1) % 10 == 0:
            with open(output_path, "w") as f:
                json.dump(images, f, indent=2, ensure_ascii=False)
            print(f"  [Saved: {len(images)} images so far]")

        time.sleep(DELAY)

    # Final save
    with open(output_path, "w") as f:
        json.dump(images, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*50}")
    print(f"Total contacts: {total}")
    print(f"Skipped (already had): {skipped}")
    print(f"Newly found: {found}")
    print(f"Total with images: {len(images)}")
    print(f"Coverage: {len(images)}/{total + 1} ({100*len(images)//(total+1)}%)")
    print(f"Saved to: {output_path}")


if __name__ == "__main__":
    main()

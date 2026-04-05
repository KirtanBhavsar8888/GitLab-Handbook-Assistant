import requests
from bs4 import BeautifulSoup
import json
import time
from urllib.parse import urljoin, urlparse

DIRECTION_URL = "https://about.gitlab.com/direction/"

# Only scrape these sections — most relevant for employees/candidates
HANDBOOK_SECTIONS = [
    "https://handbook.gitlab.com/handbook/values/",
    "https://handbook.gitlab.com/handbook/company/",
    "https://handbook.gitlab.com/handbook/engineering/",
    "https://handbook.gitlab.com/handbook/product/",
    "https://handbook.gitlab.com/handbook/people-group/",
    "https://handbook.gitlab.com/handbook/finance/",
    "https://handbook.gitlab.com/handbook/marketing/",
    "https://handbook.gitlab.com/handbook/sales/",
    "https://handbook.gitlab.com/handbook/security/",
    "https://handbook.gitlab.com/handbook/legal/",
]

MAX_PAGES_PER_SECTION = 50  # cap per section → ~300 pages total
VISITED = set()


def scrape_page(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, timeout=10, headers=headers)
        if resp.status_code != 200:
            return None, []
        soup = BeautifulSoup(resp.text, "lxml")

        # Collect child links within the same section before removing nav
        links = []
        for a in soup.find_all("a", href=True):
            href = urljoin(url, a["href"])
            # Only keep links that stay within handbook.gitlab.com
            if href.startswith("https://handbook.gitlab.com/handbook/"):
                links.append(href.split("#")[0])  # strip anchors

        # Clean page
        for tag in soup(["nav", "footer", "script", "style", "header", "aside"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)

        if len(text) < 200:
            return None, links
        return text, links

    except Exception as e:
        print(f"  Error: {e}")
        return None, []


def crawl_section(base_url, max_pages):
    """BFS crawl within a section, up to max_pages."""
    queue = [base_url]
    section_data = []

    while queue and len(section_data) < max_pages:
        url = queue.pop(0)
        if url in VISITED:
            continue
        VISITED.add(url)

        # Only crawl URLs that belong to this section
        if not url.startswith(base_url):
            continue

        print(f"  Scraping: {url}")
        text, child_links = scrape_page(url)

        if text:
            section_data.append({"url": url, "text": text})

        # Add unvisited child links to queue
        for link in child_links:
            if link not in VISITED and link.startswith(base_url):
                queue.append(link)

        time.sleep(0.3)

    return section_data


def main():
    data = []

    # 1. Direction page (single page)
    print("Scraping Direction page...")
    text, _ = scrape_page(DIRECTION_URL)
    if text:
        data.append({"url": DIRECTION_URL, "text": text})
        print(f"  Done ({len(text)} chars)")

    # 2. Each handbook section
    for section_url in HANDBOOK_SECTIONS:
        section_name = section_url.split("/handbook/")[-1].strip("/")
        print(f"\nCrawling section: {section_name}")
        section_data = crawl_section(section_url, MAX_PAGES_PER_SECTION)
        data.extend(section_data)
        print(f"  Got {len(section_data)} pages from {section_name}")

    # 3. Save
    with open("scraped_data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

    print(f"\n✅ Done! Saved {len(data)} pages to scraped_data.json")


if __name__ == "__main__":
    main()
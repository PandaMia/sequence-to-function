import csv
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup


ARTICLE_CSV_PATH = Path("data/articles.csv")
SEQUENCE_CSV_PATH = Path("data/sequence_data.csv")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

CONTENT_SELECTORS = (
    "article",
    ".article",
    ".article-body",
    ".content",
    ".main-content",
    "#content",
    ".abstract",
    ".full-text",
    "#enc-abstract",
    "#maincontent",
    "main",
)


def fetch_article_text(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
    response.raise_for_status()

    soup = BeautifulSoup(response.content, "html.parser")
    for element in soup(["script", "style", "nav", "footer"]):
        element.decompose()

    content = None
    for selector in CONTENT_SELECTORS:
        elements = soup.select(selector)
        if elements:
            content = elements[0]
            break
    if not content:
        content = soup.body or soup

    text = content.get_text(" ")
    return re.sub(r"\s+", " ", text).strip()


def ensure_articles_csv() -> None:
    if ARTICLE_CSV_PATH.exists():
        return
    if not SEQUENCE_CSV_PATH.exists():
        raise FileNotFoundError(f"Neither {ARTICLE_CSV_PATH} nor {SEQUENCE_CSV_PATH} exists")

    with SEQUENCE_CSV_PATH.open(newline="") as file:
        reader = csv.DictReader(file)
        sequence_rows = list(reader)

    articles: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in sequence_rows:
        url = (row.get("article_url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        articles.append(
            {
                "id": str(len(articles) + 1),
                "url": url,
                "article_text": row.get("article_text", ""),
                "created_at": row.get("created_at", ""),
                "updated_at": row.get("created_at", ""),
            }
        )

    ARTICLE_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with ARTICLE_CSV_PATH.open("w", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["id", "url", "article_text", "created_at", "updated_at"],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(articles)


def main() -> None:
    ensure_articles_csv()

    with ARTICLE_CSV_PATH.open(newline="") as file:
        reader = csv.DictReader(file)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    if "article_text" not in fieldnames:
        insert_at = fieldnames.index("created_at") if "created_at" in fieldnames else len(fieldnames)
        fieldnames.insert(insert_at, "article_text")

    texts: dict[str, str] = {}
    for row in rows:
        url = (row.get("url") or "").strip()
        if not url:
            continue
        try:
            text = fetch_article_text(url)
            texts[url] = text
            print(f"OK {len(text):6d} {url}")
        except Exception as exc:
            texts[url] = ""
            print(f"ERR {url}: {exc}")

    for row in rows:
        url = (row.get("url") or "").strip()
        row["article_text"] = texts.get(url, row.get("article_text", ""))

    rows.sort(key=lambda row: int((row.get("id") or "0").strip() or 0))
    with ARTICLE_CSV_PATH.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()

"""Shared helper functions for STF function tools."""

from __future__ import annotations

import base64
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import requests


def jsonable(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def row_to_dict(columns: list[str], row: Any) -> dict[str, Any]:
    row_dict: dict[str, Any] = {}
    for index, column in enumerate(columns):
        row_dict[column] = jsonable(row[index])
    return row_dict


def absolute_url(base: str, raw_url: str | None) -> str | None:
    if not raw_url:
        return None
    try:
        return urljoin(base, raw_url)
    except Exception:
        return None


def normalize_html_text(element: Any) -> str:
    extracted_text = element.get_text()
    lines = (line.strip() for line in extracted_text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    return re.sub(r"\s+", " ", " ".join(chunk for chunk in chunks if chunk)).strip()


def is_relevant_article_image(img_tag: Any, candidate_url: str) -> bool:
    bad_extensions = (".svg", ".ico", ".gif")
    good_hints = ("figure", "fig", "graph", "plot", "gel", "western", "microscop", "blot", "supp", "supplement")
    bad_hints = (
        "logo",
        "icon",
        "avatar",
        "sprite",
        "banner",
        "ad",
        "advert",
        "cookie",
        "gdpr",
        "social",
        "share",
        "header",
        "footer",
        "nav",
    )

    lowered_url = candidate_url.lower()
    alt = (img_tag.get("alt") or "").lower()
    css_class = " ".join(img_tag.get("class") or []).lower()
    element_id = (img_tag.get("id") or "").lower()
    if any(lowered_url.endswith(ext) for ext in bad_extensions):
        return False
    if any(hint in lowered_url for hint in bad_hints):
        return False
    if any(hint in alt for hint in bad_hints):
        return False
    if any(hint in css_class for hint in bad_hints):
        return False
    if any(hint in element_id for hint in bad_hints):
        return False
    if any(hint in lowered_url for hint in good_hints) or any(hint in css_class for hint in good_hints):
        return True
    return bool(alt.strip())


def download_image_as_data_url(url: str) -> str:
    """Download an image and convert it to a base64 data URL."""

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
        ),
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/",
    }
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    content_type = response.headers.get("content-type", "")
    if not content_type.startswith("image/"):
        raise ValueError(f"URL did not return an image (content-type: {content_type})")

    return "data:image/*;base64," + base64.b64encode(response.content).decode("utf-8")


def download_pdf_b64(url: str) -> tuple[str, str, str]:
    """Download a PDF and return base64 data, content type, and filename."""

    session = requests.Session()

    def is_pdf_bytes(data: bytes) -> bool:
        head = data[:4096].lstrip(b"\xef\xbb\xbf\r\n\t \x00")
        return head.startswith(b"%PDF")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
        ),
        "Accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.8",
    }

    def get(candidate_url: str) -> tuple[requests.Response, str]:
        response = session.get(candidate_url, headers=headers, timeout=60, allow_redirects=True)
        response.raise_for_status()
        return response, (response.headers.get("content-type") or "").lower()

    response, content_type = get(url)
    if content_type.startswith(("application/pdf", "application/octet-stream")) and is_pdf_bytes(response.content):
        filename = url.split("?")[0].split("/")[-1] or "document.pdf"
        return base64.b64encode(response.content).decode("ascii"), "application/pdf", filename

    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    query["download"] = ["1"]
    download_url = urlunparse(
        parsed._replace(
            query=urlencode({key: value[0] if len(value) == 1 else value for key, value in query.items()}, doseq=True)
        )
    )

    if download_url != url:
        response, content_type = get(download_url)
        if content_type.startswith(("application/pdf", "application/octet-stream")) and is_pdf_bytes(response.content):
            filename = url.split("?")[0].split("/")[-1] or "document.pdf"
            return base64.b64encode(response.content).decode("ascii"), "application/pdf", filename

    raise ValueError(f"URL did not return a PDF (content-type: {content_type or 'unknown'})")

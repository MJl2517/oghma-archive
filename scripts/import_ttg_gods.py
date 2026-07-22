from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import (  # noqa: E402
    DEFAULT_GOD_ALIGNMENTS,
    app,
    get_campaign,
    get_campaigns,
    load_gods,
    normalize_god,
    save_god_alignments,
    save_god_domains,
    save_gods,
)

API_ROOT = "https://5e14.ttg.club/api/v1"


class HtmlToText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.link_href: str = ""

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"p", "div", "section", "ul", "ol", "blockquote"}:
            self.parts.append("\n\n")
        elif tag == "li":
            self.parts.append("\n- ")
        elif tag == "br":
            self.parts.append("\n")
        elif tag == "a":
            self.link_href = dict(attrs).get("href", "")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"p", "div", "section", "li", "blockquote"}:
            self.parts.append("\n")
        elif tag == "a":
            self.link_href = ""

    def handle_data(self, data: str) -> None:
        text = re.sub(r"\s+", " ", data).strip()
        if not text:
            return
        if self.link_href:
            self.parts.append(f"[{text}]({self.link_href})")
        else:
            self.parts.append(text)

    def text(self) -> str:
        content = "".join(self.parts)
        content = re.sub(r"[ \t]+\n", "\n", content)
        content = re.sub(r"\n{3,}", "\n\n", content)
        return content.strip()


def post_json(path: str, payload: dict | None = None):
    data = json.dumps(payload or {}).encode("utf-8")
    request = Request(
        f"{API_ROOT}{path}",
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def source_label(source) -> tuple[str, str]:
    if not isinstance(source, dict):
        return (str(source or "").strip(), "")
    short_name = str(source.get("shortName") or "").strip()
    name = str(source.get("name") or "").strip()
    return (short_name or name, name)


def detail_to_god(detail: dict, now: str) -> dict:
    name = detail.get("name") if isinstance(detail.get("name"), dict) else {}
    parser = HtmlToText()
    parser.feed(str(detail.get("description") or ""))
    source, source_name = source_label(detail.get("source"))
    url = str(detail.get("url") or "").strip()
    if not url:
        english = str(name.get("eng") or "").strip().casefold().replace(" ", "-")
        url = f"/gods/{english}" if english else ""
    return normalize_god(
        {
            "id": re.sub(r"[^a-z0-9а-яё]+", "-", url.strip("/").split("/")[-1].casefold()).strip("-") or "",
            "name": str(name.get("rus") or "").strip(),
            "english_name": str(name.get("eng") or "").strip(),
            "url": f"https://5e14.ttg.club{url}" if url.startswith("/") else url,
            "alignment": detail.get("alignment", ""),
            "short_alignment": detail.get("shortAlignment", ""),
            "description": parser.text(),
            "rank": detail.get("rank", ""),
            "titles": detail.get("titles", []),
            "symbol": detail.get("symbol", ""),
            "domains": detail.get("domains", []),
            "pantheons": detail.get("panteons", detail.get("pantheons", [])),
            "images": detail.get("images", []),
            "source": source,
            "source_name": source_name,
            "created_at": now,
            "updated_at": now,
        }
    )


def import_gods(campaign_slug: str) -> dict:
    campaign = get_campaign(campaign_slug)
    if not campaign:
        raise SystemExit(f"Campaign not found: {campaign_slug}")

    filters = post_json("/filters/gods")
    alignments = [
        item.get("label", "")
        for group in filters.get("other", [])
        if group.get("key") == "alignment"
        for item in group.get("values", [])
        if item.get("label")
    ] or DEFAULT_GOD_ALIGNMENTS[:]
    domains = [
        item.get("label", "")
        for group in filters.get("other", [])
        if group.get("key") == "domain"
        for item in group.get("values", [])
        if item.get("label")
    ]

    list_items = post_json("/gods")
    now = datetime.now().isoformat(timespec="seconds")
    gods = []
    for index, item in enumerate(list_items, start=1):
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        try:
            detail = post_json(url)
        except Exception as exc:
            print(f"skip {url}: {exc}", file=sys.stderr)
            continue
        detail["url"] = url
        gods.append(detail_to_god(detail, now))
        if index % 25 == 0:
            print(f"loaded {index}/{len(list_items)}")

    existing = [normalize_god(item, campaign_slug) for item in load_gods(campaign_slug)]
    imported_keys = {
        (god.get("id") or "").casefold()
        for god in gods
        if god.get("id")
    } | {
        (god.get("url") or "").casefold()
        for god in gods
        if god.get("url")
    }
    preserved = [
        god
        for god in existing
        if (god.get("id") or "").casefold() not in imported_keys
        and (god.get("url") or "").casefold() not in imported_keys
    ]
    save_gods(campaign_slug, [*preserved, *gods])
    if domains:
        save_god_domains(campaign_slug, domains)
    save_god_alignments(campaign_slug, alignments)
    return {
        "campaign": campaign_slug,
        "imported": len(gods),
        "preserved": len(preserved),
        "total": len(preserved) + len(gods),
        "domains": len(domains),
        "alignments": len(alignments),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Import gods from 5e14.ttg.club into an Oghma campaign.")
    parser.add_argument("--campaign", default="", help="Campaign slug. Defaults to the first campaign.")
    args = parser.parse_args()
    with app.test_request_context("/"):
        campaign_slug = args.campaign or get_campaigns()[0]["slug"]
        summary = import_gods(campaign_slug)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()

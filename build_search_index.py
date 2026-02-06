#!/usr/bin/env python3
"""Build search-index.json from site HTML files.

Usage: uv run --with beautifulsoup4 python build_search_index.py
"""

import json
import re
from pathlib import Path

from bs4 import BeautifulSoup, Tag

SITE_DIR = Path(__file__).parent
OUTPUT = SITE_DIR / "search-index.json"


def text(el: Tag | None) -> str:
    """Extract clean text from an element."""
    if el is None:
        return ""
    return re.sub(r"\s+", " ", el.get_text(separator=" ")).strip()


def truncate(s: str, max_len: int = 300) -> str:
    if len(s) <= max_len:
        return s
    return s[:max_len].rsplit(" ", 1)[0] + "…"


def parse_qa(soup: BeautifulSoup) -> list[dict]:
    """Extract Q&A cards from qa.html."""
    entries = []
    for card in soup.select(".qa-card"):
        card_id = card.get("id", "")
        question = text(card.select_one(".qa-question-text"))
        # Remove the # permalink character
        if question.startswith("#"):
            question = question[1:].strip()
        content = text(card.select_one(".qa-content"))
        entries.append({
            "id": f"qa-{card_id}",
            "title": question,
            "content": content,
            "excerpt": truncate(content),
            "url": f"qa#{card_id}",
            "type": "qa",
            "type_label": "Q&A",
        })
    return entries


def parse_arg_cards(soup: BeautifulSoup, page_url: str, type_id: str, type_label: str) -> list[dict]:
    """Extract argument cards from argumentit.html or kielen-valta.html."""
    entries = []
    for card in soup.select(".arg-card"):
        card_id = card.get("id", "")
        num = text(card.select_one(".arg-num"))
        claim = text(card.select_one(".arg-claim"))
        label = text(card.select_one(".arg-label"))
        title = f"{num} {claim}".strip()
        if label:
            title = f"{title} ({label})"

        body = text(card.select_one(".arg-vastaus")) or text(card.select_one(".arg-body"))
        entries.append({
            "id": f"{type_id}-{card_id}",
            "title": title,
            "content": body,
            "excerpt": truncate(body),
            "url": f"{page_url}#{card_id}",
            "type": type_id,
            "type_label": type_label,
        })
    return entries


def parse_essay(soup: BeautifulSoup, page_url: str, type_id: str, type_label: str) -> list[dict]:
    """Extract sections from essay pages (kannustinketju, etc.)."""
    entries = []
    essay_body = soup.select_one(".essay-body")
    if not essay_body:
        return entries

    sections = essay_body.select("section")
    if not sections:
        # Treat entire essay body as one entry
        content = text(essay_body)
        h1 = soup.select_one(".essay-header h1")
        entries.append({
            "id": f"{type_id}-full",
            "title": text(h1) if h1 else type_label,
            "content": content,
            "excerpt": truncate(content),
            "url": page_url,
            "type": type_id,
            "type_label": type_label,
        })
        return entries

    for i, section in enumerate(sections):
        h2 = section.select_one("h2")
        h3 = section.select_one("h3")
        heading = text(h2) or text(h3) or f"Osio {i + 1}"

        # Try to find an anchor
        anchor = ""
        heading_el = h2 or h3
        if heading_el:
            a = heading_el.select_one("a[id]")
            if a:
                anchor = f"#{a['id']}"
            elif heading_el.get("id"):
                anchor = f"#{heading_el['id']}"

        content = text(section)
        entries.append({
            "id": f"{type_id}-s{i}",
            "title": heading,
            "content": content,
            "excerpt": truncate(content),
            "url": f"{page_url}{anchor}",
            "type": type_id,
            "type_label": type_label,
        })
    return entries


def parse_sisallys(soup: BeautifulSoup) -> list[dict]:
    """Extract table of contents entries."""
    entries = []
    for chapter in soup.select(".toc-chapter"):
        title_el = chapter.select_one(".toc-chapter-title")
        if not title_el:
            continue
        title = text(title_el)
        # Clean badge text from title
        badge = title_el.select_one(".toc-badge")
        badge_text = text(badge) if badge else ""

        link = title_el.select_one("a[href]")
        url = link["href"] if link else "sisallys"

        sections_el = chapter.select_one(".toc-sections")
        section_items = [text(li) for li in sections_el.select("li")] if sections_el else []
        content = " — ".join(section_items) if section_items else title

        entries.append({
            "id": f"toc-{url}",
            "title": title.replace(badge_text, "").strip(),
            "content": content,
            "excerpt": truncate(content),
            "url": url if url.startswith("http") else f"sisallys",
            "type": "toc",
            "type_label": "Sisällys",
        })
    return entries


def parse_terms(soup: BeautifulSoup) -> list[dict]:
    """Extract term definitions from sanakirja.html."""
    entries = []
    for term in soup.select(".term"):
        h3 = term.select_one("h3")
        p = term.select_one("p")
        if not h3:
            continue
        title = text(h3)
        content = text(p) if p else ""
        entries.append({
            "id": f"term-{title.lower().replace(' ', '-')}",
            "title": title,
            "content": content,
            "excerpt": truncate(content),
            "url": "/sanakirja",
            "type": "termi",
            "type_label": "Käsite",
        })
    return entries


def load_soup(filename: str) -> BeautifulSoup | None:
    path = SITE_DIR / filename
    if not path.exists():
        print(f"  Skipping {filename} (not found)")
        return None
    return BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")


def main():
    all_entries: list[dict] = []

    # Q&A
    print("Indexing qa.html...")
    soup = load_soup("qa.html")
    if soup:
        entries = parse_qa(soup)
        print(f"  {len(entries)} Q&A cards")
        all_entries.extend(entries)

    # Argumentit
    print("Indexing argumentit.html...")
    soup = load_soup("argumentit.html")
    if soup:
        entries = parse_arg_cards(soup, "argumentit", "arg", "Systeemivirhe")
        print(f"  {len(entries)} arguments")
        all_entries.extend(entries)

    # Kielen valta
    print("Indexing kielen-valta.html...")
    soup = load_soup("kielen-valta.html")
    if soup:
        entries = parse_arg_cards(soup, "kielen-valta", "kieli", "Kielen valta")
        print(f"  {len(entries)} language patterns")
        all_entries.extend(entries)

    # Kannustinketju
    print("Indexing kannustinketju.html...")
    soup = load_soup("kannustinketju.html")
    if soup:
        entries = parse_essay(soup, "kannustinketju", "kannustin", "Kannustinketju")
        print(f"  {len(entries)} sections")
        all_entries.extend(entries)

    # sanakirja page terms
    print("Indexing sanakirja.html terms...")
    soup = load_soup("sanakirja.html")
    if soup:
        entries = parse_terms(soup)
        print(f"  {len(entries)} terms")
        all_entries.extend(entries)

    # Write output
    OUTPUT.write_text(
        json.dumps(all_entries, ensure_ascii=False, indent=1, sort_keys=True),
        encoding="utf-8",
    )
    size_kb = OUTPUT.stat().st_size / 1024
    print(f"\nWrote {len(all_entries)} entries to {OUTPUT} ({size_kb:.0f} KB)")


if __name__ == "__main__":
    main()

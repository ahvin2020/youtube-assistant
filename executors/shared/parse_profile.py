"""Parse channel-profile.md to extract discovery config for executors.

Shared module used by executors across thumbnail/ and topics/ domains.
"""

import re


def parse_channel_profile(path: str) -> dict:
    """Read channel-profile.md and return structured config.

    Returns dict with keys: niche_terms, niche_keywords, own_niche_categories,
    adjacent_niche_categories, subreddits, twitter_search_terms, region,
    cross_niche_keywords, monitored_channels.
    """
    with open(path) as f:
        text = f.read()

    sections = _split_sections(text)

    return {
        "niche_terms": _parse_csv_line(sections.get("Niche Terms", "")),
        "niche_keywords": _parse_csv_line(sections.get("Discovery Keywords", "")),
        "own_niche_categories": _parse_list_value(
            sections.get("Niche Categories", ""), "Own"
        ),
        "adjacent_niche_categories": _parse_list_value(
            sections.get("Niche Categories", ""), "Adjacent"
        ),
        "subreddits": _parse_list_value(
            sections.get("Community Sources", ""), "Subreddits"
        ),
        "twitter_search_terms": _parse_list_value(
            sections.get("Community Sources", ""), "Twitter search terms"
        ),
        "region": sections.get("Region", "").strip(),
        "cross_niche_keywords": _parse_csv_line(
            sections.get("Cross-Niche Keywords", "")
        ),
        "monitored_channels": _parse_monitored_channels(
            sections.get("Monitored Channels", "")
        ),
    }


def _split_sections(text: str) -> dict[str, str]:
    """Split markdown into {heading: body} pairs for ## headings."""
    result: dict[str, str] = {}
    current = None
    lines: list[str] = []
    for line in text.splitlines():
        m = re.match(r"^##\s+(.+)$", line)
        if m:
            if current is not None:
                result[current] = "\n".join(lines)
            current = m.group(1).strip()
            lines = []
        else:
            lines.append(line)
    if current is not None:
        result[current] = "\n".join(lines)
    return result


def _parse_csv_line(body: str) -> list[str]:
    """Parse a comma-separated line (e.g. Discovery Keywords section)."""
    text = body.strip()
    if not text:
        return []
    return [item.strip() for item in text.split(",") if item.strip()]


def _parse_list_value(body: str, label: str) -> list[str]:
    """Extract a labeled list value like '- Own: a, b, c' or '- Subreddits: a, b'."""
    for line in body.splitlines():
        line = line.strip().lstrip("-").strip()
        if line.lower().startswith(label.lower() + ":"):
            value = line.split(":", 1)[1].strip()
            return [item.strip() for item in value.split(",") if item.strip()]
    return []


def _parse_monitored_channels(body: str) -> dict[str, dict[str, str]]:
    """Parse the Monitored Channels section.

    Expects ### sub-headings as categories and '- Name (UCxxx)' entries.
    Returns {category: {channel_id: channel_name}}.
    """
    result: dict[str, dict[str, str]] = {}
    current_category: str | None = None
    for line in body.splitlines():
        cat_match = re.match(r"^###\s+(.+)$", line)
        if cat_match:
            current_category = cat_match.group(1).strip()
            result[current_category] = {}
            continue
        if current_category is None:
            continue
        entry_match = re.match(r"^-\s+(.+?)\s+\(([A-Za-z0-9_-]+)\)\s*$", line)
        if entry_match:
            name = entry_match.group(1).strip()
            channel_id = entry_match.group(2).strip()
            result[current_category][channel_id] = name
    return result

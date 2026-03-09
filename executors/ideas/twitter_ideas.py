#!/usr/bin/env python3
"""Fetch top tweets from X.com search for topic discovery.

Uses X.com's internal GraphQL API directly via curl_cffi (Chrome TLS
impersonation). No browser automation needed — just cookies exported
from a logged-in browser session.

Setup (one-time):
    1. /opt/homebrew/bin/python3 -m pip install curl_cffi XClientTransaction
    2. Install "Cookie Editor" Chrome/Firefox extension
    3. Log in to x.com in your regular browser
    4. Click Cookie Editor icon → Export (JSON) → copies to clipboard
    5. Run: pbpaste > ~/.cache/youtube-assistant/twitter_cookies.json

Usage:
    /opt/homebrew/bin/python3 executors/ideas/twitter_ideas.py \
        [--channel-profile memory/channel-profile.md] \
        [--search-terms "personal finance,investing"] \
        [--max-tweets 20] [--max-terms 10] \
        [--output workspace/temp/ideas/<PROJECT>/twitter_data.json]

Depends on: curl_cffi, XClientTransaction, beautifulsoup4
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from datetime import datetime, timezone

_EXECUTORS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _EXECUTORS_DIR not in sys.path:
    sys.path.insert(0, _EXECUTORS_DIR)

import bs4
from curl_cffi import requests as cffi_requests
from x_client_transaction import ClientTransaction
from x_client_transaction.utils import get_ondemand_file_url

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COOKIES_CACHE = os.path.expanduser(
    "~/.cache/youtube-assistant/twitter_cookies.json"
)

BEARER_TOKEN = (
    "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs"
    "=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
)

# GraphQL endpoint hash — extracted from X.com's client JS.
# If search returns 404, this hash may need updating.
SEARCH_TIMELINE_HASH = "z_yqhtrZVEuFEUhYsDyzOg"

SEARCH_FEATURES = {
    "rweb_video_screen_enabled": False,
    "profile_label_improvements_pcf_label_in_post_enabled": True,
    "responsive_web_graphql_exclude_directive_enabled": True,
    "verified_phone_label_enabled": False,
    "responsive_web_graphql_timeline_navigation_enabled": True,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
    "communities_web_enable_tweet_community_results_fetch": True,
    "c9s_tweet_anatomy_moderator_badge_enabled": True,
    "articles_preview_enabled": True,
    "responsive_web_edit_tweet_api_enabled": True,
    "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
    "view_counts_everywhere_api_enabled": True,
    "longform_notetweets_consumption_enabled": True,
    "responsive_web_twitter_article_tweet_consumption_enabled": True,
    "freedom_of_speech_not_reach_fetch_enabled": True,
    "standardized_nudges_misinfo": True,
    "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
    "longform_notetweets_rich_text_read_enabled": True,
    "longform_notetweets_inline_media_enabled": True,
    "responsive_web_enhance_cards_enabled": False,
}

FIELD_TOGGLES = {
    "withArticleRichContentState": True,
    "withArticlePlainText": False,
    "withGrokAnalyze": False,
    "withDisallowedReplyControls": False,
}


COOKIE_SETUP_MSG = """
  ┌─────────────────────────────────────────────────┐
  │  TWITTER COOKIES REQUIRED (one-time setup)      │
  │                                                 │
  │  1. Install "Cookie Editor" extension in your   │
  │     browser (Chrome/Firefox/Edge)               │
  │  2. Go to x.com and log in normally             │
  │  3. Click the Cookie Editor icon → Export (JSON) │
  │     (this copies cookies to your clipboard)     │
  │  4. Run this command in Terminal:               │
  │     pbpaste > ~/.cache/youtube-assistant/       │
  │              twitter_cookies.json               │
  │  5. Re-run this script                          │
  └─────────────────────────────────────────────────┘
"""


# ---------------------------------------------------------------------------
# Cookie management
# ---------------------------------------------------------------------------


def _load_cookies() -> dict[str, str] | None:
    """Load cookies from Cookie Editor JSON export.

    Returns dict of {cookie_name: cookie_value} or None.
    """
    if not os.path.isfile(COOKIES_CACHE):
        return None
    try:
        with open(COOKIES_CACHE) as f:
            raw = json.load(f)

        if not isinstance(raw, list) or len(raw) == 0:
            return None

        cookie_dict = {}
        for c in raw:
            if not isinstance(c, dict):
                continue
            domain = c.get("domain", "")
            if any(d in domain
                   for d in [".x.com", "x.com", ".twitter.com", "twitter.com"]):
                cookie_dict[c["name"]] = c["value"]

        if "auth_token" not in cookie_dict or "ct0" not in cookie_dict:
            print("  WARNING: Missing auth_token or ct0 cookie. "
                  "Re-export cookies from a logged-in browser.",
                  file=sys.stderr)
            return None

        return cookie_dict
    except Exception as e:
        print(f"  Cookie load error: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Transaction ID (anti-bot header)
# ---------------------------------------------------------------------------


def _init_transaction_generator(
    cookie_dict: dict[str, str],
) -> ClientTransaction | None:
    """Initialize the x-client-transaction-id generator.

    Fetches X.com home page + ondemand.s JS file to extract the
    cryptographic components needed for transaction ID generation.
    Returns None on failure (search will still be attempted without it).
    """
    try:
        home_resp = cffi_requests.get(
            "https://x.com",
            cookies=cookie_dict,
            impersonate="chrome131",
            timeout=15,
        )
        if home_resp.status_code != 200:
            return None

        home_soup = bs4.BeautifulSoup(home_resp.content, "html.parser")
        ondemand_url = get_ondemand_file_url(response=home_soup)
        if not ondemand_url:
            return None

        ondemand_resp = cffi_requests.get(
            ondemand_url, impersonate="chrome131", timeout=15
        )
        if ondemand_resp.status_code != 200:
            return None

        return ClientTransaction(
            home_page_response=home_soup,
            ondemand_file_response=ondemand_resp.text,
        )
    except Exception as e:
        print(f"  Transaction ID init failed: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# API search
# ---------------------------------------------------------------------------


def _build_headers(ct0: str) -> dict:
    """Build request headers for X.com GraphQL API."""
    return {
        "authorization": f"Bearer {BEARER_TOKEN}",
        "x-csrf-token": ct0,
        "x-twitter-auth-type": "OAuth2Session",
        "x-twitter-active-user": "yes",
        "x-twitter-client-language": "en",
        "content-type": "application/json",
    }


def search_tweets(
    cookie_dict: dict[str, str],
    query: str,
    max_tweets: int = 30,
    ct_generator: ClientTransaction | None = None,
) -> list[dict]:
    """Search X.com for a query via the GraphQL API."""
    ct0 = cookie_dict["ct0"]
    headers = _build_headers(ct0)

    api_path = (f"/i/api/graphql/"
                f"{SEARCH_TIMELINE_HASH}/SearchTimeline")

    # Add transaction ID if generator is available
    if ct_generator:
        try:
            tx_id = ct_generator.generate_transaction_id(
                method="GET", path=api_path
            )
            headers["x-client-transaction-id"] = tx_id
        except Exception:
            pass

    variables = {
        "rawQuery": query,
        "count": min(max_tweets, 20),
        "querySource": "typed_query",
        "product": "Top",
    }

    url = "https://x.com" + api_path

    resp = cffi_requests.get(
        url,
        params={
            "variables": json.dumps(variables),
            "features": json.dumps(SEARCH_FEATURES),
            "fieldToggles": json.dumps(FIELD_TOGGLES),
        },
        headers=headers,
        cookies=cookie_dict,
        impersonate="chrome131",
        timeout=15,
    )

    if resp.status_code == 429:
        print(f"    Rate limited — waiting 30s", file=sys.stderr)
        time.sleep(30)
        # Regenerate transaction ID for retry
        if ct_generator:
            try:
                tx_id = ct_generator.generate_transaction_id(
                    method="GET", path=api_path
                )
                headers["x-client-transaction-id"] = tx_id
            except Exception:
                pass
        resp = cffi_requests.get(
            url,
            params={
                "variables": json.dumps(variables),
                "features": json.dumps(SEARCH_FEATURES),
                "fieldToggles": json.dumps(FIELD_TOGGLES),
            },
            headers=headers,
            cookies=cookie_dict,
            impersonate="chrome131",
            timeout=15,
        )

    if resp.status_code == 404:
        print(f"    SearchTimeline returned 404 — hash may be outdated "
              f"or transaction ID generation failed",
              file=sys.stderr)
        return []

    if resp.status_code != 200 or not resp.text:
        print(f"    API error: status={resp.status_code}, "
              f"body_len={len(resp.text)}", file=sys.stderr)
        return []

    data = resp.json()
    return _parse_search_response(data, query)


def _parse_search_response(data: dict, search_term: str) -> list[dict]:
    """Parse the SearchTimeline GraphQL response into tweet dicts."""
    tweets = []
    now = datetime.now(timezone.utc)

    try:
        instructions = (
            data["data"]["search_by_raw_query"]["search_timeline"]
            ["timeline"]["instructions"]
        )
    except (KeyError, TypeError):
        return []

    for inst in instructions:
        if inst.get("type") != "TimelineAddEntries":
            continue

        for entry in inst.get("entries", []):
            if "tweet" not in entry.get("entryId", ""):
                continue

            content = entry.get("content", {})
            item = content.get("itemContent", {})
            result = item.get("tweet_results", {}).get("result", {})

            # Handle "tweet" wrapper (for restricted tweets)
            if "tweet" in result and "legacy" not in result:
                result = result["tweet"]

            legacy = result.get("legacy", {})
            if not legacy:
                continue

            user_wrap = (result.get("core", {})
                        .get("user_results", {})
                        .get("result", {}))
            user_core = user_wrap.get("core", {})
            user_legacy = user_wrap.get("legacy", {})

            tweet_id = legacy.get("id_str", "")
            # screen_name moved from legacy to user.core
            handle = (user_core.get("screen_name", "")
                      or user_legacy.get("screen_name", ""))

            # Parse created_at
            created_utc = None
            days_old = None
            created_str = legacy.get("created_at", "")
            if created_str:
                try:
                    dt = datetime.strptime(
                        created_str, "%a %b %d %H:%M:%S %z %Y"
                    )
                    created_utc = int(dt.timestamp())
                    days_old = (now - dt).days
                except (ValueError, TypeError):
                    pass

            tweets.append({
                "tweet_id": tweet_id,
                "text": legacy.get("full_text", "")[:500],
                "author_handle": handle,
                "author_name": (user_core.get("name", "")
                                or user_legacy.get("name", "")),
                "likes": legacy.get("favorite_count", 0),
                "retweets": legacy.get("retweet_count", 0),
                "replies": legacy.get("reply_count", 0),
                "views": _extract_views(result),
                "created_utc": created_utc,
                "days_old": days_old,
                "url": (f"https://x.com/{handle}/status/{tweet_id}"
                        if handle and tweet_id else ""),
                "search_term": search_term,
            })

    return tweets


def _extract_views(result: dict) -> int | None:
    """Extract view count from tweet result."""
    try:
        views_str = (result.get("views", {}).get("count", ""))
        return int(views_str) if views_str else None
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Fetch top tweets from X.com search for topic discovery."
    )
    parser.add_argument("--channel-profile", default=None,
                        help="Path to channel-profile.md "
                             "(reads Community Sources → Twitter search terms)")
    parser.add_argument("--search-terms", default=None,
                        help="Comma-separated search terms (overrides config)")
    parser.add_argument("--max-tweets", type=int, default=30,
                        help="Max tweets per search term (default: 30)")
    parser.add_argument("--max-terms", type=int, default=10,
                        help="Max search terms to query "
                             "(default: 10, randomly sampled if more)")
    parser.add_argument("--output", default=None,
                        help="Output JSON file path "
                             "(optional; always prints to stdout)")
    args = parser.parse_args()

    # Resolve search terms
    search_terms = []
    if args.search_terms:
        search_terms = [t.strip() for t in args.search_terms.split(",")
                        if t.strip()]
    elif args.channel_profile:
        if not os.path.isfile(args.channel_profile):
            print(json.dumps({
                "status": "error",
                "error": f"Channel profile not found: {args.channel_profile}",
            }))
            sys.exit(1)
        from shared.parse_profile import parse_channel_profile
        config = parse_channel_profile(args.channel_profile)
        search_terms = config.get("twitter_search_terms", [])
    else:
        print(json.dumps({
            "status": "error",
            "error": "Provide --search-terms or --channel-profile",
        }))
        sys.exit(1)

    if not search_terms:
        print(json.dumps({
            "status": "error",
            "error": "No search terms specified",
        }))
        sys.exit(1)

    if len(search_terms) > args.max_terms:
        search_terms = random.sample(search_terms, args.max_terms)

    start = time.time()
    all_tweets: list[dict] = []
    errors: list[str] = []

    # Load cookies
    cookie_dict = _load_cookies()
    if not cookie_dict:
        print(COOKIE_SETUP_MSG, file=sys.stderr)
        errors.append(
            "No valid Twitter cookies found. "
            "Export cookies from your browser using Cookie Editor. "
            f"Save to: {COOKIES_CACHE}"
        )
        print(json.dumps({
            "status": "success",
            "search_terms_queried": search_terms,
            "total_tweets": 0,
            "tweets": [],
            "errors": errors,
            "elapsed_seconds": round(time.time() - start, 2),
        }))
        sys.exit(0)

    print(f"  Loaded cookies (auth_token + ct0)", file=sys.stderr)

    # Initialize transaction ID generator (required for SearchTimeline)
    print(f"  Initializing transaction ID generator...", file=sys.stderr)
    ct_generator = _init_transaction_generator(cookie_dict)
    if ct_generator:
        print(f"  Transaction ID generator ready", file=sys.stderr)
    else:
        print(f"  WARNING: Transaction ID init failed — search may "
              f"return 404", file=sys.stderr)

    # Search each term
    for i, term in enumerate(search_terms):
        print(f"  Searching: {term}", file=sys.stderr)
        try:
            tweets = search_tweets(
                cookie_dict, term, args.max_tweets, ct_generator
            )
            all_tweets.extend(tweets)
            print(f"    Found {len(tweets)} tweets", file=sys.stderr)
        except Exception as e:
            err = f"Error for '{term}': {type(e).__name__}: {e}"
            errors.append(err)
            print(f"    {err}", file=sys.stderr)

        # Human-like delay between searches
        if i < len(search_terms) - 1:
            delay = random.uniform(2, 5)
            print(f"  Waiting {delay:.1f}s...", file=sys.stderr)
            time.sleep(delay)

    # Stale session check
    if not all_tweets and not errors:
        errors.append(
            f"No tweets found. Cookies may be stale or account search "
            f"restricted — re-export cookies from browser and save to "
            f"{COOKIES_CACHE}"
        )

    # Deduplicate
    seen_ids: set[str] = set()
    unique_tweets: list[dict] = []
    for tweet in all_tweets:
        tid = tweet.get("tweet_id")
        if tid and tid not in seen_ids:
            seen_ids.add(tid)
            unique_tweets.append(tweet)

    unique_tweets.sort(key=lambda t: t.get("likes", 0), reverse=True)

    elapsed = round(time.time() - start, 2)

    result = {
        "status": "success",
        "search_terms_queried": search_terms,
        "total_tweets": len(unique_tweets),
        "tweets": unique_tweets,
        "errors": errors,
        "elapsed_seconds": elapsed,
    }

    if args.output:
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)
        print(json.dumps({
            "status": "success",
            "output": args.output,
            "total_tweets": len(unique_tweets),
            "search_terms_queried": len(search_terms),
            "elapsed_seconds": elapsed,
        }))
    else:
        print(json.dumps(result))


if __name__ == "__main__":
    main()

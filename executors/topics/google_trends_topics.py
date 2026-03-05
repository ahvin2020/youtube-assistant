#!/usr/bin/env python3
"""Fetch Google Trends data for niche keywords.

Returns interest over time, related queries (rising + top), and trend direction
for each keyword. Uses the pytrends library (unofficial Google Trends API).

Usage:
    python3 executors/topics/google_trends_topics.py \
        [--channel-profile memory/channel-profile.md] \
        [--keywords "personal finance,investing,stock market"] \
        [--region SG] [--timeframe "today 3-m"] \
        [--output workspace/temp/topics/<PROJECT>/trends_data.json]

Depends on: pytrends (pip install pytrends)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

_EXECUTORS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _EXECUTORS_DIR not in sys.path:
    sys.path.insert(0, _EXECUTORS_DIR)


def check_pytrends() -> bool:
    """Check if pytrends is installed."""
    try:
        import pytrends  # noqa: F401
        return True
    except ImportError:
        return False


def fetch_trends(keywords: list[str], region: str, timeframe: str) -> dict:
    """Fetch Google Trends data for keywords.

    Processes keywords in batches of 5 (pytrends limit).
    Returns dict with keyword_trends list and trending_searches list.
    """
    from pytrends.request import TrendReq

    pytrends = TrendReq(hl="en-US", tz=480)  # SGT offset

    keyword_trends: list[dict] = []
    errors: list[str] = []

    # Process in batches of 5 (Google Trends API limit)
    for i in range(0, len(keywords), 5):
        batch = keywords[i:i + 5]

        try:
            pytrends.build_payload(batch, timeframe=timeframe, geo=region)

            # Interest over time
            iot = pytrends.interest_over_time()

            # Related queries
            related = pytrends.related_queries()

            for keyword in batch:
                trend_data = {
                    "keyword": keyword,
                    "avg_interest": 0,
                    "recent_interest": 0,
                    "trend_direction": "stable",
                    "peak_date": None,
                    "peak_value": 0,
                    "related_rising": [],
                    "related_top": [],
                }

                # Parse interest over time
                if not iot.empty and keyword in iot.columns:
                    series = iot[keyword]
                    values = series.tolist()
                    dates = series.index.tolist()

                    if values:
                        trend_data["avg_interest"] = round(sum(values) / len(values), 1)
                        peak_idx = values.index(max(values))
                        trend_data["peak_value"] = int(max(values))
                        trend_data["peak_date"] = str(dates[peak_idx].date())

                        # Calculate trend direction
                        # Compare last 7 data points vs previous 30
                        if len(values) >= 10:
                            recent = values[-7:] if len(values) >= 7 else values[-3:]
                            earlier = values[:-7] if len(values) > 7 else values[:3]
                            recent_avg = sum(recent) / len(recent) if recent else 0
                            earlier_avg = sum(earlier) / len(earlier) if earlier else 1

                            trend_data["recent_interest"] = round(recent_avg, 1)

                            if earlier_avg > 0:
                                ratio = recent_avg / earlier_avg
                                # Check for viral spike
                                if any(v > 2 * earlier_avg for v in recent):
                                    trend_data["trend_direction"] = "viral"
                                elif ratio >= 1.2:
                                    trend_data["trend_direction"] = "rising"
                                elif ratio <= 0.8:
                                    trend_data["trend_direction"] = "declining"
                                else:
                                    trend_data["trend_direction"] = "stable"

                # Parse related queries
                if keyword in related:
                    kw_related = related[keyword]

                    if kw_related.get("rising") is not None and not kw_related["rising"].empty:
                        rising_df = kw_related["rising"].head(10)
                        trend_data["related_rising"] = [
                            {"query": row["query"], "value": str(row["value"])}
                            for _, row in rising_df.iterrows()
                        ]

                    if kw_related.get("top") is not None and not kw_related["top"].empty:
                        top_df = kw_related["top"].head(10)
                        trend_data["related_top"] = [
                            {"query": row["query"], "value": int(row["value"])}
                            for _, row in top_df.iterrows()
                        ]

                keyword_trends.append(trend_data)

        except Exception as e:
            error_msg = f"Batch {batch}: {type(e).__name__}: {e}"
            errors.append(error_msg)
            # Add placeholder entries for failed batch
            for keyword in batch:
                keyword_trends.append({
                    "keyword": keyword,
                    "avg_interest": 0,
                    "recent_interest": 0,
                    "trend_direction": "unknown",
                    "peak_date": None,
                    "peak_value": 0,
                    "related_rising": [],
                    "related_top": [],
                    "error": error_msg,
                })

        # Rate limit between batches
        if i + 5 < len(keywords):
            time.sleep(2)

    # Fetch trending searches for the region
    trending_searches: list[str] = []
    try:
        # Map region code to pytrends country name
        region_map = {
            "SG": "singapore",
            "US": "united_states",
            "GB": "united_kingdom",
            "AU": "australia",
            "CA": "canada",
        }
        country = region_map.get(region, "singapore")
        ts_df = pytrends.trending_searches(pn=country)
        if not ts_df.empty:
            trending_searches = ts_df[0].tolist()[:20]
    except Exception as e:
        errors.append(f"trending_searches: {e}")

    return {
        "keyword_trends": keyword_trends,
        "trending_searches": trending_searches,
        "errors": errors,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Fetch Google Trends data for niche keywords."
    )
    parser.add_argument("--channel-profile", default=None,
                        help="Path to channel-profile.md (reads Discovery Keywords)")
    parser.add_argument("--keywords", default=None,
                        help="Comma-separated keywords (overrides config)")
    parser.add_argument("--region", default="SG",
                        help="Geo region code (default: SG)")
    parser.add_argument("--timeframe", default="today 3-m",
                        help="Pytrends timeframe string (default: 'today 3-m' = 90 days)")
    parser.add_argument("--output", default=None,
                        help="Output JSON file path (optional; always prints to stdout)")
    args = parser.parse_args()

    # Check dependency
    if not check_pytrends():
        print(json.dumps({
            "status": "error",
            "error": "pytrends not found. Install with: pip install pytrends",
        }))
        sys.exit(1)

    # Resolve keywords
    keywords = []
    if args.keywords:
        keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    elif args.channel_profile:
        if not os.path.isfile(args.channel_profile):
            print(json.dumps({"status": "error", "error": f"Channel profile not found: {args.channel_profile}"}))
            sys.exit(1)
        from shared.parse_profile import parse_channel_profile
        config = parse_channel_profile(args.channel_profile)
        keywords = config.get("niche_keywords", [])
    else:
        print(json.dumps({"status": "error", "error": "Provide --keywords or --channel-profile"}))
        sys.exit(1)

    if not keywords:
        print(json.dumps({"status": "error", "error": "No keywords specified"}))
        sys.exit(1)

    start = time.time()

    trends_data = fetch_trends(keywords, args.region, args.timeframe)

    elapsed = round(time.time() - start, 2)

    result = {
        "status": "success",
        "region": args.region,
        "timeframe": args.timeframe,
        "keywords_analyzed": len(keywords),
        "keyword_trends": trends_data["keyword_trends"],
        "trending_searches": trends_data["trending_searches"],
        "errors": trends_data["errors"],
        "elapsed_seconds": elapsed,
    }

    # Write to output file if specified
    if args.output:
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)

    print(json.dumps(result))


if __name__ == "__main__":
    main()

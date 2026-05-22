"""DPRK 360 fixed panorama-site coverage.

DPRK 360 is modeled as a fixed point-list provider, not a tile-based provider:
the public site exposes finite 3DVista tours, but no coverage tiles and no
machine-readable coordinates. The coordinates in the bundled point table are
hand-geocoded public landmark coordinates.

This project stores only the derived coverage raster and the committed public
landmark coordinates. It never downloads or redistributes panorama imagery.
The re-scrape helper reads the public WordPress API and post HTML only; the
observed robots.txt allows `/wp-json/`, `/inside-north-korea/`, and `/360/`.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from coverage_acquisition import polite
from coverage_acquisition.models import BoundingBox, ProviderDefinition, SourceDefinition
from coverage_acquisition.polite import PolitePolicy
from coverage_acquisition.providers._registry import register_provider

USER_AGENT = "global-svi-coverage-observatory/0.3 dprk360-rescrape"
INSIDE_NORTH_KOREA_CATEGORY_ID = 2
WP_POSTS_URL = (
    "https://dprk360.com/wp-json/wp/v2/posts"
    "?per_page=100&_fields=id,slug,link,title,categories"
)
TOUR_SLUG_RE = re.compile(r"(?:https?://)?(?:www\.)?dprk360\.com/360/([A-Za-z0-9_-]+)/?")


@dataclass(frozen=True)
class WordPressPost:
    id: int
    slug: str
    link: str
    title: str
    category_ids: tuple[int, ...]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _points_json_url() -> str:
    return (_repo_root() / "data" / "external" / "dprk360" / "points.json").as_uri()


def extract_tour_slugs(html: str) -> tuple[str, ...]:
    """Extract unique DPRK 360 tour slugs from one WordPress post body."""
    slugs: list[str] = []
    seen: set[str] = set()
    for match in TOUR_SLUG_RE.finditer(html):
        slug = match.group(1).lower()
        if slug in seen:
            continue
        seen.add(slug)
        slugs.append(slug)
    return tuple(slugs)


def parse_inside_north_korea_posts(posts: list[dict]) -> tuple[WordPressPost, ...]:
    """Return WordPress posts in DPRK 360's panorama category."""
    inside_posts: list[WordPressPost] = []
    for post in posts:
        category_ids = tuple(int(category_id) for category_id in post.get("categories", ()))
        if INSIDE_NORTH_KOREA_CATEGORY_ID not in category_ids:
            continue
        title = post.get("title", {})
        inside_posts.append(
            WordPressPost(
                id=int(post["id"]),
                slug=str(post["slug"]),
                link=str(post["link"]),
                title=str(title.get("rendered", "")) if isinstance(title, dict) else str(title),
                category_ids=category_ids,
            )
        )
    return tuple(inside_posts)


def fetch_current_tour_slugs(posts_url: str = WP_POSTS_URL) -> tuple[str, ...]:
    """Fetch the live WordPress inventory and return de-duplicated tour slugs."""
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json,text/html;q=0.9,*/*;q=0.1"}
    policy = PolitePolicy(user_agent=USER_AGENT)
    posts_payload, _, _ = polite.polite_fetch(posts_url, headers=headers, policy=policy)
    posts = parse_inside_north_korea_posts(json.loads(posts_payload.decode("utf-8")))

    slugs: list[str] = []
    seen: set[str] = set()
    for post in posts:
        html_payload, _, _ = polite.polite_fetch(post.link, headers=headers, policy=policy)
        for slug in extract_tour_slugs(html_payload.decode("utf-8", errors="replace")):
            if slug in seen:
                continue
            seen.add(slug)
            slugs.append(slug)
    return tuple(slugs)


PROVIDER = ProviderDefinition(
    key="dprk360",
    output_namespace="dprk360_panorama_points",
    run_label_prefix="dprk360_panorama",
    default_display_zoom=0,
    coordinate_scheme="web_mercator",
    area_presets={
        "pyongyang_pilot_bbox": BoundingBox(
            min_lon=125.68,
            min_lat=38.98,
            max_lon=125.83,
            max_lat=39.08,
        ),
        "dprk360_full_extent_bbox": BoundingBox(
            min_lon=124.0,
            min_lat=37.0,
            max_lon=131.5,
            max_lat=43.5,
        ),
    },
    sources=(
        SourceDefinition(
            id="dprk360_panorama_sites",
            kind="coverage_json",
            template=_points_json_url(),
            headers={
                "User-Agent": "global-svi-coverage-observatory/0.3",
            },
            display_zoom_min=0,
            display_zoom_max=0,
            storage_subdir="coverage_json",
            expect_content_type_prefix="application/json",
            notes=(
                "Fixed hand-geocoded DPRK 360 panorama-site point list. The provider publishes "
                "3DVista tours but no machine-readable coordinates; this source reads the one "
                "committed local coverage JSON file and must run as a single z0 tile job."
            ),
        ),
    ),
)

register_provider(PROVIDER)

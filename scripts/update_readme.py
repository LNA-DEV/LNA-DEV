"""Fill the generated sections of README.md from the feeds of lna-dev.net.

Replaces everything between <!-- POSTS:START --> / <!-- POSTS:END --> with the
latest posts and between <!-- PHOTOS:START --> / <!-- PHOTOS:END --> with a row
of the latest photos. The photos are linked from the website, not copied here,
and sized so the row shares one height without cropping any of them.
"""

import html
import io
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

from PIL import Image

SITE = "https://lna-dev.net"
POSTS_FEED = f"{SITE}/en/posts/index.xml"
PHOTOS_FEED = f"{SITE}/en/gallery/index.xml"

POST_COUNT = 3
PHOTO_COUNT = 4
ROW_WIDTH = 720  # total width of the photo row in px; GitHub's README column is ~830
FEED_VARIANT = "/fit-1600x1600/"
THUMB_VARIANT = "/fit-600x600/"  # the size the website's own grids use

MEDIA_NS = "{http://search.yahoo.com/mrss/}"
USER_AGENT = "LNA-DEV-profile-readme"
README = "README.md"


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def published(item):
    return parsedate_to_datetime(item.findtext("pubDate"))


def feed_items(url):
    """Items of an RSS feed that have a date, newest first."""
    channel = ET.fromstring(fetch(url)).find("channel")
    items = [i for i in channel.findall("item") if i.findtext("pubDate")]
    return sorted(items, key=published, reverse=True)


def posts_markdown():
    lines = []
    for item in feed_items(POSTS_FEED)[:POST_COUNT]:
        title = item.findtext("title").strip()
        link = item.findtext("link").strip()
        lines.append(f"- [{title}]({link}) <sub>{published(item):%b %Y}</sub>")
    return "\n".join(lines)


def latest_photos():
    """The newest photos, at most one per day, so a series doesn't fill the row."""
    photos, days = [], set()
    for item in feed_items(PHOTOS_FEED):
        day = published(item).date()
        if day in days:
            continue
        days.add(day)

        source = item.find(f"{MEDIA_NS}content").get("url").replace(FEED_VARIANT, THUMB_VARIANT)
        width, height = Image.open(io.BytesIO(fetch(source))).size
        img = item.find("description/img")
        title = item.findtext("title").strip()
        photos.append({
            "src": source,
            "link": item.findtext("link").strip(),
            "title": title,
            "alt": (img.get("alt") if img is not None else None) or title,
            "ratio": width / height,
        })
        if len(photos) == PHOTO_COUNT:
            break
    return photos


def photos_markdown():
    photos = latest_photos()
    row_height = ROW_WIDTH / sum(p["ratio"] for p in photos)
    tags = []
    for p in photos:
        tags.append(
            f'<a href="{html.escape(p["link"])}" title="{html.escape(p["title"])}">'
            f'<img src="{html.escape(p["src"])}" width="{round(p["ratio"] * row_height)}" '
            f'alt="{html.escape(p["alt"])}"></a>'
        )
    return '<p align="center">\n' + "\n".join(tags) + "\n</p>"


def replace_section(text, name, content):
    pattern = re.compile(rf"(<!-- {name}:START -->).*?(<!-- {name}:END -->)", re.DOTALL)
    if not pattern.search(text):
        sys.exit(f"README.md has no {name} section")
    return pattern.sub(lambda m: f"{m.group(1)}\n{content}\n{m.group(2)}", text)


def main():
    with open(README, encoding="utf-8") as f:
        text = f.read()
    text = replace_section(text, "POSTS", posts_markdown())
    text = replace_section(text, "PHOTOS", photos_markdown())
    with open(README, "w", encoding="utf-8") as f:
        f.write(text)


if __name__ == "__main__":
    main()

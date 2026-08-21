#!/usr/bin/env python3
"""
Link preview metadata extractor using Open Graph and Twitter Card metadata.
Fetches title, description, image, and other metadata from URLs.
Includes special support for YouTube, Twitter, and other oEmbed services.
"""

import json
import re
import sys
import urllib.error
import urllib.request
from html.parser import HTMLParser
from urllib.parse import quote, urljoin, urlparse


def extract_youtube_id(url):
    """Extract YouTube video ID from various YouTube URL formats."""
    patterns = [
        r"(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})",
        r"youtube\.com\/embed\/([a-zA-Z0-9_-]{11})",
        r"youtube\.com\/v\/([a-zA-Z0-9_-]{11})",
        r"youtube\.com\/shorts\/([a-zA-Z0-9_-]{11})",
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def fetch_youtube_metadata(url, timeout=5):
    """Fetch metadata from YouTube using oEmbed API."""
    video_id = extract_youtube_id(url)
    if not video_id:
        return None

    try:
        # Use YouTube oEmbed API
        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"

        req = urllib.request.Request(oembed_url)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))

        # YouTube oEmbed returns: title, author_name, thumbnail_url, etc.
        # Try to get maxresdefault (1280x720), fall back to hqdefault
        thumbnail = data.get("thumbnail_url", "")
        if "hqdefault" in thumbnail:
            # Try maxresdefault first
            maxres_thumbnail = thumbnail.replace("hqdefault", "maxresdefault")
            # We'll use maxresdefault - if it doesn't exist, YouTube will return hqdefault anyway
            thumbnail = maxres_thumbnail

        return {
            "title": data.get("title", ""),
            "description": f"{data.get('author_name', 'Unknown')}",
            "image": thumbnail,
            "url": url,
            "request_url": url,
            "site_name": "YouTube",
            "type": "video",
            "favicon": "https://www.youtube.com/s/desktop/9c0f82da/img/favicon_144x144.png",
            "author": data.get("author_name", ""),
            "video_id": video_id,
        }
    except Exception as e:
        return None


def fetch_twitter_metadata(url, timeout=5):
    """Fetch metadata from Twitter/X using oEmbed API."""
    try:
        # Twitter oEmbed API
        oembed_url = f"https://publish.twitter.com/oembed?url={quote(url)}"

        req = urllib.request.Request(oembed_url)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))

        return {
            "title": data.get("author_name", "Tweet"),
            "description": re.sub(r"<[^>]+>", "", data.get("html", "")),  # Strip HTML
            "image": "",
            "url": url,
            "request_url": url,
            "site_name": "X (Twitter)",
            "type": "article",
            "favicon": "https://abs.twimg.com/favicons/twitter.3.ico",
            "author": data.get("author_name", ""),
        }
    except Exception as e:
        return None


def is_youtube_url(url):
    """Check if URL is a YouTube URL (hostname based)."""
    try:
        host = urlparse(url).netloc.lower().split(":")[0]
        return host == "youtube.com" or host.endswith(".youtube.com") or host == "youtu.be" or host.endswith(".youtu.be")
    except Exception:
        return False


def is_twitter_url(url):
    """Check if URL is a Twitter/X URL (hostname based)."""
    try:
        host = urlparse(url).netloc.lower().split(":")[0]
        return host == "twitter.com" or host.endswith(".twitter.com") or host == "x.com" or host.endswith(".x.com")
    except Exception:
        return False


# SSRF protection: whitelist and private-range block
def _is_private_ip(host):
    import ipaddress
    import socket
    try:
        # Resolve hostname
        infos = socket.getaddrinfo(host, None)
        for family, _, _, _, sockaddr in infos:
            ip_str = sockaddr[0]
            try:
                ip = ipaddress.ip_address(ip_str)
                if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                    return True
                # Explicit 169.254/16, cg nat etc already covered by private/link_local but double-check
                if ip.is_private:
                    return True
            except ValueError:
                continue
        return False
    except Exception:
        # If resolution fails, don't block (could be DNS failure) — caller will handle
        return False


def _is_allowed_url(url):
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False, "Unsupported scheme"
        if not parsed.hostname:
            return False, "Invalid host"
        # Block private IPs
        if _is_private_ip(parsed.hostname):
            return False, "Private address blocked"
        return True, ""
    except Exception as e:
        return False, str(e)


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Check redirect target
        allowed, reason = _is_allowed_url(newurl)
        if not allowed:
            raise urllib.error.URLError(f"Redirect blocked: {reason} ({newurl})")
        # Limit redirects to 3
        if getattr(self, "_redirect_count", 0) >= 3:
            raise urllib.error.URLError("Too many redirects")
        self._redirect_count = getattr(self, "_redirect_count", 0) + 1
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class MetaTagParser(HTMLParser):
    """Parser to extract meta tags from HTML."""

    def __init__(self):
        super().__init__()
        self.metadata = {
            "title": "",
            "description": "",
            "image": "",
            "url": "",
            "site_name": "",
            "type": "website",
            "favicon": "",
        }
        self.in_title = False
        self.title_text = ""
        # Store all found favicons with their sizes for priority selection
        self.favicon_candidates = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        # Handle title tag
        if tag == "title":
            self.in_title = True

        # Handle link tag for favicon - collect all candidates
        if tag == "link":
            rel = attrs_dict.get("rel", "")
            href = attrs_dict.get("href", "")
            sizes = attrs_dict.get("sizes", "")
            link_type = attrs_dict.get("type", "")

            if rel and href and ("icon" in rel.lower()):
                # Parse size if available (e.g., "96x96", "32x32")
                size = 0
                if sizes and "x" in sizes:
                    try:
                        size = int(sizes.split("x")[0])
                    except ValueError:
                        size = 0

                # Prefer PNG/SVG over ICO
                priority = 0
                if ".svg" in href.lower() or "svg" in link_type.lower():
                    priority = 3  # SVG is scalable, high priority
                elif ".png" in href.lower() or "png" in link_type.lower():
                    priority = 2
                elif ".ico" in href.lower() or "ico" in link_type.lower():
                    priority = 1
                else:
                    priority = 1  # Default for unknown formats

                self.favicon_candidates.append(
                    {"href": href, "size": size, "priority": priority, "rel": rel}
                )

                # Also set immediate favicon for backwards compatibility
                if not self.metadata["favicon"]:
                    self.metadata["favicon"] = href

        # Handle meta tags
        if tag == "meta":
            content = attrs_dict.get("content", "")

            # Open Graph tags
            if "property" in attrs_dict and content:
                prop = attrs_dict["property"]

                if prop == "og:title":
                    self.metadata["title"] = content
                elif prop == "og:description":
                    self.metadata["description"] = content
                elif prop == "og:image":
                    self.metadata["image"] = content
                elif prop == "og:url":
                    self.metadata["url"] = content
                elif prop == "og:site_name":
                    self.metadata["site_name"] = content
                elif prop == "og:type":
                    self.metadata["type"] = content

            # Twitter Card tags (fallback)
            if "name" in attrs_dict and content:
                name = attrs_dict["name"]

                if name == "twitter:title" and not self.metadata["title"]:
                    self.metadata["title"] = content
                elif name == "twitter:description" and not self.metadata["description"]:
                    self.metadata["description"] = content
                elif name == "twitter:image" and not self.metadata["image"]:
                    self.metadata["image"] = content
                elif name == "description" and not self.metadata["description"]:
                    self.metadata["description"] = content

    def handle_data(self, data):
        if self.in_title:
            self.title_text += data

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
            if not self.metadata["title"]:
                self.metadata["title"] = self.title_text.strip()

    def get_best_favicon(self):
        """Select the best favicon from collected candidates."""
        if not self.favicon_candidates:
            return self.metadata["favicon"]

        # Sort by: priority (format) desc, then size desc (prefer larger icons)
        # Prefer sizes around 32-96px for good quality without being too large
        def score(fav):
            size = fav["size"]
            priority = fav["priority"]
            # Prefer sizes between 32 and 128, with 64-96 being ideal
            if 32 <= size <= 128:
                size_score = size
            elif size > 128:
                size_score = 128 - (size - 128) // 10  # Penalize very large
            else:
                size_score = size  # Small or unknown (0)
            return (priority, size_score)

        sorted_favicons = sorted(self.favicon_candidates, key=score, reverse=True)
        return (
            sorted_favicons[0]["href"] if sorted_favicons else self.metadata["favicon"]
        )


def fetch_preview(url, timeout=5):
    """
    Fetch preview metadata for a given URL.

    Args:
        url: The URL to fetch metadata from
        timeout: Request timeout in seconds

    Returns:
        Dictionary with metadata or error information
    """
    try:
        # Validate URL (whitelist + SSRF check)
        allowed, reason = _is_allowed_url(url)
        if not allowed:
            return {"error": reason or "Invalid URL"}
        parsed = urlparse(url)

        # Check for special URL types that have oEmbed support
        if is_youtube_url(url):
            result = fetch_youtube_metadata(url, timeout)
            if result:
                return result
            # If oEmbed fails, fall through to regular scraping

        if is_twitter_url(url):
            result = fetch_twitter_metadata(url, timeout)
            if result:
                return result
            # If oEmbed fails, fall through to regular scraping

        # Create request with headers to mimic a browser
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "identity",
            "Connection": "close",
        }

        req = urllib.request.Request(url, headers=headers)

        # Use opener with redirect validation and limit
        opener = urllib.request.build_opener(_NoRedirectHandler)
        # Fetch the page (redirects validated)
        with opener.open(req, timeout=timeout) as response:
            # Get the final URL after redirects (already validated)
            final_url = response.geturl()
            final_parsed = urlparse(final_url)

            # Only parse HTML content (allow xhtml/xml)
            content_type = response.headers.get("Content-Type", "") or ""
            ct_lower = content_type.lower()
            if not any(t in ct_lower for t in ("text/html", "application/xhtml", "application/xml")):
                return {"error": "Not an HTML page"}

            # Check Content-Length before reading
            clen = response.headers.get("Content-Length")
            if clen:
                try:
                    if int(clen) > 2 * 1024 * 1024:
                        return {"error": "Content too large"}
                except ValueError:
                    pass

            # Read only first 500KB to avoid large downloads
            html = response.read(500 * 1024).decode("utf-8", errors="ignore")

        # Parse the HTML
        parser = MetaTagParser()
        parser.feed(html)

        # Use the final URL after redirects for resolving relative URLs
        base_url = f"{final_parsed.scheme}://{final_parsed.netloc}"
        metadata = parser.metadata

        # Get the best favicon from candidates
        best_favicon = parser.get_best_favicon()
        if best_favicon:
            metadata["favicon"] = best_favicon

        if metadata["image"] and not metadata["image"].startswith(
            ("http://", "https://")
        ):
            metadata["image"] = urljoin(final_url, metadata["image"])

        if metadata["favicon"] and not metadata["favicon"].startswith(
            ("http://", "https://")
        ):
            metadata["favicon"] = urljoin(final_url, metadata["favicon"])
        elif not metadata["favicon"]:
            # Try common favicon locations before falling back to /favicon.ico
            metadata["favicon"] = f"{base_url}/favicon.ico"

        if not metadata["url"]:
            metadata["url"] = url  # Keep original URL, not redirected

        # Always include the request URL for cache keying purposes
        metadata["request_url"] = url

        # Set site name from domain if not present
        if not metadata["site_name"]:
            metadata["site_name"] = final_parsed.netloc

        return metadata

    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}", "url": url, "request_url": url}
    except urllib.error.URLError as e:
        return {
            "error": f"Connection failed: {e.reason}",
            "url": url,
            "request_url": url,
        }
    except Exception as e:
        return {"error": f"Failed to parse: {str(e)}", "url": url, "request_url": url}


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Fetch link preview metadata for Ambxst[+]")
    parser.add_argument("url", help="URL to fetch preview for")
    parser.add_argument("timeout", nargs="?", type=int, default=5,
                        help="Timeout in seconds (default: 5)")
    args = parser.parse_args()

    result = fetch_preview(args.url, args.timeout)
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()

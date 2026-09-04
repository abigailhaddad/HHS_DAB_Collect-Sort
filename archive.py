"""Fetching pages and files through the Internet Archive.

dab.hhs.gov sits behind an Akamai edge block that returns 403 to automated
requests for everything -- index pages, decision files, robots.txt -- whatever
user agent is sent. Both the index collector and the decision fetcher therefore
go through the Archive, and both need the same two things: resolve a URL to a
snapshot, then fetch it.
"""
from __future__ import annotations

import json
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request

AVAIL = "http://archive.org/wayback/available?url="
CDX = ("http://web.archive.org/cdx/search/cdx?output=json&fl=timestamp"
       "&filter=statuscode:200&limit=-1&url=")
UA = {"User-Agent": "hhs-dab-collector (+https://github.com/KMisener90/HHS_DAB_Collect-Sort)"}


def get(url: str, timeout: int = 30, tries: int = 4) -> bytes | None:
    """GET with backoff on transient failures only.

    A 404 is not retried. Retrying it turned every year a division did not
    publish into minutes of backoff against a resource that will never exist.
    Everything else is, because the Archive rate-limits and a single miss reads
    exactly like "this was never archived" -- 2016 ALJ came back empty on one
    run and full of 260 decisions on the next.
    """
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (403, 404, 410) or attempt == tries - 1:
                return None
            time.sleep(2 ** attempt + random.uniform(0, 1))
        except Exception:
            if attempt == tries - 1:
                return None
            time.sleep(2 ** attempt + random.uniform(0, 1))
    return None


def get_text(url: str, **kw) -> str | None:
    body = get(url, **kw)
    return body.decode("utf-8", "ignore") if body is not None else None


def snapshot_url(page_url: str) -> str | None:
    """The newest archived copy of a URL, addressed so it returns the original.

    Two sources, because the availability API returns an empty
    "archived_snapshots" object under load rather than an error, which is
    indistinguishable from "never archived". CDX is slower and does not lie.

    Note the shape of the result. "web/2026id_/<url>" looks like it asks for the
    newest snapshot and instead redirects to the live site -- so the response is
    an HHS 403 page delivered under an archive.org URL, with a 200 status. Only
    an exact timestamp works.
    """
    quoted = urllib.parse.quote(page_url, safe="")

    body = get_text(AVAIL + quoted)
    if body:
        try:
            snap = (json.loads(body).get("archived_snapshots") or {}).get("closest")
        except json.JSONDecodeError:
            snap = None
        if snap:
            # /web/TIMESTAMP/ -> /web/TIMESTAMPid_/ returns the original bytes,
            # not the Archive's page with its own navigation injected.
            return re.sub(r"(/web/\d+)/", r"\1id_/", snap["url"], count=1)

    body = get_text(CDX + quoted)
    if not body or not body.strip():
        return None
    try:
        rows = json.loads(body)
    except json.JSONDecodeError:
        return None
    rows = rows[1:] if rows and rows[0][:1] == ["timestamp"] else rows
    if not rows:
        return None
    return f"http://web.archive.org/web/{rows[-1][0]}id_/{page_url}"

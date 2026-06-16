"""Tiny stdlib HTTP helper with retries and a shared cookie jar.

Stdlib-only on purpose: fewer third-party dependencies = smaller supply-chain
attack surface (a concern for this project).
"""
import http.cookiejar
import ssl
import time
import urllib.request

_UA = "CapitolWatchData/1.0 (+https://github.com/YOUR_GITHUB_USERNAME/capitol-watch-data)"


def make_opener():
    jar = http.cookiejar.CookieJar()
    ctx = ssl.create_default_context()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(jar),
        urllib.request.HTTPSHandler(context=ctx),
    )
    opener.addheaders = [("User-Agent", _UA)]
    return opener


def get(opener, url, *, data=None, headers=None, timeout=60, retries=3, pause=2.0):
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data)
            for k, v in (headers or {}).items():
                req.add_header(k, v)
            with opener.open(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as exc:  # noqa: BLE001 - network, retry on anything
            last = exc
            time.sleep(pause * (attempt + 1))
    raise RuntimeError(f"GET failed after {retries} tries: {url} ({last})")

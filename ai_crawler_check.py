#!/usr/bin/env python3
"""ai-crawler-check: can AI search and training crawlers actually reach your site?

Checks three layers, because each can block AI visibility on its own:
  1. robots.txt rules for each AI crawler token
  2. llms.txt / llms-full.txt presence
  3. live HTTP responses using each crawler's user-agent, compared with a normal
     browser baseline, to catch CDN / WAF / rate-limit blocks that robots.txt can't fix

Standard library only. Python 3.9+.
Usage: python ai_crawler_check.py https://example.com [--path /pricing] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")

# (robots.txt token, purpose, user-agent for a live request or None for robots-only tokens,
#  verified=True when the real bot is IP-verified, so a spoofed request may be refused on purpose)
CRAWLERS = [
    ("GPTBot", "OpenAI model training", "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; GPTBot/1.2; +https://openai.com/gptbot)", False),
    ("OAI-SearchBot", "ChatGPT search results", "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; OAI-SearchBot/1.0; +https://openai.com/searchbot", False),
    ("ChatGPT-User", "ChatGPT browsing on a user's request", "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; ChatGPT-User/1.0; +https://openai.com/bot", False),
    ("ClaudeBot", "Anthropic model training", "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; ClaudeBot/1.0; +claudebot@anthropic.com)", False),
    ("Claude-SearchBot", "Claude search results", "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Claude-SearchBot/1.0; +Claude-SearchBot@anthropic.com)", False),
    ("PerplexityBot", "Perplexity search index", "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)", False),
    ("CCBot", "Common Crawl (feeds many models)", "CCBot/2.0 (https://commoncrawl.org/faq/)", False),
    ("Google-Extended", "Gemini / AI training opt-out token", None, False),
    ("Applebot-Extended", "Apple Intelligence training token", None, False),
    ("Googlebot", "Google Search + AI Overviews", "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)", True),
    ("Bingbot", "Bing + Copilot", "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)", True),
]


@dataclass
class Result:
    bot: str
    purpose: str
    robots_allowed: bool
    http_status: int | None
    verdict: str


def fetch(url: str, ua: str, timeout: float = 15.0) -> tuple[int | None, str]:
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "text/html,*/*;q=0.8"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(200_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except (urllib.error.URLError, TimeoutError, OSError):
        return None, ""


def verdict(robots_ok: bool, status: int | None, baseline: int | None, verified: bool) -> str:
    if not robots_ok:
        return "BLOCKED by robots.txt"
    if status is None:
        return "allowed (robots-only token)" if baseline is not None else "unreachable"
    if 200 <= status < 400:
        return "OK"
    if verified and status in (403, 429):
        return "refused spoofed UA (normal) - confirm in Search Console / Bing Webmaster"
    if baseline is not None and 200 <= baseline < 400:
        return f"BLOCKED at server/CDN ({status}) - robots.txt can't fix this"
    return f"error {status}"


def check(site: str, path: str) -> dict:
    root = f"{urlparse(site).scheme}://{urlparse(site).netloc}/"
    target = urljoin(root, path.lstrip("/"))

    robots_status, robots_txt = fetch(urljoin(root, "robots.txt"), BROWSER_UA)
    rp = RobotFileParser()
    rp.parse(robots_txt.splitlines() if robots_status == 200 else [])
    sitemaps = [l.split(":", 1)[1].strip() for l in robots_txt.splitlines() if l.lower().startswith("sitemap:")]

    llms = {name: fetch(urljoin(root, name), BROWSER_UA)[0] for name in ("llms.txt", "llms-full.txt")}
    baseline, _ = fetch(target, BROWSER_UA)

    results = []
    for token, purpose, ua, verified in CRAWLERS:
        allowed = rp.can_fetch(token, target)
        status = fetch(target, ua)[0] if ua else None
        results.append(Result(token, purpose, allowed, status, verdict(allowed, status, baseline, verified)))
        time.sleep(0.4)  # be polite

    blocked = [r.bot for r in results if r.verdict.startswith("BLOCKED")]
    return {
        "target": target,
        "browser_baseline_status": baseline,
        "robots_txt": robots_status,
        "sitemaps_in_robots": sitemaps,
        "llms_txt": llms["llms.txt"],
        "llms_full_txt": llms["llms-full.txt"],
        "crawlers": [asdict(r) for r in results],
        "blocked": blocked,
    }


def print_report(rep: dict) -> None:
    ok = lambda s: "yes" if s == 200 else f"no ({s})"
    print(f"\nAI crawler check: {rep['target']}")
    print(f"browser baseline: {rep['browser_baseline_status']}   robots.txt: {ok(rep['robots_txt'])}   "
          f"llms.txt: {ok(rep['llms_txt'])}   llms-full.txt: {ok(rep['llms_full_txt'])}")
    print(f"sitemap declared in robots.txt: {'yes' if rep['sitemaps_in_robots'] else 'no'}\n")
    print(f"{'crawler':18} {'purpose':38} {'robots':7} {'http':5} verdict")
    print("-" * 110)
    for c in rep["crawlers"]:
        print(f"{c['bot']:18} {c['purpose']:38} {('allow' if c['robots_allowed'] else 'DENY'):7} "
              f"{str(c['http_status'] or '-'):5} {c['verdict']}")
    if rep["blocked"]:
        print(f"\n{len(rep['blocked'])} crawler(s) blocked: {', '.join(rep['blocked'])}")
        print("Server/CDN blocks usually live in your host's bot-protection or AI-crawler settings, not robots.txt.")
    else:
        print("\nNo AI crawler is blocked.")


def main() -> int:
    ap = argparse.ArgumentParser(description="Check whether AI crawlers can reach a website.")
    ap.add_argument("url", help="site URL, e.g. https://example.com")
    ap.add_argument("--path", default="/", help="page to test (default: /)")
    ap.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = ap.parse_args()
    if not urlparse(args.url).scheme:
        args.url = "https://" + args.url

    rep = check(args.url, args.path)
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print_report(rep)
    return 1 if rep["blocked"] else 0


if __name__ == "__main__":
    sys.exit(main())

# ai-crawler-check

**Can ChatGPT, Claude and Perplexity actually reach your website?** One command tells you.

Most sites check `robots.txt` and stop there. But AI crawlers are often blocked one layer down, by a CDN, firewall or host "bot protection" setting, which robots.txt can't override. Your site then never appears in AI answers, and nothing in your CMS tells you why.

`ai-crawler-check` tests all three layers:

1. **robots.txt**: is each AI crawler allowed?
2. **llms.txt / llms-full.txt**: do you give AI tools a map of your site?
3. **Live responses**: does the server return 200 to each crawler's real user-agent, compared with a normal browser?

No dependencies. Python 3.9+.

## Usage

```bash
python ai_crawler_check.py https://example.com
python ai_crawler_check.py example.com --path /pricing   # test a specific page
python ai_crawler_check.py example.com --json            # machine-readable output
```

Exit code is `1` when any crawler is blocked, so it also works in CI or uptime checks.

## Example output

```
AI crawler check: https://example.com/
browser baseline: 200   robots.txt: yes   llms.txt: yes   llms-full.txt: no (404)
sitemap declared in robots.txt: yes

crawler            purpose                                robots  http  verdict
--------------------------------------------------------------------------------------------------------------
GPTBot             OpenAI model training                  allow   429   BLOCKED at server/CDN (429) - robots.txt can't fix this
OAI-SearchBot      ChatGPT search results                 allow   200   OK
ChatGPT-User       ChatGPT browsing on a user's request   allow   200   OK
ClaudeBot          Anthropic model training               allow   200   OK
Claude-SearchBot   Claude search results                  allow   200   OK
PerplexityBot      Perplexity search index                allow   200   OK
CCBot              Common Crawl (feeds many models)       allow   200   OK
Google-Extended    Gemini / AI training opt-out token     allow   -     allowed (robots-only token)
Applebot-Extended  Apple Intelligence training token      allow   -     allowed (robots-only token)
Googlebot          Google Search + AI Overviews           allow   403   refused spoofed UA (normal) - confirm in Search Console / Bing Webmaster
Bingbot            Bing + Copilot                         allow   403   refused spoofed UA (normal) - confirm in Search Console / Bing Webmaster

1 crawler(s) blocked: GPTBot
```

This is a real result. The site's robots.txt allowed GPTBot, but the host's CDN answered every GPTBot request with `429 Too Many Requests`. The fix was a setting in the hosting panel, not a robots.txt edit.

## Reading the results

| Verdict | Meaning | Where to fix it |
|---|---|---|
| `OK` | The crawler gets your page | Nothing to do |
| `BLOCKED by robots.txt` | Your robots.txt disallows this crawler | robots.txt (only if you want it allowed) |
| `BLOCKED at server/CDN` | The server refuses the crawler while browsers get 200 | Host / CDN / WAF bot-protection or AI-crawler settings |
| `refused spoofed UA (normal)` | Googlebot and Bingbot are verified by IP, so a fake user-agent is refused on purpose | Confirm real access with Google Search Console URL Inspection / Bing Webmaster Tools |
| `allowed (robots-only token)` | `Google-Extended` and `Applebot-Extended` are opt-out tokens, not separate crawlers | robots.txt |

## Limits

- The live test sends each crawler's **user-agent** from your own IP. A host that verifies crawlers by IP range may treat the real bot differently, better or worse. Use it as a strong signal, then confirm with the platform's own tools where they exist.
- It checks one page at a time. Run it on your key templates (home, a product or service page, a blog post).
- Requests are spaced out politely; please don't loop it against sites you don't own.

## Why it matters

AI assistants increasingly answer "who should I hire" and "which product is best" questions directly. If their crawlers can't read your pages, you can't be cited, however good your content is. This is the first check in any GEO (Generative Engine Optimization) audit.

---

Built by [Varun Rajurkar](https://varunrajurkar.in): web developer and SEO/GEO consultant. Need your site found by Google *and* cited by AI? **[See services →](https://varunrajurkar.in/services#geo)**

MIT licensed.

# Third-party software and data

This project is personal, non-commercial research. The code is public on GitHub
for the author's master's applications; nothing is sold, and the dashboard runs
only on the author's own computer. This file lists every third-party package the
project installs and every data source it uses or plans to use.

## Licence rule

Allowed for dependencies: MIT, BSD (including 0BSD), Apache 2.0, ISC, PSF, Zlib,
and the permissive licences NCSA, MIT-0, MIT-CMU, the Unlicense and CC0; OFL for
fonts only; MPL 2.0 for dependencies used unmodified, at runtime or in
development. Not allowed: GPL, AGPL, LGPL, SSPL, non-commercial, research-only or
unknown licences. (Rule set by the author on 2026-11-23 and widened the same day
after the first inventory; also in docs/PROJECT_BRIEF.md.)

## Python packages

Read on 2026-11-23 from the installed package metadata with pip-licenses 5.5.5,
run through uvx so it is not a project dependency:

```sh
uvx pip-licenses --python .venv/bin/python --from mixed --format json
```

"Group" is runtime if the package is needed by the project's runtime
dependencies (from `uv export --no-dev`), otherwise dev. 180 packages, the project
itself excluded (re-read after removing arch).

### Outside the allowed list

None, after the rule was widened on 2026-11-23. The first inventory found seven
packages outside the first rule; the author accepted NCSA, MIT-0, the Unlicense,
MIT-CMU, 0BSD and CC0 as permissive and MPL 2.0 for unmodified dependencies, and
had arch (NCSA, unused) removed. Packages under MPL 2.0, all used unmodified:
certifi (runtime, via curl_cffi, requests and httpx), fqdn (dev, via jupyter)
and hypothesis (dev). peewee's metadata says UNKNOWN, but its bundled LICENSE
file is the MIT text, so it is listed as MIT.

### Full list

| Package | Version | Group | Licence | Status |
|---|---|---|---|---|
| aiofile | 3.12.3 | runtime | Apache-2.0 | allowed |
| alpaca-py | 0.45.0 | runtime | Apache Software License | allowed |
| annotated-doc | 0.0.5 | runtime | MIT | allowed |
| annotated-types | 0.8.0 | runtime | MIT | allowed |
| anyio | 4.16.0 | runtime | MIT | allowed |
| appnope | 1.0.0 | dev | BSD-2-Clause | allowed |
| argon2-cffi | 25.1.0 | dev | MIT | allowed |
| argon2-cffi-bindings | 26.1.0 | dev | MIT | allowed |
| arrow | 1.4.0 | dev | Apache Software License | allowed |
| asttokens | 3.0.2 | dev | Apache 2.0 | allowed |
| async-lru | 2.4.0 | dev | MIT License | allowed |
| attrs | 26.1.0 | runtime | MIT | allowed |
| Authlib | 1.9.4 | runtime | BSD License | allowed |
| babel | 2.18.0 | dev | BSD License | allowed |
| beartype | 0.23.1 | runtime | MIT | allowed |
| beautifulsoup4 | 4.15.0 | runtime | MIT License | allowed |
| bleach | 6.4.0 | dev | Apache Software License | allowed |
| cachetools | 7.2.8 | runtime | MIT | allowed |
| caio | 0.12.10 | runtime | Apache-2.0 | allowed |
| certifi | 2026.10.23 | runtime | Mozilla Public License 2.0 (MPL 2.0) | allowed (MPL 2.0, used unmodified) |
| cffi | 2.1.1 | runtime | MIT-0 | allowed |
| charset-normalizer | 3.5.2 | runtime | MIT | allowed |
| claude-agent-sdk | 0.2.178 | runtime | MIT License | allowed |
| click | 8.5.0 | runtime | BSD-3-Clause | allowed |
| comm | 0.2.3 | dev | BSD License | allowed |
| contourpy | 1.4.0 | runtime | BSD-3-Clause | allowed |
| cryptography | 50.0.2 | runtime | Apache-2.0 OR BSD-3-Clause | allowed |
| curl_cffi | 0.17.0 | runtime | MIT | allowed |
| cycler | 0.12.1 | runtime | BSD License | allowed |
| cyclopts | 5.3.3 | runtime | Apache-2.0 | allowed |
| debugpy | 1.8.22 | dev | MIT License | allowed |
| defusedxml | 0.7.1 | dev | Python Software Foundation License | allowed |
| dnspython | 2.9.2 | runtime | ISC | allowed |
| docstring_parser | 0.18.0 | runtime | MIT License | allowed |
| email-validator | 2.3.0 | runtime | The Unlicense (Unlicense) | allowed |
| exceptiongroup | 1.3.1 | runtime | MIT License | allowed |
| executing | 2.3.0 | dev | MIT License | allowed |
| fastjsonschema | 2.22.3 | dev | BSD License | allowed |
| fastmcp | 4.1.6 | runtime | Apache-2.0 | allowed |
| fastmcp-slim | 4.1.6 | runtime | Apache-2.0 | allowed |
| fonttools | 4.68.0 | runtime | MIT | allowed |
| formulaic | 1.2.2 | runtime | MIT | allowed |
| fqdn | 1.6.0 | dev | MPL-2.0 | allowed (MPL 2.0, used unmodified) |
| griffelib | 2.4.1 | runtime | ISC | allowed |
| h11 | 0.16.0 | runtime | MIT License | allowed |
| httpcore | 1.0.9 | dev | BSD-3-Clause | allowed |
| httpcore2 | 2.16.0 | runtime | BSD-3-Clause | allowed |
| httpx | 0.28.1 | dev | BSD License | allowed |
| httpx2 | 2.16.0 | runtime | BSD-3-Clause | allowed |
| hypothesis | 6.170.14 | dev | MPL-2.0 | allowed (MPL 2.0, used unmodified) |
| idna | 3.20 | runtime | BSD-3-Clause | allowed |
| iniconfig | 2.3.1 | dev | MIT | allowed |
| interface_meta | 2.0.1 | runtime | MIT | allowed |
| ipykernel | 7.4.0 | dev | BSD-3-Clause | allowed |
| ipython | 9.18.1 | dev | BSD-3-Clause | allowed |
| ipython_pygments_lexers | 1.1.1 | dev | BSD License | allowed |
| ipywidgets | 8.1.9 | dev | BSD License | allowed |
| isoduration | 20.11.0 | dev | ISC License (ISCL) | allowed |
| jedi | 0.20.1 | dev | MIT License | allowed |
| Jinja2 | 3.1.6 | dev | BSD License | allowed |
| joserfc | 1.8.0 | runtime | BSD License | allowed |
| json5 | 0.17.3 | dev | Apache-2.0 | allowed |
| jsonpointer | 3.8 | dev | BSD License | allowed |
| jsonref | 1.1.0 | runtime | MIT | allowed |
| jsonschema | 4.26.0 | runtime | MIT | allowed |
| jsonschema-path | 0.5.0 | runtime | Apache Software License | allowed |
| jsonschema-specifications | 2025.9.1 | runtime | MIT | allowed |
| jupyter | 1.1.1 | dev | BSD License | allowed |
| jupyter-console | 6.6.3 | dev | BSD License | allowed |
| jupyter-events | 0.12.1 | dev | BSD License | allowed |
| jupyter-lsp | 2.3.1 | dev | BSD License | allowed |
| jupyter_builder | 1.2.4 | dev | Apache-2.0 AND BSD-2-Clause AND BSD-3-Clause AND ISC AND MIT | allowed |
| jupyter_client | 8.10.0 | dev | BSD License | allowed |
| jupyter_core | 5.9.1 | dev | BSD-3-Clause | allowed |
| jupyter_server | 2.21.1 | dev | BSD License | allowed |
| jupyter_server_terminals | 0.5.4 | dev | BSD License | allowed |
| jupyterlab | 4.6.5 | dev | BSD License | allowed |
| jupyterlab_pygments | 0.3.0 | dev | BSD License | allowed |
| jupyterlab_server | 2.28.1 | dev | BSD License | allowed |
| jupyterlab_widgets | 3.0.17 | dev | BSD License | allowed |
| kiwisolver | 1.5.1 | runtime | BSD License | allowed |
| lark | 1.3.1 | dev | MIT License | allowed |
| lxml | 6.1.3 | runtime | BSD-3-Clause | allowed |
| markdown-it-py | 4.2.0 | runtime | MIT License | allowed |
| MarkupSafe | 3.0.4 | dev | BSD-3-Clause | allowed |
| matplotlib | 3.11.2 | runtime | Python Software Foundation License | allowed |
| matplotlib-inline | 0.2.2 | dev | BSD-3-Clause | allowed |
| mcp | 2.3.0 | runtime | MIT License | allowed |
| mcp-types | 2.3.0 | runtime | MIT License | allowed |
| mdurl | 0.1.2 | runtime | MIT License | allowed |
| mistune | 3.4.0 | dev | BSD License | allowed |
| msgpack | 1.2.4 | runtime | Apache-2.0 | allowed |
| narwhals | 2.28.0 | runtime | MIT | allowed |
| nbclient | 0.11.0 | dev | BSD License | allowed |
| nbconvert | 7.17.2 | dev | BSD License | allowed |
| nbformat | 5.11.1 | dev | BSD License | allowed |
| nbstripout | 0.9.1 | dev | MIT | allowed |
| nest-asyncio2 | 1.7.4 | dev | BSD License | allowed |
| notebook | 7.6.4 | dev | BSD License | allowed |
| notebook_shim | 0.2.4 | dev | BSD License | allowed |
| numpy | 2.5.4 | runtime | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | allowed |
| openapi-pydantic | 0.6.0 | runtime | MIT License | allowed |
| opentelemetry-api | 1.45.2 | runtime | Apache-2.0 | allowed |
| packaging | 26.3 | runtime | Apache-2.0 OR BSD-2-Clause | allowed |
| pandas | 3.1.1 | runtime | BSD-3-Clause | allowed |
| pandocfilters | 1.5.1 | dev | BSD License | allowed |
| parso | 0.8.7 | dev | MIT License | allowed |
| pathable | 0.6.0 | runtime | Apache Software License | allowed |
| patsy | 1.0.3 | runtime | BSD License | allowed |
| peewee | 4.5.3 | runtime | MIT (LICENSE file; package metadata says UNKNOWN) | allowed |
| pexpect | 4.9.0 | dev | ISC License (ISCL) | allowed |
| pillow | 13.0.0 | runtime | MIT-CMU | allowed |
| platformdirs | 4.14.5 | runtime | MIT | allowed |
| pluggy | 1.7.0 | dev | MIT License | allowed |
| prometheus_client | 0.26.0 | dev | Apache-2.0 AND BSD-2-Clause | allowed |
| prompt_toolkit | 3.0.53 | dev | BSD License | allowed |
| protobuf | 7.36.2 | runtime | 3-Clause BSD License | allowed |
| psutil | 7.2.2 | dev | BSD-3-Clause | allowed |
| ptyprocess | 0.7.0 | dev | ISC License (ISCL) | allowed |
| pure_eval | 0.2.4 | dev | MIT License | allowed |
| py-key-value-aio | 0.4.6 | runtime | Apache-2.0 | allowed |
| pyarrow | 26.0.1 | runtime | Apache-2.0 | allowed |
| pycparser | 3.12 | runtime | BSD-3-Clause | allowed |
| pydantic | 2.14.3 | runtime | MIT | allowed |
| pydantic-settings | 2.16.2 | runtime | MIT | allowed |
| pydantic_core | 2.50.4 | runtime | MIT | allowed |
| Pygments | 2.21.0 | runtime | BSD-2-Clause | allowed |
| PyJWT | 2.15.1 | runtime | MIT | allowed |
| pyparsing | 3.3.3 | runtime | MIT | allowed |
| pyperclip | 1.11.0 | runtime | BSD License | allowed |
| pytest | 9.2.0 | dev | MIT | allowed |
| python-dateutil | 4.0.0 | runtime | BSD-3-Clause | allowed |
| python-dotenv | 1.2.4 | runtime | BSD-3-Clause | allowed |
| python-json-logger | 4.2.0 | dev | BSD-2-Clause | allowed |
| python-multipart | 0.0.33 | runtime | Apache-2.0 | allowed |
| pytz | 2026.6 | runtime | MIT License | allowed |
| PyYAML | 6.0.3 | runtime | MIT License | allowed |
| pyzmq | 27.3.0 | dev | BSD-3-Clause | allowed |
| referencing | 0.37.0 | runtime | MIT | allowed |
| requests | 2.34.2 | runtime | Apache Software License | allowed |
| rfc3339-validator | 0.1.4 | dev | MIT License | allowed |
| rfc3986-validator | 0.1.1 | dev | MIT License | allowed |
| rfc3987-syntax | 1.1.0 | dev | MIT | allowed |
| rich | 15.0.0 | runtime | MIT License | allowed |
| rich-rst | 2.2.0 | runtime | MIT | allowed |
| rpds-py | 2026.9.1 | runtime | MIT | allowed |
| ruff | 0.17.3 | dev | MIT | allowed |
| scipy | 1.18.1 | runtime | BSD License | allowed |
| Send2Trash | 2.1.0 | dev | BSD-3-Clause | allowed |
| shellingham | 1.5.4 | runtime | ISC License (ISCL) | allowed |
| six | 1.17.0 | dev | MIT License | allowed |
| sniffio | 1.3.1 | runtime | Apache Software License; MIT License | allowed |
| sortedcontainers | 2.4.0 | dev | Apache Software License | allowed |
| soupsieve | 4.0.1 | runtime | MIT | allowed |
| sse-starlette | 3.6.0 | runtime | BSD-3-Clause | allowed |
| sseclient-py | 1.9.0 | runtime | Apache Software License v2 | allowed |
| stack-data | 0.6.3 | dev | MIT License | allowed |
| starlette | 1.10.0 | runtime | BSD-3-Clause | allowed |
| statsmodels | 0.15.0 | runtime | BSD-3-Clause | allowed |
| terminado | 0.18.1 | dev | BSD License | allowed |
| tinycss2 | 1.5.1 | dev | BSD License | allowed |
| tornado | 6.6 | dev | Apache Software License | allowed |
| traitlets | 5.16.1 | dev | BSD License | allowed |
| truststore | 0.10.5 | runtime | MIT | allowed |
| typer | 0.27.3 | runtime | MIT | allowed |
| typing-inspection | 0.4.5 | runtime | MIT | allowed |
| typing_extensions | 4.16.0 | runtime | PSF-2.0 | allowed |
| tzdata | 2026.6 | runtime | Apache-2.0 | allowed |
| uncalled-for | 0.4.2 | runtime | MIT | allowed |
| uri-template | 1.3.0 | dev | MIT License | allowed |
| urllib3 | 2.8.0 | runtime | MIT | allowed |
| uvicorn | 0.54.0 | runtime | BSD-3-Clause | allowed |
| watchfiles | 1.3.0 | runtime | MIT License | allowed |
| webcolors | 25.10.0 | dev | BSD License | allowed |
| webencodings | 0.6.1 | dev | BSD License | allowed |
| websocket-client | 1.9.2 | dev | Apache-2.0 | allowed |
| websockets | 17.4 | runtime | BSD-3-Clause | allowed |
| widgetsnbextension | 4.0.16 | dev | BSD License | allowed |
| wrapt | 2.5.2 | runtime | BSD-2-Clause | allowed |
| yfinance | 1.8.0 | runtime | Apache Software License | allowed |

## npm packages

None yet. This section will be generated with
`npx license-checker` once the frontend exists (milestone C, commit 4).

## Data sources

Terms pages read on 2026-11-23. Quotes are verbatim from the pages as fetched
that day; "not stated" means the page read does not say it. This is a record of
what the pages say, not legal advice.

How the project uses data, for every source: downloaded data stays on the
author's computer under `data/raw/` and is never committed to git or
redistributed; only a manifest of what was downloaded (source, URL, time,
hashes) is committed. Every source is cited in the README. The dashboard runs
locally and is not published.

| Source | Status in the project | Cost | Terms page read | What the page says on our kind of use | Compliance |
|---|---|---|---|---|---|
| Yahoo Finance, through the yfinance library | used since Phase 2 (12 tickers downloaded once each) | no fee stated as charged; the terms say "We reserve the right to charge fees" (2(k)); no account or payment method used | https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html (version dated May 15, 2025); yfinance README "Legal Stuff" at https://github.com/ranaroussi/yfinance; Yahoo Developer API terms at https://legal.yahoo.com/us/en/yahoo/terms/product-atos/apiforydn/index.html | Section 2(d)(9) prohibits accessing or collecting data "using any automated means" "for any purpose without our express, prior permission". Section 2(e): no access "for any commercial purpose". Section 2(h): "you must not reproduce, modify, rent, lease, sell, trade, distribute". The yfinance README: "the Yahoo! finance API is intended for personal use only". | NEW DOWNLOADS DISABLED (2026-11-23). yfinance is automated access and the terms do not exempt personal research, so the code now refuses every new download. The 12 snapshots taken on 2026-11-08 and 2026-11-10, before the terms were checked, are kept and still read; every result recorded from them stays as it is. |
| SEC EDGAR | planned (Phase 4 to 5) | free: "Anyone can access and download this information for free." | https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data and https://www.sec.gov/privacy | "Current max request rate: 10 requests/second." "Please declare your user agent in request headers". "Information presented on sec.gov is considered public information and may be copied or further distributed". "Please consider appropriate citation to the SEC as the source." "The SEC does not allow botnets or automated tools to crawl the site." | Planned use complies if requests stay well under 10 per second, a User-Agent with a project contact is declared, only needed filings are fetched (no crawling), and the SEC is cited. |
| FRED (Federal Reserve Bank of St. Louis) | planned (macro data) | free for personal use: "You are free to access and use FRED® at no cost for your own personal use"; an API key is required; payment method not stated | https://fred.stlouisfed.org/docs/api/terms_of_use.html and https://fred.stlouisfed.org/legal/ | Use "solely for your personal, non-commercial use". Prohibited: "Store, cache, or archive any portion of the FRED® Services or FRED® Content". The application must show: "This product uses the FRED® API but is not endorsed or certified by the Federal Reserve Bank of St. Louis." Cite the source "and note that it was accessed via FRED". | OPEN. The ban on storing or caching conflicts with the project's snapshot store. Not used yet; to be decided before any FRED download. |
| Kenneth French Data Library | planned (factor returns, Phase 3b) | no price or payment stated; direct file downloads | https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html | Use, redistribution and citation terms: not stated. Footer: "Copyright Eugene F. Fama and Kenneth R. French". The page names its raw data sources (CRSP, MSCI, Bloomberg). | No restriction stated. The project will cite the library and the Fama and French papers and will not redistribute the files. |
| Alpaca (paper trading and free market data) | planned (Phase 6) | Basic plan "Free"; paper trading "does not require real money"; payment method for paper sign-up not stated | https://alpaca.markets/disclosures and https://docs.alpaca.markets/docs/about-market-data-api | Basic plan: historical API "200 / min"; real-time equities from "the IEX exchange" only. The operative terms (Terms and Conditions PDF and the NYSE and NASDAQ market data agreements linked from the disclosures page) could not be read as text on 2026-11-23. | NOT VERIFIED. Read the Terms and Conditions and the market data agreements before Phase 6. |

## Open questions for the author

1. Yahoo Finance. Decided 2026-11-23: new downloads are disabled in code
   (`YFINANCE_DOWNLOADS_ENABLED = False` in `sources/prices.py`); `statarb
   fetch`, `analyse`, `demo`, the backtest commands and the planned dashboard job
   refuse with a message pointing here, before any request is made. The 12
   existing snapshots are kept. The open question is recorded: they were taken
   with an automated tool before the terms were read. A replacement source is
   being evaluated (see the source evaluation below).
2. FRED. The terms prohibit storing or caching FRED content, which the snapshot
   store does by design.
3. Alpaca. The market data terms are unread.

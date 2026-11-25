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
dependencies (from `uv export --no-dev`), otherwise dev. 181 packages, the project
itself excluded (re-read after removing arch; fastapi added on 2026-11-25 for
the dashboard backend, approved in the milestone C plan, with no other new
package).

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
| fastapi | 0.165.0 | runtime | MIT | allowed |
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

Read on 2026-11-25 from `frontend/package-lock.json` (each entry's `license`
field) with `npm run licenses` in `frontend/`, which reads the lock file only;
no licence-checker package was installed. 256 packages: 16 runtime (shipped in
the dashboard bundle or its fonts) and 240 dev (build, type check, lint, tests),
13 of them optional platform builds of lightningcss. `motion` is the current
name of the Framer Motion package (same project and licence).

### Outside the named list

Three dev-only packages, all pulled in by approved tools and none shipped in the
dashboard bundle, have licences that are free and permissive but are not named
in the licence rule. They are kept for now and listed here for the author's
decision:

- BlueOak-1.0.0 (a permissive licence, OSI approved): `minimatch` and
  `@isaacs/nonrecursive-glob-match` (through eslint and typescript-eslint) and
  `graceful-fs` (through `@tailwindcss/vite`).
- CC-BY-4.0 (attribution): `caniuse-lite`, browser-support data used at build
  time (through `eslint-plugin-react-hooks` and Babel's browserslist). It is
  not redistributed: node_modules is not committed and the data is not in the
  bundle.

`argparse` (dev, through `json-schema-to-typescript`) is under the Python
Software Foundation licence (Python-2.0 and PSF-2.0), counted as PSF.
`lightningcss` (dev, through vite and tailwind) is MPL 2.0 and used
unmodified.

### Full list

| Package | Version | Group | Licence | Status |
|---|---|---|---|---|
| @apidevtools/json-schema-ref-parser | 11.9.3 | dev | MIT | allowed |
| @babel/code-frame | 7.29.7 | dev | MIT | allowed |
| @babel/compat-data | 7.29.7 | dev | MIT | allowed |
| @babel/core | 7.29.13 | dev | MIT | allowed |
| @babel/generator | 7.29.15 | dev | MIT | allowed |
| @babel/helper-compilation-targets | 7.29.13 | dev | MIT | allowed |
| @babel/helper-globals | 7.29.7 | dev | MIT | allowed |
| @babel/helper-module-imports | 7.29.7 | dev | MIT | allowed |
| @babel/helper-module-transforms | 7.29.14 | dev | MIT | allowed |
| @babel/helper-string-parser | 7.29.15 | dev | MIT | allowed |
| @babel/helper-validator-identifier | 7.29.7 | dev | MIT | allowed |
| @babel/helper-validator-option | 7.29.7 | dev | MIT | allowed |
| @babel/helpers | 7.29.15 | dev | MIT | allowed |
| @babel/parser | 7.29.15 | dev | MIT | allowed |
| @babel/template | 7.29.7 | dev | MIT | allowed |
| @babel/traverse | 7.29.15 | dev | MIT | allowed |
| @babel/types | 7.29.15 | dev | MIT | allowed |
| @cacheable/memory | 2.2.0 | dev | MIT | allowed |
| @cacheable/utils | 2.5.0 | dev | MIT | allowed |
| @emnapi/core | 1.11.3 | dev (optional) | MIT | allowed |
| @emnapi/core | 2.0.0-beta.2 | dev (optional) | MIT | allowed |
| @emnapi/runtime | 1.11.3 | dev (optional) | MIT | allowed |
| @emnapi/runtime | 2.0.0-beta.2 | dev (optional) | MIT | allowed |
| @emnapi/wasi-threads | 1.2.3 | dev (optional) | MIT | allowed |
| @emnapi/wasi-threads | 2.2.0 | dev (optional) | MIT | allowed |
| @eslint-community/eslint-utils | 4.10.1 | dev | MIT | allowed |
| @eslint-community/regexpp | 4.12.3 | dev | MIT | allowed |
| @eslint/config-array | 0.23.6 | dev | Apache-2.0 | allowed |
| @eslint/config-helpers | 0.7.0 | dev | Apache-2.0 | allowed |
| @eslint/core | 1.2.1 | dev | Apache-2.0 | allowed |
| @eslint/js | 10.0.1 | dev | MIT | allowed |
| @eslint/object-schema | 3.0.5 | dev | Apache-2.0 | allowed |
| @eslint/plugin-kit | 0.7.3 | dev | Apache-2.0 | allowed |
| @fontsource/inter | 5.3.0 | runtime | OFL-1.1 | allowed (OFL, font) |
| @fontsource/jetbrains-mono | 5.3.0 | runtime | OFL-1.1 | allowed (OFL, font) |
| @humanfs/core | 0.19.2 | dev | Apache-2.0 | allowed |
| @humanfs/node | 0.16.8 | dev | Apache-2.0 | allowed |
| @humanfs/types | 0.15.0 | dev | Apache-2.0 | allowed |
| @humanwhocodes/module-importer | 1.0.1 | dev | Apache-2.0 | allowed |
| @humanwhocodes/retry | 0.4.3 | dev | Apache-2.0 | allowed |
| @isaacs/nonrecursive-glob-match | 1.1.0 | dev | BlueOak-1.0.0 | OUTSIDE THE NAMED LIST, pending the author's decision |
| @jridgewell/gen-mapping | 0.3.13 | dev | MIT | allowed |
| @jridgewell/remapping | 2.3.5 | dev | MIT | allowed |
| @jridgewell/resolve-uri | 3.1.3 | dev | MIT | allowed |
| @jridgewell/sourcemap-codec | 1.6.0 | dev | MIT | allowed |
| @jridgewell/trace-mapping | 0.3.31 | dev | MIT | allowed |
| @jsdevtools/ono | 7.1.3 | dev | MIT | allowed |
| @keyv/bigmap | 1.3.1 | dev | MIT | allowed |
| @keyv/serialize | 1.1.1 | dev | MIT | allowed |
| @napi-rs/wasm-runtime | 1.2.2 | dev (optional) | MIT | allowed |
| @napi-rs/wasm-runtime | 1.2.6 | dev (optional) | MIT | allowed |
| @oxc-project/types | 0.156.0 | dev | MIT | allowed |
| @rolldown/binding-android-arm-eabi | 1.2.19 | dev (optional) | MIT | allowed |
| @rolldown/binding-android-arm64 | 1.2.19 | dev (optional) | MIT | allowed |
| @rolldown/binding-darwin-arm64 | 1.2.19 | dev (optional) | MIT | allowed |
| @rolldown/binding-darwin-x64 | 1.2.19 | dev (optional) | MIT | allowed |
| @rolldown/binding-freebsd-x64 | 1.2.19 | dev (optional) | MIT | allowed |
| @rolldown/binding-linux-arm-gnueabihf | 1.2.19 | dev (optional) | MIT | allowed |
| @rolldown/binding-linux-arm64-gnu | 1.2.19 | dev (optional) | MIT | allowed |
| @rolldown/binding-linux-arm64-musl | 1.2.19 | dev (optional) | MIT | allowed |
| @rolldown/binding-linux-ppc64-gnu | 1.2.19 | dev (optional) | MIT | allowed |
| @rolldown/binding-linux-s390x-gnu | 1.2.19 | dev (optional) | MIT | allowed |
| @rolldown/binding-linux-x64-gnu | 1.2.19 | dev (optional) | MIT | allowed |
| @rolldown/binding-linux-x64-musl | 1.2.19 | dev (optional) | MIT | allowed |
| @rolldown/binding-openharmony-arm64 | 1.2.19 | dev (optional) | MIT | allowed |
| @rolldown/binding-wasm32-wasi | 1.2.19 | dev (optional) | MIT | allowed |
| @rolldown/binding-win32-arm64-msvc | 1.2.19 | dev (optional) | MIT | allowed |
| @rolldown/binding-win32-x64-msvc | 1.2.19 | dev (optional) | MIT | allowed |
| @rolldown/pluginutils | 1.1.1 | dev | MIT | allowed |
| @tailwindcss/node | 4.3.5 | dev | MIT | allowed |
| @tailwindcss/oxide | 4.3.5 | dev | MIT | allowed |
| @tailwindcss/oxide-android-arm64 | 4.3.5 | dev (optional) | MIT | allowed |
| @tailwindcss/oxide-darwin-arm64 | 4.3.5 | dev (optional) | MIT | allowed |
| @tailwindcss/oxide-darwin-x64 | 4.3.5 | dev (optional) | MIT | allowed |
| @tailwindcss/oxide-freebsd-x64 | 4.3.5 | dev (optional) | MIT | allowed |
| @tailwindcss/oxide-linux-arm-gnueabihf | 4.3.5 | dev (optional) | MIT | allowed |
| @tailwindcss/oxide-linux-arm64-gnu | 4.3.5 | dev (optional) | MIT | allowed |
| @tailwindcss/oxide-linux-arm64-musl | 4.3.5 | dev (optional) | MIT | allowed |
| @tailwindcss/oxide-linux-x64-gnu | 4.3.5 | dev (optional) | MIT | allowed |
| @tailwindcss/oxide-linux-x64-musl | 4.3.5 | dev (optional) | MIT | allowed |
| @tailwindcss/oxide-wasm32-wasi | 4.3.5 | dev (optional) | MIT | allowed |
| @tailwindcss/oxide-win32-arm64-msvc | 4.3.5 | dev (optional) | MIT | allowed |
| @tailwindcss/oxide-win32-x64-msvc | 4.3.5 | dev (optional) | MIT | allowed |
| @tailwindcss/vite | 4.3.5 | dev | MIT | allowed |
| @tybys/wasm-util | 0.10.3 | dev (optional) | MIT | allowed |
| @tybys/wasm-util | 0.10.5 | dev (optional) | MIT | allowed |
| @types/chai | 5.2.3 | dev | MIT | allowed |
| @types/deep-eql | 4.0.2 | dev | MIT | allowed |
| @types/esrecurse | 4.3.1 | dev | MIT | allowed |
| @types/estree | 1.0.11 | dev | MIT | allowed |
| @types/json-schema | 7.0.15 | dev | MIT | allowed |
| @types/lodash | 4.17.27 | dev | MIT | allowed |
| @types/node | 26.6.10 | dev | MIT | allowed |
| @types/plotly.js | 3.0.15 | dev | MIT | allowed |
| @types/react | 19.3.2 | runtime | MIT | allowed |
| @types/react-dom | 19.3.0 | dev | MIT | allowed |
| @typescript-eslint/eslint-plugin | 8.74.0 | dev | MIT | allowed |
| @typescript-eslint/parser | 8.74.0 | dev | MIT | allowed |
| @typescript-eslint/project-service | 8.74.0 | dev | MIT | allowed |
| @typescript-eslint/scope-manager | 8.74.0 | dev | MIT | allowed |
| @typescript-eslint/tsconfig-utils | 8.74.0 | dev | MIT | allowed |
| @typescript-eslint/type-utils | 8.74.0 | dev | MIT | allowed |
| @typescript-eslint/types | 8.74.0 | dev | MIT | allowed |
| @typescript-eslint/typescript-estree | 8.74.0 | dev | MIT | allowed |
| @typescript-eslint/utils | 8.74.0 | dev | MIT | allowed |
| @typescript-eslint/visitor-keys | 8.74.0 | dev | MIT | allowed |
| @vitejs/plugin-react | 6.3.0 | dev | MIT | allowed |
| @vitest/mocker | 5.1.2 | dev | MIT | allowed |
| @vitest/spy | 5.1.2 | dev | MIT | allowed |
| acorn | 8.19.0 | dev | MIT | allowed |
| acorn-jsx | 5.3.2 | dev | MIT | allowed |
| ajv | 6.15.0 | dev | MIT | allowed |
| argparse | 2.0.1 | dev | Python-2.0 | allowed (PSF licence) |
| argparse | 3.0.4 | dev | PSF-2.0 | allowed (PSF licence) |
| assertion-error | 2.0.1 | dev | MIT | allowed |
| balanced-match | 4.0.4 | dev | MIT | allowed |
| baseline-browser-mapping | 2.11.39 | dev | Apache-2.0 | allowed |
| brace-expansion | 5.1.0 | dev | MIT | allowed |
| browserslist | 4.29.6 | dev | MIT | allowed |
| cacheable | 2.5.0 | dev | MIT | allowed |
| caniuse-lite | 1.0.30001828 | dev | CC-BY-4.0 | OUTSIDE THE NAMED LIST, pending the author's decision |
| chai | 6.3.0 | dev | MIT | allowed |
| commander | 15.1.0 | runtime | MIT | allowed |
| convert-source-map | 2.0.0 | dev | MIT | allowed |
| cross-spawn | 7.0.6 | dev | MIT | allowed |
| csstype | 3.2.4 | runtime | MIT | allowed |
| debug | 4.4.3 | dev | MIT | allowed |
| deep-is | 0.1.4 | dev | MIT | allowed |
| detect-libc | 2.1.2 | dev | Apache-2.0 | allowed |
| electron-to-chromium | 1.5.494 | dev | ISC | allowed |
| enhanced-resolve | 5.27.0 | dev | MIT | allowed |
| es-module-lexer | 2.3.2 | dev | MIT | allowed |
| escalade | 3.2.0 | dev | MIT | allowed |
| escape-string-regexp | 4.0.0 | dev | MIT | allowed |
| eslint | 10.15.0 | dev | MIT | allowed |
| eslint-plugin-react-hooks | 7.1.1 | dev | MIT | allowed |
| eslint-scope | 9.1.2 | dev | BSD-2-Clause | allowed |
| eslint-visitor-keys | 3.4.3 | dev | Apache-2.0 | allowed |
| eslint-visitor-keys | 5.0.1 | dev | Apache-2.0 | allowed |
| espree | 11.2.0 | dev | BSD-2-Clause | allowed |
| esquery | 1.7.0 | dev | BSD-3-Clause | allowed |
| esrecurse | 4.3.0 | dev | BSD-2-Clause | allowed |
| estraverse | 5.3.0 | dev | BSD-2-Clause | allowed |
| estree-walker | 3.0.3 | dev | MIT | allowed |
| esutils | 2.0.3 | dev | BSD-2-Clause | allowed |
| expect-type | 1.4.0 | dev | Apache-2.0 | allowed |
| fast-deep-equal | 3.1.3 | dev | MIT | allowed |
| fast-json-stable-stringify | 2.1.0 | dev | MIT | allowed |
| fast-levenshtein | 2.0.6 | dev | MIT | allowed |
| fdir | 6.5.0 | dev | MIT | allowed |
| file-entry-cache | 11.1.5 | dev | MIT | allowed |
| find-up | 5.0.0 | dev | MIT | allowed |
| flat-cache | 6.1.23 | dev | MIT | allowed |
| flatted | 3.4.4 | dev | ISC | allowed |
| framer-motion | 14.14.0 | runtime | MIT | allowed |
| fsevents | 2.3.3 | dev (optional) | MIT | allowed |
| gensync | 1.0.0-beta.2 | dev | MIT | allowed |
| glob-parent | 6.0.2 | dev | ISC | allowed |
| globals | 17.14.0 | dev | MIT | allowed |
| graceful-fs | 4.2.12 | dev | BlueOak-1.0.0 | OUTSIDE THE NAMED LIST, pending the author's decision |
| hashery | 1.5.1 | dev | MIT | allowed |
| hermes-estree | 0.25.1 | dev | MIT | allowed |
| hermes-parser | 0.25.1 | dev | MIT | allowed |
| hookified | 1.15.1 | dev | MIT | allowed |
| hookified | 2.2.0 | dev | MIT | allowed |
| ignore | 5.3.2 | dev | MIT | allowed |
| ignore | 7.0.17 | dev | MIT | allowed |
| imurmurhash | 0.1.4 | dev | MIT | allowed |
| is-extglob | 2.1.1 | dev | MIT | allowed |
| is-glob | 4.0.3 | dev | MIT | allowed |
| isexe | 2.0.0 | dev | ISC | allowed |
| jiti | 2.7.0 | dev | MIT | allowed |
| js-tokens | 4.0.0 | dev | MIT | allowed |
| js-yaml | 4.3.2 | dev | MIT | allowed |
| js-yaml | 5.5.0 | dev | MIT | allowed |
| jsesc | 3.1.0 | dev | MIT | allowed |
| json-schema-to-typescript | 16.0.0 | dev | MIT | allowed |
| json-schema-traverse | 0.4.1 | dev | MIT | allowed |
| json-stable-stringify-without-jsonify | 1.0.1 | dev | MIT | allowed |
| json5 | 2.2.3 | dev | MIT | allowed |
| katex | 0.19.1 | runtime | MIT | allowed |
| keyv | 5.6.0 | dev | MIT | allowed |
| levn | 0.4.1 | dev | MIT | allowed |
| lightningcss | 1.33.0 | dev | MPL-2.0 | allowed (MPL 2.0, used unmodified) |
| lightningcss-android-arm64 | 1.33.0 | dev (optional) | MPL-2.0 | allowed (MPL 2.0, used unmodified) |
| lightningcss-darwin-arm64 | 1.33.0 | dev (optional) | MPL-2.0 | allowed (MPL 2.0, used unmodified) |
| lightningcss-darwin-x64 | 1.33.0 | dev (optional) | MPL-2.0 | allowed (MPL 2.0, used unmodified) |
| lightningcss-freebsd-x64 | 1.33.0 | dev (optional) | MPL-2.0 | allowed (MPL 2.0, used unmodified) |
| lightningcss-linux-arm-gnueabihf | 1.33.0 | dev (optional) | MPL-2.0 | allowed (MPL 2.0, used unmodified) |
| lightningcss-linux-arm64-gnu | 1.33.0 | dev (optional) | MPL-2.0 | allowed (MPL 2.0, used unmodified) |
| lightningcss-linux-arm64-musl | 1.33.0 | dev (optional) | MPL-2.0 | allowed (MPL 2.0, used unmodified) |
| lightningcss-linux-x64-gnu | 1.33.0 | dev (optional) | MPL-2.0 | allowed (MPL 2.0, used unmodified) |
| lightningcss-linux-x64-musl | 1.33.0 | dev (optional) | MPL-2.0 | allowed (MPL 2.0, used unmodified) |
| lightningcss-win32-arm64-msvc | 1.33.0 | dev (optional) | MPL-2.0 | allowed (MPL 2.0, used unmodified) |
| lightningcss-win32-x64-msvc | 1.33.0 | dev (optional) | MPL-2.0 | allowed (MPL 2.0, used unmodified) |
| locate-path | 6.0.0 | dev | MIT | allowed |
| lodash | 4.18.1 | dev | MIT | allowed |
| lru-cache | 5.1.1 | dev | ISC | allowed |
| lucide-react | 1.80.0 | runtime | ISC | allowed |
| magic-string | 1.4.5 | dev | MIT | allowed |
| minimatch | 11.0.9 | dev | BlueOak-1.0.0 | OUTSIDE THE NAMED LIST, pending the author's decision |
| minimist | 1.2.8 | dev | MIT | allowed |
| motion | 14.14.0 | runtime | MIT | allowed |
| motion-dom | 14.14.0 | runtime | MIT | allowed |
| motion-utils | 14.7.0 | runtime | MIT | allowed |
| ms | 2.1.3 | dev | MIT | allowed |
| nanoid | 3.3.20 | dev | MIT | allowed |
| natural-compare | 1.4.0 | dev | MIT | allowed |
| node-releases | 2.0.65 | dev | MIT | allowed |
| obug | 3.0.0 | dev | MIT | allowed |
| optionator | 0.9.4 | dev | MIT | allowed |
| p-limit | 3.1.0 | dev | MIT | allowed |
| p-locate | 5.0.0 | dev | MIT | allowed |
| path-exists | 4.0.0 | dev | MIT | allowed |
| path-key | 3.1.1 | dev | MIT | allowed |
| picocolors | 1.1.1 | dev | ISC | allowed |
| picomatch | 4.0.7 | dev | MIT | allowed |
| plotly.js-dist-min | 4.3.0 | runtime | MIT | allowed |
| postcss | 8.5.33 | dev | MIT | allowed |
| prelude-ls | 1.2.1 | dev | MIT | allowed |
| prettier | 3.10.1 | dev | MIT | allowed |
| punycode | 2.3.1 | dev | MIT | allowed |
| qified | 0.10.1 | dev | MIT | allowed |
| react | 19.3.1 | runtime | MIT | allowed |
| react-dom | 19.3.1 | runtime | MIT | allowed |
| rolldown | 1.2.19 | dev | MIT | allowed |
| scheduler | 0.28.0 | runtime | MIT | allowed |
| semver | 6.3.2 | dev | ISC | allowed |
| semver | 7.8.6 | dev | ISC | allowed |
| shebang-command | 2.0.0 | dev | MIT | allowed |
| shebang-regex | 3.0.0 | dev | MIT | allowed |
| source-map-js | 1.2.4 | dev | BSD-3-Clause | allowed |
| std-env | 4.3.0 | dev | MIT | allowed |
| tailwindcss | 4.3.5 | dev | MIT | allowed |
| tapable | 2.3.4 | dev | MIT | allowed |
| tinybench | 6.2.5 | dev | MIT | allowed |
| tinyexec | 1.4.0 | dev | MIT | allowed |
| tinyglobby | 0.2.17 | dev | MIT | allowed |
| ts-api-utils | 2.5.0 | dev | MIT | allowed |
| tslib | 2.8.1 | dev (optional) | 0BSD | allowed |
| tslib | 2.9.1 | runtime | 0BSD | allowed |
| type-check | 0.4.0 | dev | MIT | allowed |
| typescript | 6.0.3 | dev | Apache-2.0 | allowed |
| typescript-eslint | 8.74.0 | dev | MIT | allowed |
| undici-types | 8.9.0 | dev | MIT | allowed |
| update-browserslist-db | 1.4.0 | dev | MIT | allowed |
| uri-js | 4.4.1 | dev | BSD-2-Clause | allowed |
| vite | 8.3.8 | dev | MIT | allowed |
| vitest | 5.1.2 | dev | MIT | allowed |
| which | 2.0.2 | dev | ISC | allowed |
| why-is-node-running | 3.2.1 | dev | MIT | allowed |
| word-wrap | 1.2.5 | dev | MIT | allowed |
| yallist | 3.1.1 | dev | ISC | allowed |
| yocto-queue | 0.1.0 | dev | MIT | allowed |
| zod | 4.6.7 | dev | MIT | allowed |
| zod-validation-error | 4.0.2 | dev | MIT | allowed |

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
| CRSP, through WRDS (Wharton Research Data Services) | requested 2026-11-25, not granted | licensed to the university; no payment by the author | not read (access requested through the University of Amsterdam library) | Licensed for academic research; includes delisted stocks, so it removes the survivorship bias of the current data. Terms of the university's licence not read yet. | NOT IN USE. Nothing changes until the author confirms access. If granted, CRSP becomes the research data source, plugged in through the existing source interface in `sources/`, and its licence terms are read and recorded here first. |
| Alpaca (paper trading and free market data) | planned (Phase 6) | Basic plan "Free"; paper trading "does not require real money"; payment method for paper sign-up not stated | https://alpaca.markets/disclosures and https://docs.alpaca.markets/docs/about-market-data-api | Basic plan: historical API "200 / min"; real-time equities from "the IEX exchange" only. The operative terms (Terms and Conditions PDF and the NYSE and NASDAQ market data agreements linked from the disclosures page) could not be read as text on 2026-11-23. | NOT VERIFIED. Read the Terms and Conditions and the market data agreements before Phase 6. |

## Replacement price source: evaluation of 2026-11-23

Requirements: free with no payment method; automated API access permitted;
local storage permitted for personal, non-commercial use; daily history from
2010 or earlier; dividends and splits; workable rate limits. Pages read on
2026-11-23 by a web-reading subagent; no account was created and no data was
downloaded. Quotes are verbatim from its report. "Not read" means the page did
not load (HTTP 403 or 404, an empty page, or a PDF that came back as binary).

| Source | Free, no payment method | API allowed | Local storage | History to 2010 | Dividends and splits | Rate limits (free) | Result |
|---|---|---|---|---|---|---|---|
| Tiingo | free "Starter" plan, but ToS 9.2: "You must provide Company with a valid credit card" "as a condition to signing up for the Services" | yes, ToS 7.3: "All data via the API is for internal consumption only." | no, ToS 1.6(a): "you may not write, save, archive, back up, or otherwise retain Tiingo Data in any persistent or durable storage"; the paid-plan exception is not given "for a Starter Plan" | yes: "30+ Years" | yes: divCash and splitFactor fields | "Max Requests Per Hour 50", "Max Requests Per Day 1000" | fails: card at sign-up and no persistent storage |
| Alpaca market data | Basic plan "$0/mo"; card not stated | docs describe HTTP and WebSocket access; the governing terms (Terms and Conditions, NYSE and NASDAQ agreements) are PDFs that were not read | not stated | no: "Historical data timeframe, Since 2016" | adjusted bars only (split and dividend adjustment); no event fields on the bars endpoint | "200 / min" | fails: history from 2016 |
| EODHD | yes, FAQ: "You do not need a credit card to start a free trial." | yes (API key) | yes: "Non-Professional Users are permitted to store, manipulate, and analyze the data for private, non-commercial purposes." | no: free tier "1 yr" | yes: "Dividends & splits" "Included" | 20 calls a day, 20 a minute | fails: one year of history |
| Alpha Vantage | free key; card not stated | terms not read | not stated | not stated | not stated | "25 API requests per day" | not established |
| Twelve Data | "$0" Basic, "Internal non-display usage" | not stated | not stated | not stated | no: Dividends and Splits "No" on Basic | "8 (800 a day)" | fails: no dividends or splits |
| Marketstack | free | not stated | not stated | no: "1 Year History" | not checked | "100 Requests / mo" | fails: one year of history |
| Polygon.io (Massive) | no free stock tier in the readable pricing text | | | | | | fails: no free tier found |
| Financial Modeling Prep | not read (HTTP 403) | | | | | | not established |
| Nasdaq Data Link | not read (page without content) | | | | | | not established |
| Stooq | not read (page without content) | | | | | | not established |

No source read on 2026-11-23 meets all the requirements. The sources not read
(Financial Modeling Prep, Nasdaq Data Link, Stooq, and Alpha Vantage's terms)
are open.

Decided by the author on 2026-11-25:
- The project stays on the 12 Yahoo snapshots for now, with new downloads off.
- Paid EODHD is rejected: it would need a payment method, which the data and
  service policy forbids.
- The sources whose pages did not load are not retried for now.
- The author is requesting CRSP access through WRDS from the University of
  Amsterdam library (row above). If it is granted, CRSP becomes the research
  data source through the existing source interface. Until the author confirms
  access, nothing changes.
- The dashboard's "any two tickers" flow offers only cached tickers; for any
  other ticker it says that downloads are off pending a licensed data source.
  Its download path stays behind the source interface and the
  `YFINANCE_DOWNLOADS_ENABLED` switch, so a licensed source can be added later
  without changing the dashboard.

## Open questions for the author

1. Yahoo Finance. Decided 2026-11-23: new downloads are disabled in code
   (`YFINANCE_DOWNLOADS_ENABLED = False` in `sources/prices.py`); `statarb
   fetch`, `analyse`, `demo`, the backtest commands and the planned dashboard job
   refuse with a message pointing here, before any request is made. The 12
   existing snapshots are kept. The open question is recorded: they were taken
   with an automated tool before the terms were read. On 2026-11-25 the author
   chose to stay on the snapshots and requested CRSP access through WRDS (see
   the source evaluation above).
2. FRED. The terms prohibit storing or caching FRED content, which the snapshot
   store does by design.
3. Alpaca. The market data terms are unread.

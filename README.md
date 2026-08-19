# codecard

Render a code, log or error snippet as a clean card for a social feed, and
refuse to render the ones that identify your codebase.

![codecard rendering its own leak guard](docs/hero.png)

[![License: MIT](https://img.shields.io/badge/license-MIT-2ea44f.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-3776ab.svg)](pyproject.toml)
[![Tests](https://img.shields.io/badge/tests-171%20passing-2ea44f.svg)](tests)
[![Offline](https://img.shields.io/badge/network-never-777.svg)](#fonts-and-portability)

The image above is codecard rendering the function inside codecard that decides
what codecard will not render. Nothing in `docs/` is a screenshot. Every image
in this README was produced by `python scripts/build_docs_images.py`.

## The problem I actually had

I post engineering artifacts: a migration that fixed a bug, a stack trace a user
saw, the build output before and after. Those snippets come out of real
repositories, and a snippet out of a real repository carries things I never meant
to publish. The package name of a private service. A build path with my username
in it. A hostname that only resolves inside somebody's network. None of that is
visible to me while I am looking at the code, because in the editor it is just
the file. An image is permanent and gets scraped, so being careful once is a
different thing from being careful every time.

The second problem is smaller and constant: pasted screenshots look different
every time. Different editor width, different theme, different zoom, different
crop. A series of posts that should look like one series looks like five people
posting.

So the tool does two things. It typesets a snippet the same way every time, and
it reads the snippet first and stops when the text names a codebase.

**before**, pasted straight out of the editor. Five things on this card identify
a real repository: the package declaration, the private import, an API key, an
internal hostname, and a build path with a username in it.

![before](docs/before.png)

**after**, the same change with those five removed, rendered with the defaults.

![after](docs/after.png)

## Install

```bash
pip install codecard
```

From a checkout:

```bash
git clone https://github.com/dimhold/codecard
cd codecard
pip install -e ".[dev]"
```

Two dependencies, Pillow and PyYAML. No network calls at runtime, no headless
browser, no system font requirements.

## Quickstart

```bash
codecard examples/migration.sql
```

That writes `examples/migration.png` at 1600x900, dark theme, line numbers on,
watermark off. The language comes from the file extension and the card height
follows the content, so a nine line snippet does not sit in a mostly empty
frame.

A few more:

```bash
codecard fix.sql -o fix.png --title "The fix, in full" --highlight 4,5
codecard trace.log --theme ember
git diff | codecard - --lang diff --theme paper -o diff.png
codecard Service.java --check          # run the guard, render nothing
```

Useful flags: `--theme`, `--lang`, `--title`, `--highlight 4,5,9-12`,
`--no-numbers`, `--width/--height`, `--watermark "@you"`, `--guard`,
`--config`, `--list-themes`, `--list-languages`, `--list-rules`,
`--dump-theme NAME`.

## Themes

Three ship with the tool. Nothing about them is tied to a brand and the
watermark is off in all three.

| | |
|---|---|
| `midnight` (default) | ![midnight](docs/theme-midnight.png) |
| `paper` | ![paper](docs/theme-paper.png) |
| `ember` | ![ember](docs/theme-ember.png) |

`ember` exists because a failing build is not the same kind of image as a
migration:

![a failing run](docs/log.png)

### Your own theme

Start from a built-in and change what you want. `extends` pulls in the rest:

```yaml
# my-theme.yaml
extends: midnight

background: "#07131c"
panel:
  color: "#0d1f2b"
  border: "#16313f"
tokens:
  keyword: "#5ec8f2"
  string: "#7fd6a2"
watermark:
  enabled: true
  text: "@your-handle"
```

```bash
codecard examples/migration.sql --theme my-theme.yaml
```

![a custom theme](docs/custom-theme.png)

Every key is optional and anything you leave out keeps its default, so a three
line theme file is a valid theme. To see the full set of keys with their current
values, dump one and edit it:

```bash
codecard --dump-theme midnight > my-theme.yaml
```

The keys, in full: `width`, `height`, `min_height`, `padding`, `background`,
`panel.{color,radius,border,padding}`, `title.{color,size,font,gap}`,
`font.{mono,mono_bold,sans,sans_bold,min_size,max_size,line_spacing}`,
`line_numbers.{enabled,color,width}`,
`tokens.{text,keyword,string,number,comment}`,
`highlight.{background,bar,bar_width}`,
`watermark.{enabled,text,color,size,font,gap}`.

A typo in a theme file is an error rather than a silently ignored key:

```
codecard: unknown theme key 'tokens.keywords', did you mean 'keyword'?
```

Precedence, lowest to highest: built-in defaults, the named theme, the `extends`
chain, your theme file, the theme block in your config file, then explicit
arguments such as `--width` or `--watermark`.

### Config file

Drop a `codecard.yaml` next to your work and codecard picks it up, so the
repeated flags disappear from the command line. `examples/codecard.yaml` is a
commented tour of it. The short version:

```yaml
theme: paper
guard:
  mode: error
  disable: [private-ip]
languages:
  hcl:
    keywords: [resource, variable, module, output]
    line_comment: "#"
defaults:
  lang: text
  line_numbers: true
```

Use `--config path.yaml` to point at one explicitly, or `--no-config` to ignore
whatever is on disk.

## The guard

This is the part I built the tool for. Before anything is drawn, the snippet is
matched against a set of named rules, and by default codecard refuses to render
when one of them fires. It fails closed, because a warning printed at 1am gets
scrolled past and the image is permanent.

```
$ codecard examples/before-leaky.java
codecard: refusing to render, this snippet identifies a codebase
  line 1: package-declaration: package com.acmebank.ledger.settlement;  (a Java or Kotlin package name is your company and product, spelled out)
  line 3: private-import: import com.acmebank.ledger.core.OrderRepository  (an import of a group id nobody publishes is an import of your own code)
  line 8: credential-literal: API_KEY = "sk-live-8f2b1c7d4e9a  (a literal that looks like a credential, whether or not it is a live one)
  line 9: internal-host: https://ledger.acmebank.internal/v2  (internal hostnames map your network for anyone who cares)
  line 12: absolute-path: C:\Users\dmitry\projects\acme-ledger\build\libs\ledger.jar  (build paths carry your username, your employer and your directory layout)
edit the snippet, or pass --guard off if it is genuinely public code
```

Exit code 2, no file written.

The rules, all of which you can list with `codecard --list-rules`:

| rule | what it catches |
|---|---|
| `package-declaration` | `package com.yourcompany.product;` |
| `namespace-declaration` | the C# and PHP equivalent |
| `absolute-path` | `C:\Users\you\...`, `/home/you/...`, `/opt/...` |
| `private-import` | an import of a group id nobody publishes |
| `internal-host` | `*.internal`, `*.local`, `*.corp`, `*.intranet`, `*.lan` |
| `private-ip` | RFC1918 addresses |
| `credential-literal` | `api_key = "..."`, `password: "..."`, `token = "..."` |
| `aws-access-key` | `AKIA...` and `ASIA...` key ids |
| `private-key-block` | `-----BEGIN RSA PRIVATE KEY-----` |
| `jwt` | a token that usually decodes to a real account |
| `connection-string` | `postgres://user:password@host/db` |

This is a seatbelt and not a scanner. It reads the text you are about to publish
and it catches the specific mistakes that show up when you paste from an editor
in a hurry. It does not know what your company is called, it will miss a leak
that looks like ordinary prose, and it says nothing about whether you are
allowed to publish the snippet at all.

### Turning it down

```bash
codecard snippet.java                 # error mode, the default
codecard snippet.java --guard warn    # render, print the findings to stderr
codecard snippet.java --guard off     # render, say nothing
codecard snippet.java --allow-leaks   # same as --guard off
codecard snippet.java --check         # scan and exit, render nothing
```

`--check` is the one to put in a pre-commit hook or CI if you keep your snippets
in a repository.

### Tuning it

Rules are data. In `codecard.yaml`:

```yaml
guard:
  mode: error
  disable: [private-ip]                 # version strings kept tripping it
  only: [credential-literal]            # or run just one rule
  allow:
    - "https://docs\\.example\\.com"    # exempt a match by regex
  rules:
    - name: ticket-id
      pattern: "ACME-[0-9]+"
      why: our tracker ids are not public
```

A rule that does not exist is an error rather than a typo you never notice.

## Python API

```python
from codecard import render_card, render_file, scan, Guard, LeakDetected

result = render_card(
    open("fix.sql").read(),
    lang="sql",
    title="The fix, in full",
    highlight=[4, 5],
    theme="paper",
    output="fix.png",
)
print(result.size, result.font_size, result.line_count)

# a file, with the language taken from the extension
render_file("migration.sql", theme="midnight", output="migration.png")

# the guard on its own, without rendering anything
for finding in scan(open("Service.java").read()):
    print(finding.line, finding.rule, finding.match)

# fail closed in your own pipeline
try:
    render_card(text, lang="java", output="card.png")
except LeakDetected as exc:
    print([f.rule for f in exc.findings])
```

`render_card` returns a `RenderResult` with the Pillow `image`, the resolved
`theme`, `font_size`, `line_count`, `wrapped`, `truncated`, `findings` and the
`path` it saved to. Passing no `output` renders in memory and saves nothing.

Themes and guards are objects too, so a service can build them once:

```python
from codecard import load_theme, Guard

theme = load_theme("my-theme.yaml")
guard = Guard.from_config({"mode": "warn", "disable": ["private-ip"]})
render_card(text, theme=theme, guard=guard, output="card.png")
```

## Languages

`text`, `log`, `python`, `javascript` (with `ts`, `tsx`, `jsx`), `java` (with
`kotlin`, `scala`, `csharp`), `sql`, `go`, `rust`, `shell`, `json`, `yaml`,
`diff`. `codecard --list-languages` prints them with their aliases.

The highlighter is deliberately crude: strings, numbers, keywords, comments, one
line at a time. At 1600 pixels wide a real parser would change almost no pixels,
and being crude is what makes a language five lines of config:

```yaml
languages:
  hcl:
    keywords: [resource, variable, module, output, provider]
    line_comment: "#"
  psql:
    extends: sql
    keywords: [EXPLAIN, ANALYZE, LATERAL, MATERIALIZED]
```

A language you define wins over a built-in of the same name, so you can fix the
`sql` keyword set for your dialect without forking anything.

## Fonts and portability

codecard bundles DejaVu Sans and DejaVu Sans Mono and uses them by default, so
Linux, macOS and Windows produce the same image and a fresh machine needs no
setup. The fonts are unmodified and distributed under the Bitstream Vera and
Arev licenses, which permit redistribution inside a larger package. The full
text is in [`src/codecard/assets/fonts/LICENSE-DejaVu.txt`](src/codecard/assets/fonts/LICENSE-DejaVu.txt)
and applies to those files only.

To use something else:

```yaml
font:
  mono: "JetBrains Mono"                       # a family name, found on this machine
  sans: system                                 # let codecard pick a good one
  mono_bold: "/usr/share/fonts/truetype/x.ttf" # or an exact file
```

A family name that is not installed falls back to the bundled face with a
warning. A file path that does not exist is an error, because a silent fallback
there is how you end up with one card in the wrong font.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

171 tests, no network, no fixtures larger than a string. They cover the
tokenizer, line wrapping and font fitting, theme and config loading with
overrides, the guard (every default rule has a case it must catch and a list of
ordinary code it must leave alone), font resolution and fallback, and the
rendered image itself: size, height following the content, themes changing
pixels, and the CLI exit codes.

To regenerate every image in `docs/`:

```bash
python scripts/build_docs_images.py
```

## License

MIT, Copyright (c) 2026 Dmitriy Semenkevich. See [LICENSE](LICENSE). The bundled
fonts keep their own license, linked above.

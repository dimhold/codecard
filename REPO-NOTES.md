# Repo notes

Notes for publishing this repository. Not part of the package.

## One-line description

Render code, logs and stack traces as clean cards for social feeds, and refuse
to render the ones that leak your codebase.

## Topics

```
python
cli
developer-tools
code-screenshot
syntax-highlighting
image-generation
pillow
social-media
devrel
privacy
security
secret-detection
opsec
themes
```

## Suggested repository settings

- Default branch: `main`
- Description: the one-liner above
- Website: leave empty until there is a docs page
- Releases: tag `v0.1.0` when the PyPI name is claimed
- Issues on, Discussions off, Wiki off, Projects off

## Before the first push

- `pytest` passes on the machine you push from
- `python scripts/build_docs_images.py` regenerates `docs/` without changes
- `pip install -e .` then `codecard --version` works in a clean virtualenv
- the PyPI name `codecard` is available, or `pyproject.toml` gets a new one

## What is deliberately not here

- No telemetry, no network calls at runtime
- No default watermark, and no brand of mine anywhere in the built-in themes
- No bundled theme that assumes a particular editor colour scheme

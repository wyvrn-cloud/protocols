# The protocol site

`https://wyvrn-cloud.github.io/protocols/` -- every protocol in this repo, browsable,
searchable, with its schemas served beside it. Built with [Hugo](https://gohugo.io) and
the [Hextra](https://github.com/imfing/hextra) documentation theme, published by
`.github/workflows/pages.yml` on every merge to `master`.

Nothing is written twice. The readmes under `protocols/`, the `discussions/` and the
root `README.md` are the only sources; `scripts/build_site.py` turns them into Hugo
content at build time (`site/content/` is generated and gitignored):

| Source | Page |
|---|---|
| `protocols/<name>/<version>/readme.md` | `/<name>/<version>/` -- with a header block (PIURI, status, publisher, license, authors) made from the front matter, and the protocol's `schemas/*.json` served at `/<name>/<version>/schemas/<type>.json` |
| `protocols/<name>/` | `/<name>/` -- the protocol's versions |
| `discussions/<slug>.md` | `/discussions/<slug>/` |
| `README.md` | the home page |

Relative links between those files are rewritten to the pages they become; a link to
any other file in the repo becomes a link to it on GitHub.

The paths mirror the PIURIs on purpose: `https://wyvrn.app/chat-message/1.0` and
`https://wyvrn-cloud.github.io/protocols/chat-message/1.0/` differ only in the host, so
pointing `wyvrn.app` at this site would make every PIURI resolve to its own
specification.

## Building it locally

Needs Hugo extended (0.146 or later) and Go (the theme is a Hugo module; `go.mod` and
`go.sum` here pin it).

```sh
python3 scripts/build_site.py      # from the repo root: regenerates site/content/
cd site && hugo server             # http://localhost:1313/protocols/
```

`hugo --gc --minify` in `site/` builds to `site/public/`.

## Customizing

`hugo.yaml` holds the theme settings (menu, search, width, dark mode). Theme overrides
go under `site/layouts/` as Hextra documents; there are none today. The theme is
updated with `hugo mod get -u github.com/imfing/hextra && hugo mod tidy` in `site/`.

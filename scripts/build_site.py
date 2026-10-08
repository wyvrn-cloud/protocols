#!/usr/bin/env python3
"""Generate the Hugo site's content from this repo's own files (see site/README.md).

The protocol readmes, the discussions and the root README stay the only sources;
this script copies them into site/content/ at build time, with:

  - protocols/<name>/<version>/readme.md  ->  site/content/<name>/<version>/index.md
    (a leaf bundle; its schemas/*.json are copied beside it, so relative schema links
    keep working and the site serves them at /<name>/<version>/schemas/<type>.json --
    the same path shape as the PIURI, https://wyvrn.app/<name>/<version>)
  - protocols/<name>/                     ->  site/content/<name>/_index.md (version list)
  - discussions/<slug>.md                 ->  site/content/discussions/<slug>.md
  - README.md                             ->  site/content/_index.md (the home page)

and every relative Markdown link rewritten to the page it lands on, or to the file
on GitHub when it isn't a page. A protocol page also gets a short header block (PIURI,
status, publisher, license, authors) built from its front matter.

Usage: python3 scripts/build_site.py   (writes site/content/, which is gitignored)
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
PROTOCOLS = ROOT / "protocols"
DISCUSSIONS = ROOT / "discussions"
OUT = ROOT / "site" / "content"
GITHUB_BLOB = "https://github.com/wyvrn-cloud/protocols/blob/master/"

FRONT = re.compile(r"\A---\n(.*?)\n---\n", re.S)
LINK = re.compile(r"(!?)\[([^\]]*)\]\(([^)\s]+)(\s+\"[^\"]*\")?\)")
STATUS_ORDER = ["Production", "Implemented", "Demonstrated", "Proposed", "Adopted"]


def split_front(text: str) -> tuple[str, str]:
    m = FRONT.match(text)
    return (m.group(1), text[m.end():]) if m else ("", text)


def yaml_scalar(front: str, key: str) -> str:
    m = re.search(rf"^{key}:\s*(.*)$", front, re.M)
    return m.group(1).strip().strip('"') if m else ""


def yaml_list(front: str, key: str) -> list[str]:
    m = re.search(rf"^{key}:\s*\n((?:[ \t]+-.*\n?)+)", front, re.M)
    if not m:
        inline = yaml_scalar(front, key)
        return [s.strip() for s in inline.strip("[]").split(",") if s.strip()] if inline else []
    return [re.sub(r"^\s*-\s*(name:\s*)?", "", line).strip() for line in m.group(1).splitlines() if line.strip()]


def version_key(v: str) -> tuple[int, ...]:
    return tuple(int(p) if p.isdigit() else 0 for p in v.split("."))


def content_target(repo_path: PurePosixPath) -> str | None:
    """The site-content path (as Hugo's GetPage takes it) a repo file becomes, or None."""
    parts = repo_path.parts
    if len(parts) == 4 and parts[0] == "protocols" and parts[3].lower() == "readme.md":
        return f"/{parts[1]}/{parts[2]}/index.md"
    if len(parts) == 2 and parts[0] == "protocols":
        return f"/{parts[1]}/_index.md"
    if len(parts) == 2 and parts[0] == "discussions" and parts[1].endswith(".md"):
        return f"/discussions/{parts[1]}"
    if parts == ("README.md",):
        return "/_index.md"
    return None


def rewrite_links(body: str, source: Path) -> str:
    """Point every relative link at the page it becomes, the copied schema, or GitHub."""
    source_dir = PurePosixPath(source.relative_to(ROOT).as_posix()).parent

    def repl(m: re.Match) -> str:
        bang, text, dest, title = m.groups()
        title = title or ""
        if dest.startswith(GITHUB_BLOB):  # an absolute link into this repo: a page if it is one
            path, _, fragment = dest[len(GITHUB_BLOB):].partition("#")
            page = content_target(PurePosixPath(path))
            return f"{bang}[{text}]({page}{'#' + fragment if fragment else ''}{title})" if page and not bang else m.group(0)
        if bang or re.match(r"^[a-z][a-z0-9+.-]*:", dest) or dest.startswith("#") or dest.startswith("/"):
            return m.group(0)
        path, _, fragment = dest.partition("#")
        target = PurePosixPath(*[p for p in (source_dir / path).parts])
        normalized: list[str] = []
        for part in target.parts:
            if part == "..":
                if normalized:
                    normalized.pop()
                else:
                    return m.group(0)  # points outside the repo (a sibling checkout): leave it
            elif part != ".":
                normalized.append(part)
        repo_path = PurePosixPath(*normalized)
        page = content_target(repo_path)
        if page:
            new = page + (f"#{fragment}" if fragment else "")
        elif len(repo_path.parts) == 5 and repo_path.parts[3] == "schemas" and source.name.lower() == "readme.md":
            new = dest  # copied beside the page as a bundle resource
        elif (ROOT / repo_path).exists():
            new = GITHUB_BLOB + repo_path.as_posix() + (f"#{fragment}" if fragment else "")
        else:
            return m.group(0)
        return f"{bang}[{text}]({new}{title})"

    return LINK.sub(repl, body)


def protocol_header(front: str) -> str:
    """One line of metadata under the title, then the front matter's summary."""
    parts = [f"`{yaml_scalar(front, 'piuri')}`", f"**{yaml_scalar(front, 'status')}**"]
    for key in ("publisher", "license"):
        if yaml_scalar(front, key):
            parts.append(yaml_scalar(front, key))
    authors = yaml_list(front, "authors")
    if authors and authors != [yaml_scalar(front, "publisher")]:
        parts.append("by " + ", ".join(authors))
    line = " · ".join(parts)
    summary = yaml_scalar(front, "summary")
    return f"{line}\n\n> {summary}\n\n" if summary else f"{line}\n\n"


def write(path: Path, front: dict, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # JSON is valid YAML flow style, and json.dumps quotes everything a summary can contain.
    path.write_text("---\n" + json.dumps(front, ensure_ascii=False) + "\n---\n\n" + body)


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)

    protocols: dict[str, list[dict]] = {}
    for readme in sorted(PROTOCOLS.glob("*/*/readme.md")):
        name, version = readme.parent.parent.name, readme.parent.name
        front, body = split_front(readme.read_text())
        info = {
            "name": name,
            "version": version,
            "title": yaml_scalar(front, "title") or name,
            "piuri": yaml_scalar(front, "piuri"),
            "status": yaml_scalar(front, "status"),
            "summary": yaml_scalar(front, "summary"),
            "tags": yaml_list(front, "tags"),
        }
        protocols.setdefault(name, []).append(info)
        page_dir = OUT / name / version
        write(page_dir / "index.md", {
            "title": f"{info['title']} {version}",
            "linkTitle": version,
            "description": info["summary"],
            "params": {"piuri": info["piuri"], "status": info["status"]},
            "weight": -int("".join(f"{int(p):03d}" for p in version.split("."))),
        }, protocol_header(front) + rewrite_links(body, readme))
        schemas = readme.parent / "schemas"
        if schemas.is_dir():
            shutil.copytree(schemas, page_dir / "schemas")
        for extra in readme.parent.iterdir():  # diagrams and the like, if a protocol ever has them
            if extra.is_file() and extra.name.lower() != "readme.md":
                shutil.copy2(extra, page_dir / extra.name)

    for name, versions in protocols.items():
        versions.sort(key=lambda v: version_key(v["version"]), reverse=True)
        latest = versions[0]
        lines = [f"**{latest['title']}** — {latest['summary']}", "", "| Version | Status | PIURI |", "|---|---|---|"]
        for v in versions:
            lines.append(f"| [{v['version']}](/{name}/{v['version']}/index.md) | {v['status']} | `{v['piuri']}` |")
        write(OUT / name / "_index.md", {"title": latest["title"], "linkTitle": name, "description": latest["summary"], "weight": 10},
              "\n".join(lines) + "\n")

    # Discussions.
    for doc in sorted(DISCUSSIONS.glob("*.md")):
        text = doc.read_text()
        front, body = split_front(text)
        heading = re.search(r"^#\s+(.+)$", body, re.M)
        title = heading.group(1).strip() if heading else doc.stem
        if heading:
            body = body[:heading.start()] + body[heading.end():]
        write(OUT / "discussions" / doc.name, {"title": title}, rewrite_links(body.lstrip("\n"), doc))
    write(OUT / "discussions" / "_index.md",
          {"title": "Discussions", "weight": 1000, "description": "Design notes and open questions behind the protocols."},
          "Design notes and questions that came up while building the protocols, kept with them.\n")

    # Home page: the repo README, minus its H1 (the site title says it), plus a protocol index.
    front, body = split_front((ROOT / "README.md").read_text())
    body = re.sub(r"^#\s+.+\n", "", body, count=1)
    write(OUT / "_index.md", {"title": "wyvrn protocols", "cascade": {"type": "docs"}}, rewrite_links(body, ROOT / "README.md"))

    print(f"{sum(len(v) for v in protocols.values())} protocol pages, {len(list(DISCUSSIONS.glob('*.md')))} discussions -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

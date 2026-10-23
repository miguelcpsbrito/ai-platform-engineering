"""The thin portal (Section 7.3): blueprint execution, a catalog, and the update
machinery — without Backstage. Same templates, same values, same outputs.

    python portal/thin_portal.py new rag-service --name warranty-assistant --tenant cx-warranty \\
        --alias standard --risk-tier 1 --corpus s3://cx-docs/warranty/ --out /tmp/services
    python portal/thin_portal.py update /tmp/services/warranty-assistant --blueprint rag-service
"""
from __future__ import annotations

import argparse
import datetime as dt
import difflib
import fnmatch
import json
import pathlib
import re
import shutil
import sys
import tempfile
import time

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
BLUEPRINTS = ROOT / "blueprints"
CATALOG = pathlib.Path.home() / ".ai-platform" / "catalog.json"
PLACEHOLDER = re.compile(r"\$\{\{\s*values\.(\w+)\s*\}\}")


def template_meta(blueprint: str) -> dict:
    t = yaml.safe_load((BLUEPRINTS / blueprint / "template.yaml").read_text())
    fetch = next(s for s in t["spec"]["steps"] if s["action"] == "fetch:template")
    return {"version": t["metadata"].get("annotations", {}).get("ai-platform/blueprint-version", "0"),
            "required": t["spec"]["parameters"][0]["required"],
            "raw_globs": fetch["input"].get("copyWithoutTemplating", [])}


def render_tree(blueprint: str, values: dict, out: pathlib.Path) -> list[str]:
    meta = template_meta(blueprint)
    missing = [k for k in meta["required"] if k not in values]
    if missing:
        raise SystemExit(f"missing parameters: {missing}")
    src = BLUEPRINTS / blueprint / "skeleton"
    written = []
    for p in sorted(src.rglob("*")):
        if p.is_dir() or "__pycache__" in p.parts:
            continue
        rel = p.relative_to(src).as_posix()
        dest = out / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if any(fnmatch.fnmatch(rel, g) for g in meta["raw_globs"]):
            shutil.copyfile(p, dest)
        else:
            text = p.read_text()
            unknown = set(PLACEHOLDER.findall(text)) - set(values)
            if unknown:
                raise SystemExit(f"{rel}: template uses unknown values {sorted(unknown)}")
            dest.write_text(PLACEHOLDER.sub(lambda m: str(values[m.group(1)]), text))
        written.append(rel)
    (out / ".blueprint.json").write_text(json.dumps({"blueprint": blueprint, "version": meta["version"],
                                                     "values": values}, indent=2))
    return written


def register(entry: dict) -> None:
    CATALOG.parent.mkdir(parents=True, exist_ok=True)
    cat = json.loads(CATALOG.read_text()) if CATALOG.exists() else {}
    cat[entry["name"]] = entry
    CATALOG.write_text(json.dumps(cat, indent=2))


def cmd_new(a) -> pathlib.Path:
    t0 = time.perf_counter()
    values = {"name": a.name, "tenant": a.tenant, "alias": a.alias, "riskTier": str(a.risk_tier),
              "corpus": a.corpus}
    out = pathlib.Path(a.out) / a.name
    if out.exists():
        raise SystemExit(f"{out} exists")
    files = render_tree(a.blueprint, values, out)
    catalog = yaml.safe_load((out / "catalog-info.yaml").read_text())
    register({"name": a.name, "path": str(out), "annotations": catalog["metadata"]["annotations"],
              "created": dt.datetime.now(dt.timezone.utc).isoformat(), "blueprint": a.blueprint})
    print(f"created {out} ({len(files)} files) in {time.perf_counter() - t0:.2f}s; registered in {CATALOG}")
    return out


def cmd_update(a) -> pathlib.Path:
    inst = pathlib.Path(a.instance)
    meta = json.loads((inst / ".blueprint.json").read_text())
    new_version = template_meta(meta["blueprint"])["version"]
    with tempfile.TemporaryDirectory() as td:
        fresh = pathlib.Path(td) / "fresh"
        render_tree(meta["blueprint"], meta["values"], fresh)
        patch = []
        for p in sorted(fresh.rglob("*")):
            if p.is_dir() or p.name == ".blueprint.json":
                continue
            rel = p.relative_to(fresh).as_posix()
            if rel.startswith("src/") and (inst / rel).exists():
                continue          # service code belongs to the team; the template does not overwrite it
            old = (inst / rel).read_text().splitlines(keepends=True) if (inst / rel).exists() else []
            new = p.read_text().splitlines(keepends=True)
            patch.extend(difflib.unified_diff(old, new, f"a/{rel}", f"b/{rel}"))
    out = inst / f"blueprint-update-{meta['version']}-to-{new_version}.patch"
    out.write_text("".join(patch))
    print(f"update {meta['version']} → {new_version}: {out.name} ({sum(1 for l in patch if l.startswith('+++'))} files)")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(prog="thin-portal")
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new")
    n.add_argument("blueprint")
    n.add_argument("--name", required=True)
    n.add_argument("--tenant", required=True)
    n.add_argument("--alias", default="standard", choices=["fast", "standard", "premium"])
    n.add_argument("--risk-tier", type=int, default=1)
    n.add_argument("--corpus", default="s3://example/corpus/")
    n.add_argument("--out", default=".")
    u = sub.add_parser("update")
    u.add_argument("instance")
    a = ap.parse_args(argv)
    return cmd_new(a) if a.cmd == "new" else cmd_update(a)


if __name__ == "__main__":
    main(sys.argv[1:])

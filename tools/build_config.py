"""Compose a generator config from a base example plus overrides.

The "Generate · bag" workflow form can only carry ten inputs, so it starts
from one of the configs/examples/ files and overrides the headline options on
top of it. Keeping the base a real example means the form can never produce a
config that is missing a section.

    python tools/build_config.py --base configs/examples/tote_small.yaml \
        --set body.shape_profile=trapezoidal --set fabric.rows=8 \
        --merge "export: {split_by_part: false}" -o bag.yaml

Values are parsed as YAML, so numbers stay numbers and "[stl, 3mf]" becomes a
list. A --set whose value is empty or "keep" is ignored, which lets the caller
pass every form field without first testing which ones the user filled in.
"""

import argparse
import copy
import sys

import yaml

SKIP_VALUES = {"", "keep"}


def deep_merge(base, over):
    """Merge `over` onto `base`, recursing into nested dicts."""
    out = copy.deepcopy(base)
    for key, value in over.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def apply_set(config, assignment):
    """Apply one `dotted.path=value` assignment in place."""
    if "=" not in assignment:
        raise ValueError(f"--set needs dotted.path=value, got: {assignment!r}")
    path, _, raw = assignment.partition("=")
    path, raw = path.strip(), raw.strip()
    if raw in SKIP_VALUES:
        return False
    node = config
    parts = path.split(".")
    for part in parts[:-1]:
        node = node.setdefault(part, {})
        if not isinstance(node, dict):
            raise ValueError(f"--set {path}: {part} is not a section")
    node[parts[-1]] = yaml.safe_load(raw)
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="config to start from")
    parser.add_argument("--set", action="append", default=[], metavar="PATH=VALUE",
                        help="override one value; empty or 'keep' is ignored")
    parser.add_argument("--merge", default="", metavar="YAML",
                        help="YAML fragment merged last, over everything else")
    parser.add_argument("-o", "--out", required=True, help="where to write the config")
    args = parser.parse_args(argv)

    with open(args.base) as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        parser.error(f"{args.base} is not a mapping")

    applied = [a for a in args.set if apply_set(config, a)]

    fragment = args.merge.strip()
    if fragment:
        extra = yaml.safe_load(fragment)
        if not isinstance(extra, dict):
            parser.error("--merge must be a YAML mapping, e.g. \"fabric: {rows: 8}\"")
        config = deep_merge(config, extra)

    with open(args.out, "w") as handle:
        yaml.safe_dump(config, handle, sort_keys=False, default_flow_style=False)

    print(f"base {args.base} + {len(applied)} override(s)"
          f"{' + merge' if fragment else ''} -> {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

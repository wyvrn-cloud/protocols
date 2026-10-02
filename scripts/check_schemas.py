#!/usr/bin/env python3
"""Check every protocol's shipped JSON Schemas (see README "Schemas").

For each protocols/<name>/<version>/schemas/*.json:
  - it must be a valid JSON Schema 2020-12 document,
  - it must pin its message type with properties.type.const,
  - every example in that protocol's readme.md with that type must validate against it.

Needs: pip install jsonschema json5
"""

import json
import re
import sys
from pathlib import Path

import json5
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent / "protocols"
FENCE = re.compile(r"```[a-zA-Z]*\n(.*?)```", re.S)


def examples(readme):
    for block in FENCE.findall(readme.read_text()):
        try:
            value = json5.loads(block)
        except ValueError:
            continue
        if isinstance(value, dict) and isinstance(value.get("type"), str):
            yield value


def main():
    failures = []
    checked_schemas = checked_examples = 0
    for schema_dir in sorted(ROOT.glob("*/*/schemas")):
        validators = {}
        for path in sorted(schema_dir.glob("*.json")):
            checked_schemas += 1
            name = path.relative_to(ROOT.parent)
            try:
                schema = json.loads(path.read_text())
                Draft202012Validator.check_schema(schema)
            except Exception as e:  # noqa: BLE001 -- report any problem with the file
                failures.append(f"{name}: not a valid JSON Schema 2020-12 document: {e}")
                continue
            message_type = schema.get("properties", {}).get("type", {}).get("const")
            if not isinstance(message_type, str):
                failures.append(f"{name}: no properties.type.const naming its message type")
                continue
            if path.stem != message_type.rsplit("/", 1)[-1]:
                failures.append(f"{name}: file name doesn't match its message type {message_type}")
            validators[message_type] = Draft202012Validator(schema)

        readme = schema_dir.parent / "readme.md"
        for example in examples(readme):
            validator = validators.get(example["type"])
            if validator is None:
                continue
            checked_examples += 1
            for error in validator.iter_errors(example):
                path = "/".join(map(str, error.path)) or "(root)"
                failures.append(f"{readme.relative_to(ROOT.parent)}: example of {example['type']} at {path}: {error.message}")

    print(f"{checked_schemas} schemas, {checked_examples} examples checked")
    for failure in failures:
        print(f"FAIL: {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

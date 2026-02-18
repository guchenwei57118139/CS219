from __future__ import annotations

import yaml
import sys
from pathlib import Path
import re, json, textwrap, os, itertools, math, pandas as pd
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    _DOCX_AVAILABLE = True
except ImportError:
    _DOCX_AVAILABLE = False

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR))
INPUT_FORMAT_PATH = ROOT_DIR / "input_format"
FORMAT_INPUT_PATH_ANNEX_A = Path(__file__).resolve().parent / "input_format" / "input_format.txt"



if FORMAT_INPUT_PATH_ANNEX_A.exists():
    spec_text = FORMAT_INPUT_PATH_ANNEX_A.read_text(encoding="utf-8")
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extract and recursively expand OpenAPI data models for a target operation from a PURE 3GPP text dump
(e.g., section_6_4_6.txt, Annex "A.2 Nnrf_NFManagement API").

Key properties:
- Input is PURE text: parsing is done with regex + indentation heuristics (no YAML libraries).
- Operation is specified via JSON fields: Operation / Paths / Method.
- Extracts:
  - path-level + operation-level parameters (and resolves internal $ref under components/parameters)
  - requestBody schema (resolves internal $ref under components/schemas recursively)
- Builds a STRICT nested JSON "data model" dictionary where leaf nodes are:
  - basic types: int, string, boolean
  - enum
  - or unresolved external refs marked as object_ref + unresolved=true

Usage:
  python extract_nf_op.py --spec /mnt/data/section_6_4_6.txt \
    --op-json '{"Operation":"NFRegister","Paths":"/nf-instances/{nfInstanceId}","Method":"PUT"}'
"""

import argparse
import json
import re
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple, Union

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extract & normalize NRF OpenAPI-like schemas from a PURE text (no real YAML parsing).
This script is tailored to the "section_6_4_6.txt" format you used in thinking.txt:
- Find NFProfile block
- Cut NFProfile precisely before next schema (e.g., "RcfId:")
- Parse schema blocks with regex + state machine
- Transform to a strictly nested JSON-ish model:
  - primitive types: int/string/boolean/number
  - array/map support
  - enum support
  - oneOf/anyOf/allOf as variants
  - internal refs expanded (configurable), external refs marked unresolved

Usage:
  python extract_nrf_datamodel.py \
    --spec /mnt/data/section_6_4_6.txt \
    --operation NFRegister \
    --path "/nf-instances/{nfInstanceId}" \
    --method PUT \
    --out out.json

Notes:
- This script does NOT parse real YAML indentation; it uses regex heuristics only.
- Expansion is intentionally bounded to a curated internal schema set (to avoid exploding output).
"""



# ----------------------------
# IO helpers
# ----------------------------

def read_lines(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read().splitlines()


# ----------------------------
# Schema block extraction (regex + heuristics)
# ----------------------------

def get_schema_block(text_lines: List[str], name: str) -> Optional[Tuple[int, int, List[str]]]:
    """
    Heuristic block extractor from thinking.txt:
    - Find the first line exactly "name:"
    - Keep collecting lines until the next top-level schema definition is detected.
      A "schema def" candidate is:
        * line is at column 0 (strip()==line)
        * endswith ':'
        * not a list item ('- ...')
        * looks like an identifier
        * previous line is blank
        * next few lines include 'description:'
    Returns (start_idx, end_idx_exclusive, block_lines)
    """
    for i, l in enumerate(text_lines):
        if l.strip() == f"{name}:":
            block = [text_lines[i]]
            j = i + 1
            while j < len(text_lines):
                cand = text_lines[j].strip()
                if (
                    cand.endswith(":")
                    and cand == text_lines[j]                      # column 0
                    and not cand.startswith("-")
                    and cand[:-1].replace("_", "").isalnum()
                ):
                    prev_blank = (text_lines[j - 1].strip() == "") if j - 1 >= 0 else False
                    next_has_desc = False
                    for k in range(j + 1, min(j + 4, len(text_lines))):
                        if text_lines[k].strip().startswith("description:"):
                            next_has_desc = True
                            break
                    if prev_blank and next_has_desc and cand != f"{name}:":
                        break
                block.append(text_lines[j])
                j += 1
            return i, j, block
    return None


def slice_nfprofile_block(text_lines: List[str]) -> List[str]:
    """
    You used two-stage logic in thinking.txt:
    1) take a wide slice NFProfile ... before NFService (or other big marker)
    2) then cut NFProfile precisely at "RcfId:" inside that slice

    Here we do it robustly:
    - get_schema_block("NFProfile") to obtain a large-ish block
    - within that block, find "RcfId:" that is a new schema (preceded by blank, followed by description)
    - cut NFProfile block before that line
    """
    got = get_schema_block(text_lines, "NFProfile")
    if not got:
        raise RuntimeError("Cannot find NFProfile: block in spec text.")
    _, _, nfprofile_block = got

    cut_idx = None
    for idx, line in enumerate(nfprofile_block):
        if line.strip() == "RcfId:":
            prev_blank = (idx - 1 >= 0 and nfprofile_block[idx - 1].strip() == "")
            next_is_desc = (idx + 1 < len(nfprofile_block) and nfprofile_block[idx + 1].strip().startswith("description:"))
            if prev_blank and next_is_desc:
                cut_idx = idx
                break

    if cut_idx is not None:
        return nfprofile_block[:cut_idx]
    return nfprofile_block


# ----------------------------
# Schema parser (regex-only state machine)
# ----------------------------

def parse_schema_lines(lines: List[str], schema_name: str) -> Dict[str, Any]:
    """
    Parser derived from thinking.txt (regex + ctx state):
    Supports:
      - root: description/type/required/properties/enum/oneOf/anyOf/allOf
      - properties:
          propName:
            type: ...
            description: ...
            $ref: ...
            items:
              ...
            additionalProperties:
              ...
            enum:
              - ...
    Important:
      - This input is "YAML-like" but may be flattened; we do NOT rely on indentation.
      - We treat lines that match r'[A-Za-z0-9_]+:' as section markers or property names.
    """
    root: Dict[str, Any] = {"name": schema_name}
    current: Dict[str, Any] = root
    ctx = "schema"  # schema | prop | required | enum | enum_prop | items | additionalProperties | anyOf/allOf/oneOf

    def start_new_prop(prop: str) -> None:
        nonlocal current, ctx
        root.setdefault("properties", {})
        root["properties"][prop] = {}
        current = root["properties"][prop]
        ctx = "prop"

    i = 1  # skip first "SchemaName:"
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        # list items
        if line.startswith("- "):
            item = line[2:].strip()
            if ctx == "required":
                root.setdefault("required", []).append(item)
            elif ctx == "enum":
                root.setdefault("enum", []).append(item.strip("'\""))
            elif ctx == "enum_prop":
                current.setdefault("enum", []).append(item.strip("'\""))
            elif ctx in ["allOf", "oneOf", "anyOf"]:
                if item.startswith("$ref:"):
                    ref = item.split(":", 1)[1].strip().strip("'\"")
                    root.setdefault(ctx, []).append({"$ref": ref})
                elif item.startswith("required:"):
                    m = re.search(r"\[(.*?)\]", item)
                    reqs = [s.strip() for s in m.group(1).split(",")] if (m and m.group(1).strip()) else []
                    root.setdefault(ctx, []).append({"required": reqs})
                else:
                    root.setdefault(ctx, []).append(item)
            else:
                # Sometimes required list items appear without switching ctx properly; keep a safe fallback.
                if "required" in root and isinstance(root["required"], list) and item and not item.startswith("$ref:"):
                    root["required"].append(item)
            i += 1
            continue

        # section marker or new property: "Key:"
        if re.fullmatch(r"[A-Za-z0-9_]+:", line):
            key = line[:-1]
            if key in [
                "description", "type", "required", "properties", "items", "additionalProperties",
                "anyOf", "allOf", "oneOf", "enum", "not",
                "minItems", "maxItems", "minimum", "maximum", "format", "pattern", "default",
                "minProperties", "maxProperties"
            ]:
                if key == "required":
                    root["required"] = []
                    ctx = "required"
                elif key == "properties":
                    root.setdefault("properties", {})
                    ctx = "properties"
                elif key in ["anyOf", "allOf", "oneOf"]:
                    root.setdefault(key, [])
                    ctx = key
                elif key == "enum":
                    if ctx == "prop":
                        current.setdefault("enum", [])
                        ctx = "enum_prop"
                    else:
                        root.setdefault("enum", [])
                        ctx = "enum"
                elif key == "items":
                    if ctx == "prop":
                        current["items"] = {}
                        current = current["items"]
                        ctx = "items"
                elif key == "additionalProperties":
                    if ctx == "prop":
                        current["additionalProperties"] = {}
                        current = current["additionalProperties"]
                        ctx = "additionalProperties"
                else:
                    # other markers ignored as standalone sections
                    pass
            else:
                # treat as a new property name
                start_new_prop(key)
            i += 1
            continue

        # key: value
        if ":" in line:
            k, v = line.split(":", 1)
            k = k.strip()
            v = v.strip()

            # where to write
            target = current if ctx in ["prop", "items", "additionalProperties", "enum_prop"] else root

            if k == "$ref":
                target["$ref"] = v.strip("'\"")
            elif k in ["description", "type", "format", "default", "pattern"]:
                target[k] = v.strip("'\"")
            elif k in ["minimum", "maximum", "minItems", "maxItems", "minProperties", "maxProperties"]:
                try:
                    target[k] = int(v)
                except ValueError:
                    target[k] = v
            else:
                target[k] = v.strip("'\"")

        i += 1

    return root


# ----------------------------
# Transform to your nested JSON model + bounded recursive expansion
# ----------------------------

def simplify_type(t: Optional[str]) -> str:
    if t is None:
        return "object"
    if t in ["integer", "int"]:
        return "int"
    if t in ["boolean", "bool"]:
        return "boolean"
    if t == "string":
        return "string"
    if t == "number":
        return "number"
    return t


def ref_name_from_ref(ref: str) -> str:
    # "#/components/schemas/NFStatus" or "TS29571_CommonData.yaml#/components/schemas/NfInstanceId"
    if "#/components/schemas/" in ref:
        return ref.split("#/components/schemas/", 1)[1]
    if "/components/schemas/" in ref:
        return ref.split("/components/schemas/", 1)[1]
    return ref


def build_model(
    schemas: Dict[str, Dict[str, Any]],
    internal_expand: Set[str],
    root_schema_names: List[str],
) -> Dict[str, Any]:
    def transform_ref(ref: str, visited: Set[str]) -> Dict[str, Any]:
        nm = ref_name_from_ref(ref)
        if nm in internal_expand and nm not in visited and nm in schemas:
            return transform_schema(nm, visited)
        return {"type": "object_ref", "ref_name": nm, "unresolved": True}

    def transform_schema(name: str, visited: Optional[Set[str]] = None) -> Dict[str, Any]:
        if visited is None:
            visited = set()
        visited = set(visited) | {name}

        s = schemas[name]
        out: Dict[str, Any] = {"name": name}

        # enum-like schema (sometimes type omitted)
        if "enum" in s and s.get("type") is None:
            opts = [o for o in s["enum"] if ":" not in o]
            out.update(
                {
                    "type": "enum",
                    "description": s.get("description", ""),
                    "options": opts,
                }
            )
            return out

        # oneOf/anyOf/allOf without properties => treat as combinator
        for comb in ["oneOf", "anyOf", "allOf"]:
            if comb in s and "properties" not in s and s.get("type") is None:
                out["type"] = comb
                out["description"] = s.get("description", "")
                variants = []
                for entry in s[comb]:
                    if isinstance(entry, dict) and "$ref" in entry:
                        variants.append(transform_ref(entry["$ref"], visited))
                    else:
                        variants.append(entry)
                out["variants"] = variants
                return out

        out["type"] = s.get("type", "object")
        if "description" in s:
            out["description"] = s["description"]

        required = set(s.get("required", []))
        fields: Dict[str, Any] = {}

        for prop, ps in s.get("properties", {}).items():
            f: Dict[str, Any] = {"mandatory": prop in required}
            if "description" in ps:
                f["description"] = ps["description"]

            # $ref
            if "$ref" in ps:
                f.update(transform_ref(ps["$ref"], visited))
                fields[prop] = f
                continue

            t = ps.get("type")

            # array
            if t == "array":
                f["type"] = "array"
                items = ps.get("items", {})
                if "$ref" in items:
                    f["items"] = transform_ref(items["$ref"], visited)
                else:
                    f["items"] = {"type": simplify_type(items.get("type", "string"))}
                if "minItems" in ps:
                    f["minItems"] = ps["minItems"]
                if "maxItems" in ps:
                    f["maxItems"] = ps["maxItems"]

            # map (object + additionalProperties)
            elif t == "object" and "additionalProperties" in ps:
                f["type"] = "map"
                ap = ps["additionalProperties"]
                if "$ref" in ap:
                    f["additionalProperties"] = transform_ref(ap["$ref"], visited)
                else:
                    f["additionalProperties"] = {"type": simplify_type(ap.get("type", "string"))}
                if "minProperties" in ps:
                    f["minProperties"] = ps["minProperties"]
                if "maxProperties" in ps:
                    f["maxProperties"] = ps["maxProperties"]

            # enum at property level
            elif "enum" in ps:
                f["type"] = "enum"
                f["options"] = [o for o in ps["enum"] if ":" not in o]

            # primitive/object
            else:
                f["type"] = simplify_type(t)

            # range/constraints
            if "minimum" in ps or "maximum" in ps:
                f["range"] = [ps.get("minimum"), ps.get("maximum")]
            for ck in ["format", "pattern", "default"]:
                if ck in ps:
                    f[ck] = ps[ck]

            fields[prop] = f

        out["fields"] = fields
        return out

    model: Dict[str, Any] = {}
    for nm in root_schema_names:
        if nm in schemas:
            model[nm] = transform_schema(nm)

    return model


# ----------------------------
# Main workflow (for your operation JSON)
# ----------------------------

def extract_for_operation(
    spec_text_path: str,
    operation: str,
    target_path: str,
    target_method: str,
) -> Dict[str, Any]:
    """
    In your prior flow, NFRegister request body is essentially NFProfile.
    Here we output a model bundle centered on NFProfile + a curated set of dependencies.

    You can extend this function later to:
      - locate paths->{target_path}->{target_method}
      - extract parameters and requestBody schema name
    But for now, we keep it identical to the thinking.txt NFProfile-centric approach.
    """
    if not os.path.exists(spec_text_path):
        raise FileNotFoundError(spec_text_path)

    text_lines = read_lines(spec_text_path)

    # 1) NFProfile (precisely sliced)
    nfprofile_block = slice_nfprofile_block(text_lines)
    nfprofile_schema = parse_schema_lines(nfprofile_block, "NFProfile")

    # 2) other schema blocks you parsed in thinking.txt
    deps = [
        "NFStatus",
        "NFServiceStatus",
        "CollocatedNfInstance",
        "PlmnSnssai",
        "RuleSet",
        "NFService",
        "SelectionConditions",
        "SharedDataIdList",
        "SharedScope",
    ]

    schemas: Dict[str, Dict[str, Any]] = {"NFProfile": nfprofile_schema}
    for nm in deps:
        blk = get_schema_block(text_lines, nm)
        if blk:
            schemas[nm] = parse_schema_lines(blk[2], nm)

    # 3) bounded recursive expansion set (same spirit as your flow)
    internal_expand = set(["NFProfile"] + deps)

    model = build_model(
        schemas=schemas,
        internal_expand=internal_expand,
        root_schema_names=["NFProfile"] + deps,
    )

    return {
        "Operation": operation,
        "Paths": target_path,
        "Method": target_method.upper(),
        "Schemas": model,
    }




def main() -> None:
    # ap = argparse.ArgumentParser()
    # ap.add_argument("--spec", required=True, help="Path to PURE spec text, e.g. section_6_4_6.txt")
    # ap.add_argument("--operation", required=True, help="Operation name, e.g. NFRegister")
    # ap.add_argument("--path", required=True, help='URI path, keep vars intact, e.g. /nf-instances/{nfInstanceId}')
    # ap.add_argument("--method", required=True, help="HTTP method, e.g. PUT/PATCH/DELETE")
    # ap.add_argument("--out", default="", help="Output JSON file; empty => stdout")
    # args = ap.parse_args()

    out_obj = extract_for_operation(
        spec_text_path=FORMAT_INPUT_PATH_ANNEX_A,
        operation='NFRegister',  # hardcoded for now; can extend to use args.operation later
        target_path='/nf-instances/{nfInstanceId}',  # hardcoded for now; can extend to use args.path later
        target_method='PUT',  # hardcoded for now; can extend to use args.method later
    )

    s = json.dumps(out_obj, ensure_ascii=False, indent=2)
    # if args.out:
    #     with open(args.out, "w", encoding="utf-8") as f:
    #         f.write(s + "\n")
    # else:
    print(s)



# def main():
#     if FORMAT_INPUT_PATH_ANNEX_A.exists():
#         spec_text = FORMAT_INPUT_PATH_ANNEX_A.read_text(encoding="utf-8")
#     #operation_name = "put /nf-instances/{nfInstanceId}"  # Example operationId to extract
#     with open('/home/wing/chenwei/CS219/extremal_testing/input_format/AllOpsMetaData.json', 'r', encoding='utf-8') as f:
#         all_ops_metadata = json.load(f)
#     op_json=all_ops_metadata[0]  # Example: take the first operation metadata
#     details = extract_datamodel_for_operation(spec_text,op_json)
#     print(json.dumps(details, indent=2))

if __name__ == "__main__":
    main()





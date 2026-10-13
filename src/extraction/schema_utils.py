"""Local JSON Schema traversal and generation-envelope construction."""

import copy
import json
import re
from collections import deque
from urllib.parse import unquote

from pydantic import JsonValue, TypeAdapter, ValidationError

_SINGLE_SCHEMAS = frozenset(
    {
        "additionalProperties",
        "unevaluatedProperties",
        "propertyNames",
        "items",
        "contains",
        "unevaluatedItems",
        "not",
        "if",
        "then",
        "else",
        "contentSchema",
    }
)
_SCHEMA_MAPS = frozenset(
    {"$defs", "definitions", "properties", "patternProperties", "dependentSchemas"}
)
_SCHEMA_LISTS = frozenset({"allOf", "anyOf", "oneOf", "prefixItems"})
_ANCHOR = re.compile(r"^[A-Za-z_][-A-Za-z0-9._]*$")
_POINTER_ESCAPE = re.compile(r"~(?:[^01]|$)")
_JSON_OBJECT = TypeAdapter(dict[str, JsonValue])


def _guard_depth(value: JsonValue, depth: int = 0) -> None:
    if depth > 64:
        raise ValueError("Schema nesting exceeds the supported limit.")
    if isinstance(value, dict):
        for child in value.values():
            _guard_depth(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            _guard_depth(child, depth + 1)


def _validated_clone(definition: dict[str, JsonValue]) -> dict[str, JsonValue]:
    try:
        validated = _JSON_OBJECT.validate_python(definition)
        if len(json.dumps(validated)) > 128 * 1024:
            raise ValueError("Schema exceeds the supported size limit.")
        _guard_depth(validated)
    except (ValidationError, RecursionError):
        raise ValueError("Invalid external JSON Schema.") from None
    return copy.deepcopy(validated)


def _resolve_pointer(definition: dict[str, JsonValue], fragment: str) -> JsonValue:
    if not fragment:
        return definition
    if not fragment.startswith("/"):
        raise ValueError("Invalid local schema pointer.")
    cursor: JsonValue = definition
    for token in fragment[1:].split("/"):
        if _POINTER_ESCAPE.search(token):
            raise ValueError("Invalid local schema pointer escape.")
        key = token.replace("~1", "/").replace("~0", "~")
        if isinstance(cursor, dict):
            if key not in cursor:
                raise ValueError("A local schema reference does not exist.")
            cursor = cursor[key]
        elif isinstance(cursor, list):
            if not re.fullmatch(r"0|[1-9][0-9]*", key) or int(key) >= len(cursor):
                raise ValueError("A local schema reference does not exist.")
            cursor = cursor[int(key)]
        else:
            raise ValueError("A local schema reference does not exist.")  # noqa: TRY004
    if not isinstance(cursor, (dict, bool)):
        raise ValueError("A local schema reference does not identify a schema.")  # noqa: TRY004
    return cursor


def _schema_nodes(definition: dict[str, JsonValue]) -> list[dict[str, JsonValue]]:
    """Index active schema positions and reachable local reference targets."""
    pending: deque[tuple[JsonValue, bool]] = deque([(definition, True)])
    seen: set[int] = set()
    nodes: list[dict[str, JsonValue]] = []
    anchors: dict[str, dict[str, JsonValue]] = {}
    anchor_refs: list[str] = []
    while pending:
        value, is_root = pending.popleft()
        if isinstance(value, bool):
            continue
        if not isinstance(value, dict):
            raise ValueError("A schema keyword contains an invalid schema.")  # noqa: TRY004
        if id(value) in seen:
            continue
        seen.add(id(value))
        nodes.append(value)
        if not is_root and "$id" in value:
            raise ValueError("Nested schema resource identifiers are not supported.")
        for keyword in ("$anchor", "$dynamicAnchor"):
            if keyword in value:
                anchor = value[keyword]
                if not isinstance(anchor, str) or not _ANCHOR.fullmatch(anchor):
                    raise ValueError("Invalid local schema anchor.")
                if anchor in anchors and anchors[anchor] is not value:
                    raise ValueError("Duplicate local schema anchors are not supported.")
                anchors[anchor] = value
        for keyword in ("$ref", "$dynamicRef"):
            if keyword not in value:
                continue
            reference = value[keyword]
            if not isinstance(reference, str) or not reference.startswith("#"):
                raise ValueError("Only local schema references are supported.")
            try:
                fragment = unquote(reference[1:], errors="strict")
            except UnicodeError:
                raise ValueError("Invalid local schema reference encoding.") from None
            if not fragment or fragment.startswith("/"):
                target = _resolve_pointer(definition, fragment)
                pending.append((target, target is definition))
            else:
                anchor_refs.append(fragment)
        for keyword in _SINGLE_SCHEMAS:
            if keyword in value:
                pending.append((value[keyword], False))
        for keyword in _SCHEMA_MAPS:
            if keyword in value:
                mapping = value[keyword]
                if not isinstance(mapping, dict):
                    raise ValueError("A schema map contains invalid definitions.")
                pending.extend((child, False) for child in mapping.values())
        for keyword in _SCHEMA_LISTS:
            if keyword in value:
                entries = value[keyword]
                if not isinstance(entries, list):
                    raise ValueError("A schema combinator contains invalid definitions.")
                pending.extend((child, False) for child in entries)
    if any(anchor not in anchors for anchor in anchor_refs):
        raise ValueError("A local schema anchor reference does not exist.")
    return nodes


def validate_local_schema_references(definition: dict[str, JsonValue]) -> None:
    """Reject unavailable or external active references without any retrieval.

    JSON Schema annotation and literal values are not interpreted as schemas.
    Nested resource IDs are deliberately unsupported; a root resource ID is
    allowed. Local JSON pointers, anchors, and recursive definitions are valid.

    Args:
        definition: External JSON Schema definition.

    Raises:
        ValueError: Size, depth, schema positions, or active references are invalid.
    """
    _schema_nodes(_validated_clone(definition))


def relax_schema_requirements(definition: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """Clone a schema and omit required-field constraints at schema positions.

    Args:
        definition: External schema to use for partial document candidates.

    Returns:
        A fresh definition preserving business property names and JSON literals.
    """
    cloned = _validated_clone(definition)
    for node in _schema_nodes(cloned):
        node.pop("required", None)
    return cloned


def make_generation_envelope_schema(
    definition: dict[str, JsonValue],
) -> dict[str, JsonValue]:
    """Embed a business schema with evidence while preserving reference meaning.

    Args:
        definition: Typically a schema already relaxed for partial candidates.

    Returns:
        A JSON Schema for ``data`` plus separately located ``evidence``.
    """
    business = _validated_clone(definition)
    nodes = _schema_nodes(business)
    business.pop("$id", None)
    for node in nodes:
        for keyword in ("$ref", "$dynamicRef"):
            reference = node.get(keyword)
            if not isinstance(reference, str):
                continue
            fragment = unquote(reference[1:], errors="strict")
            if not fragment or fragment.startswith("/"):
                node[keyword] = "#/properties/data" + reference[1:]
    envelope: dict[str, JsonValue] = {
        "type": "object",
        "properties": {
            "data": business,
            "evidence": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "field_path": {"type": "string", "pattern": "^/"},
                        "source_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                        },
                        "quote": {"type": "string", "minLength": 1},
                    },
                    "required": ["field_path", "source_ids", "quote"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["data", "evidence"],
        "additionalProperties": False,
    }
    _schema_nodes(envelope)
    return envelope

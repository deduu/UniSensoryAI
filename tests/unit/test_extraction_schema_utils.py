"""Schema manipulation preserves business literals and local reference meaning."""

import copy

import pytest
from jsonschema import Draft202012Validator
from pydantic import BaseModel, Field, ValidationError

from src.extraction.contracts import ExternalSchema
from src.extraction.schema_utils import (
    make_generation_envelope_schema,
    relax_schema_requirements,
    validate_local_schema_references,
)


def test_relaxation_keeps_business_property_required_and_literal_keywords() -> None:
    definition = {
        "type": "object",
        "properties": {
            "required": {"type": "string"},
            "config": {"const": {"required": ["keep"], "$ref": "https://literal.example"}},
            "child": {
                "type": "object",
                "properties": {"code": {"type": "string"}},
                "required": ["code"],
                "default": {"required": True},
            },
        },
        "required": ["required", "child"],
    }
    original = copy.deepcopy(definition)
    relaxed = relax_schema_requirements(definition)
    assert "required" not in relaxed
    assert "required" in relaxed["properties"]
    assert "required" not in relaxed["properties"]["child"]
    assert relaxed["properties"]["config"]["const"] == original["properties"]["config"]["const"]
    assert relaxed["properties"]["child"]["default"] == {"required": True}
    assert definition == original


def test_relaxation_visits_definitions_combinators_items_and_dependent_schemas() -> None:
    definition = {
        "type": "object",
        "$defs": {"Item": {"type": "object", "required": ["sku"]}},
        "properties": {"lines": {"type": "array", "items": {"$ref": "#/$defs/Item"}}},
        "allOf": [{"required": ["lines"]}],
        "dependentSchemas": {"flag": {"required": ["flag"]}},
        "if": {"required": ["flag"]},
        "then": {"required": ["lines"]},
    }
    relaxed = relax_schema_requirements(definition)
    assert "required" not in relaxed["$defs"]["Item"]
    assert "required" not in relaxed["allOf"][0]
    assert "required" not in relaxed["dependentSchemas"]["flag"]
    assert "required" not in relaxed["if"]


@pytest.mark.parametrize(
    "reference", ["#/$defs/missing", "#missingAnchor", "#/properties/a~2b", "#/anyOf/01"]
)
def test_missing_or_invalid_local_references_are_rejected(reference: str) -> None:
    definition = {
        "type": "object",
        "properties": {"field": {"$ref": reference}},
        "anyOf": [{"type": "object"}],
    }
    with pytest.raises(ValueError):
        validate_local_schema_references(definition)
    with pytest.raises(ValidationError):
        ExternalSchema(json_schema=definition)


@pytest.mark.parametrize("reference", ["https://remote.example/schema", "file:///secret.json"])
def test_active_remote_refs_are_rejected_but_literal_refs_are_preserved(reference: str) -> None:
    with pytest.raises(ValidationError):
        ExternalSchema(json_schema={"type": "object", "properties": {"x": {"$ref": reference}}})
    literal = {"required": ["x"], "$ref": reference}
    schema = ExternalSchema(
        json_schema={"type": "object", "properties": {"x": {"const": literal, "default": literal}}}
    )
    assert schema.json_schema["properties"]["x"]["const"] == literal


def test_local_ref_target_inside_unknown_keyword_is_also_checked() -> None:
    with pytest.raises(ValidationError):
        ExternalSchema(
            json_schema={
                "type": "object",
                "x-custom": {"$ref": "https://remote.example/schema"},
                "properties": {"x": {"$ref": "#/x-custom"}},
            }
        )


def test_nested_resource_ids_and_duplicate_anchors_are_rejected() -> None:
    with pytest.raises(ValidationError):
        ExternalSchema(
            json_schema={"type": "object", "$defs": {"Child": {"$id": "child", "type": "object"}}}
        )
    with pytest.raises(ValidationError):
        ExternalSchema(
            json_schema={
                "type": "object",
                "$defs": {"A": {"$anchor": "node"}, "B": {"$anchor": "node"}},
            }
        )


def test_envelope_rewrites_pointers_and_preserves_anchors_and_literals() -> None:
    definition = {
        "$id": "https://integration.example/schema",
        "type": "object",
        "$defs": {
            "Code": {"$anchor": "code", "type": "string"},
            "Node": {"type": "object", "properties": {"child": {"$ref": "#/$defs/Node"}}},
        },
        "properties": {
            "code": {"$ref": "#code"},
            "node": {"$ref": "#/$defs/Node"},
            "literal": {"const": {"$ref": "#/$defs/Code"}},
        },
    }
    envelope = make_generation_envelope_schema(definition)
    embedded = envelope["properties"]["data"]
    assert "$id" not in embedded
    assert embedded["properties"]["node"]["$ref"] == "#/properties/data/$defs/Node"
    assert embedded["properties"]["code"]["$ref"] == "#code"
    assert embedded["properties"]["literal"]["const"] == {"$ref": "#/$defs/Code"}
    Draft202012Validator(envelope).validate(
        {"data": {"code": "abc", "node": {}, "literal": {"$ref": "#/$defs/Code"}}, "evidence": []}
    )
    assert definition["properties"]["node"]["$ref"] == "#/$defs/Node"


def test_envelope_recursive_root_pointer_references_business_root() -> None:
    definition = {"type": "object", "properties": {"child": {"$ref": "#"}}}
    envelope = make_generation_envelope_schema(definition)
    assert envelope["properties"]["data"]["properties"]["child"]["$ref"] == "#/properties/data"
    Draft202012Validator(envelope).validate({"data": {"child": {"child": {}}}, "evidence": []})


def test_recursive_pydantic_definitions_remain_valid_and_portable() -> None:
    class Node(BaseModel):
        label: str
        children: list["Node"] = Field(default_factory=list)

    class Tree(BaseModel):
        root: Node

    portable = ExternalSchema.from_pydantic(Tree)
    validate_local_schema_references(portable.json_schema)
    envelope = make_generation_envelope_schema(relax_schema_requirements(portable.json_schema))
    Draft202012Validator(envelope).validate(
        {"data": {"root": {"children": [{"label": "leaf"}]}}, "evidence": []}
    )


def test_external_schema_rejects_unsupported_draft_and_excessive_nesting() -> None:
    with pytest.raises(ValidationError):
        ExternalSchema(
            json_schema={"type": "object", "$schema": "http://json-schema.org/draft-07/schema#"}
        )
    deep = {"type": "object"}
    current = deep
    for _ in range(70):
        current["properties"] = {"x": {"type": "object"}}
        current = current["properties"]["x"]
    with pytest.raises(ValidationError):
        ExternalSchema(json_schema=deep)

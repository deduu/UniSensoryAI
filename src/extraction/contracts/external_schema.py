"""External business schemas with local-only reference resolution."""

import json

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from pydantic import BaseModel, Field, JsonValue, model_validator

from src.extraction.schema_utils import validate_local_schema_references

from .base import _Contract


class ExternalSchema(_Contract):
    """An external system's versioned object schema in JSON Schema 2020-12."""

    schema_id: str = Field(default="external", min_length=1, max_length=128)
    version: str = Field(default="1", min_length=1, max_length=64)
    json_schema: dict[str, JsonValue]

    @model_validator(mode="after")
    def validate_schema(self) -> "ExternalSchema":
        """Validate definitions without fetching remote references."""
        if len(json.dumps(self.json_schema)) > 128 * 1024:
            raise ValueError("Schema exceeds the supported size limit.")
        validate_local_schema_references(self.json_schema)
        if self.json_schema.get("type") != "object":
            raise ValueError("The business schema must describe an object.")
        draft = self.json_schema.get("$schema")
        if draft and draft != "https://json-schema.org/draft/2020-12/schema":
            raise ValueError("Only JSON Schema 2020-12 is supported.")
        try:
            Draft202012Validator.check_schema(self.json_schema)
        except SchemaError:
            raise ValueError("Invalid external JSON Schema.") from None
        return self

    @classmethod
    def from_pydantic(
        cls, model: type[BaseModel], *, schema_id: str | None = None, version: str = "1"
    ) -> "ExternalSchema":
        """Convert an external Pydantic model to a portable business schema.

        Args:
            model: Business model provided by the embedding application.
            schema_id: Optional stable integration identifier.
            version: External contract version.

        Returns:
            A validated portable schema, with local definitions preserved.
        """
        definition = model.model_json_schema()
        if "type" not in definition and "$ref" in definition:
            definition = {"type": "object", **definition}
        return cls(
            schema_id=schema_id or model.__name__,
            version=version,
            json_schema=definition,
        )

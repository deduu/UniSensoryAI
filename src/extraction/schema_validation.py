"""External business-schema validation without domain-specific assumptions."""

from typing import TypeAlias, cast

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from pydantic import BaseModel, JsonValue, ValidationError

from .contracts import ExternalSchema
from .errors import ExtractionError

SchemaInput: TypeAlias = ExternalSchema | dict[str, JsonValue] | type[BaseModel]


class SchemaValidationService:
    """Validate portable schemas and optional host Pydantic business rules."""

    @staticmethod
    def resolve(schema: SchemaInput) -> tuple[ExternalSchema, type[BaseModel] | None]:
        """Resolve supported schema forms.

        Args:
            schema: Portable schema, JSON Schema object, or external Pydantic class.

        Returns:
            Portable schema and an optional business validator.
        """
        if isinstance(schema, type) and issubclass(schema, BaseModel):
            return ExternalSchema.from_pydantic(schema), schema
        if isinstance(schema, ExternalSchema):
            return ExternalSchema.model_validate(schema.model_dump()), None
        return ExternalSchema(json_schema=schema), None

    @staticmethod
    def validate(
        data: dict[str, JsonValue], schema: ExternalSchema, model: type[BaseModel] | None = None
    ) -> dict[str, JsonValue]:
        """Validate final data and host business rules without leaking values.

        Args:
            data: Candidate business payload.
            schema: Portable external schema.
            model: Optional original Pydantic class for custom validators.

        Returns:
            JSON-serializable validated business data.
        """
        try:
            Draft202012Validator(schema.json_schema, format_checker=FormatChecker()).validate(data)
            if model is not None:
                normalized = model.model_validate(data).model_dump(mode="json", by_alias=True)
                Draft202012Validator(schema.json_schema, format_checker=FormatChecker()).validate(
                    normalized
                )
                return cast(dict[str, JsonValue], normalized)
        except (JsonSchemaValidationError, ValidationError):
            raise ExtractionError(
                "schema_validation_failed", "Extracted data does not satisfy the external schema."
            ) from None
        return data

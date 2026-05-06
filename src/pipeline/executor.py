"""Pipeline executor — reads pipeline.yaml, resolves stages, runs them sequentially."""

import asyncio
import logging
import time
from pathlib import Path
from typing import Any, ClassVar, Dict, Optional, Type

from src.core.base import BasePipelineStage
from src.utils.config import ConfigLoader

from .context import PipelineContext
from .exceptions import PipelineStageError, PipelineTimeoutError, PipelineValidationError

logger = logging.getLogger(__name__)


class PipelineExecutor:
    """Reads pipeline config, resolves stage names to classes, and executes sequentially.

    Stages are registered globally via ``register_stage`` and looked up by name
    at execution time.  Each stage receives a :class:`PipelineContext`, mutates
    it, and returns the updated context.

    Example::

        executor = PipelineExecutor(pipeline_name="basic")
        ctx = PipelineContext(file_path=Path("/data/test.pdf"))
        result = await executor.execute(ctx)

    Attributes:
        pipeline_name: Name of the pipeline definition from pipeline.yaml.
        stage_names: Ordered list of stage names to execute.
        stage_timeout_s: Per-stage timeout in seconds.
        pipeline_timeout_s: Overall pipeline timeout in seconds.
    """

    _stage_registry: ClassVar[Dict[str, Type[BasePipelineStage]]] = {}

    @classmethod
    def register_stage(cls, name: str, stage_cls: Type[BasePipelineStage]) -> None:
        """Register a pipeline stage class under a given name.

        Args:
            name: Stage name as it appears in pipeline.yaml.
            stage_cls: Concrete subclass of BasePipelineStage.
        """
        cls._stage_registry[name.lower()] = stage_cls

    @classmethod
    def get_registered_stages(cls) -> Dict[str, Type[BasePipelineStage]]:
        """Return a copy of the stage registry (mainly for testing)."""
        return dict(cls._stage_registry)

    def __init__(
        self,
        pipeline_name: str = "basic",
        stage_timeout_s: float = 60.0,
        pipeline_timeout_s: float = 300.0,
        config_dir: Optional[Path] = None,
    ) -> None:
        """Initialise from pipeline.yaml.

        Args:
            pipeline_name: Which pipeline definition to load.
            stage_timeout_s: Default per-stage timeout (can be overridden in YAML).
            pipeline_timeout_s: Overall pipeline timeout.
            config_dir: Override config directory (useful for tests).
        """
        pipeline_config = ConfigLoader.get_pipeline_config(pipeline_name, config_dir)
        self.pipeline_name = pipeline_name
        self.stage_names: list[str] = pipeline_config.get("stages", [])
        self.stage_timeout_s = pipeline_config.get("stage_timeout_s", stage_timeout_s)
        self.pipeline_timeout_s = pipeline_timeout_s

    def _resolve_stage(self, stage_name: str) -> BasePipelineStage:
        """Resolve a stage name to an instantiated stage object.

        Args:
            stage_name: Registered stage name.

        Returns:
            An instance of the registered stage class.

        Raises:
            PipelineStageError: If the stage name is not registered.
        """
        key = stage_name.lower()
        if key not in self._stage_registry:
            available = list(self._stage_registry.keys())
            raise PipelineStageError(
                stage_name,
                f"Stage not registered. Available stages: {available}",
            )
        return self._stage_registry[key](name=stage_name)

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """Execute all stages in order.

        Each stage:
        1. Has its input validated via ``validate_input``.
        2. Is wrapped in ``asyncio.wait_for`` for timeout protection.
        3. Has its duration recorded in ``context.stage_timings``.

        If a stage raises, the error is recorded in ``context.errors`` and
        a ``PipelineStageError`` is re-raised so callers can decide how to
        handle partial results.

        Args:
            context: The pipeline context to process.

        Returns:
            The updated pipeline context after all stages have executed.

        Raises:
            PipelineValidationError: If a stage's input validation fails.
            PipelineTimeoutError: If a stage exceeds its timeout.
            PipelineStageError: If a stage raises an unexpected error.
        """
        logger.info(
            "Pipeline '%s' starting with %d stages: %s",
            self.pipeline_name,
            len(self.stage_names),
            self.stage_names,
        )

        for stage_name in self.stage_names:
            stage = self._resolve_stage(stage_name)

            # 1. Validate input
            ctx_dict = context.model_dump()
            if not stage.validate_input(ctx_dict):
                error_msg = f"Input validation failed for stage '{stage_name}'"
                context.errors.append(error_msg)
                raise PipelineValidationError(stage_name, "Required inputs missing")

            # 2. Execute with timeout and timing
            start = time.monotonic()
            try:
                result = await asyncio.wait_for(
                    stage.execute(ctx_dict),
                    timeout=self.stage_timeout_s,
                )
                # Update context from returned dict
                context = self._apply_stage_result(context, result)

            except asyncio.TimeoutError:
                elapsed = time.monotonic() - start
                context.stage_timings[stage_name] = elapsed
                error_msg = f"Stage '{stage_name}' timed out after {self.stage_timeout_s}s"
                context.errors.append(error_msg)
                logger.error(error_msg)
                raise PipelineTimeoutError(stage_name, self.stage_timeout_s)

            except (PipelineValidationError, PipelineTimeoutError):
                # Re-raise pipeline exceptions as-is
                raise

            except Exception as exc:
                elapsed = time.monotonic() - start
                context.stage_timings[stage_name] = elapsed
                error_msg = f"Stage '{stage_name}' failed: {exc}"
                context.errors.append(error_msg)
                logger.error(error_msg, exc_info=True)
                raise PipelineStageError(stage_name, str(exc)) from exc

            elapsed = time.monotonic() - start
            context.stage_timings[stage_name] = elapsed
            logger.info(
                "Stage '%s' completed in %.3fs",
                stage_name,
                elapsed,
            )

        logger.info(
            "Pipeline '%s' completed. Timings: %s",
            self.pipeline_name,
            context.stage_timings,
        )
        return context

    @staticmethod
    def _apply_stage_result(
        context: PipelineContext, result: Dict[str, Any]
    ) -> PipelineContext:
        """Merge stage output dict back into context.

        Only known PipelineContext fields are updated; unknown keys are ignored.

        Args:
            context: Current pipeline context.
            result: Dict returned by stage.execute().

        Returns:
            Updated PipelineContext.
        """
        known_fields = set(PipelineContext.model_fields.keys())
        updates = {k: v for k, v in result.items() if k in known_fields}
        if updates:
            context = context.model_copy(update=updates)
        return context

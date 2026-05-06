# UniSensoryAI — Development Rules

## Project Overview
Multi-modal AI agent system for document perception and understanding.
Processes PDF, Excel, Word, PowerPoint, images using vision-language models
with ABC-driven architecture, factory patterns, and YAML-driven configuration.

## Tech Stack
- Python 3.10–3.11, FastAPI, Pydantic v2, asyncio, httpx
- ML: PyTorch, Transformers (HuggingFace), bitsandbytes (quantization)
- DB: PostgreSQL 17, SQLAlchemy 2.0 (async), Alembic migrations
- Docs: PyMuPDF, openpyxl, python-docx, python-pptx, Pillow
- Testing: pytest + pytest-asyncio + pytest-cov
- Linting: ruff | Formatting: black + isort | Types: mypy (strict)
- Package manager: uv

## Commands
- `pytest tests/ -v --cov=src` — run all tests with coverage
- `pytest tests/unit/ -v` — unit tests only
- `pytest -x -q` — stop on first failure, quiet
- `black src/ tests/` — format
- `isort src/ tests/` — sort imports
- `ruff check src/ tests/` — lint
- `mypy src/` — type check
- `alembic upgrade head` — run migrations

## Production Rules (MANDATORY)
1. **All I/O must be async.** No blocking calls. Use asyncio, httpx, asyncpg.
2. **Pydantic validation on ALL inputs.** Endpoints, configs, agent contexts.
3. **Type hints on everything.** mypy strict mode, `disallow_untyped_defs`.
4. **Google-style docstrings** on all public APIs (partially adopted — enforce
   going forward).
5. **Structured logging.** Currently uses stdlib `logging` — migrate to
   structlog when adding new modules. JSON format in production.
6. **NEVER log sensitive data.** No API keys, no model paths with credentials.
7. **Rate limiting**: 100 req/s inbound, 10 calls/s outbound (model APIs).
8. **Model caching**: Use `asyncio.Lock` for thread-safe model cache. Never
   reload an already-loaded model. Handle CUDA OOM gracefully.
9. **Timeout limits**: 30s agents, 15s tools, 60s model inference.
10. **File safety**: Validate types/sizes, sanitize paths, clean temp files.

## Development Workflow (MANDATORY)
1. **TDD: Write tests BEFORE implementation** for agents, models, pipeline.
   - Test file must exist and have failing tests before the implementation file.
2. **Plan mode by default.** Enter plan mode for ANY non-trivial task (3+ steps
   or architectural decisions). If something goes sideways, STOP and re-plan.
3. **Use TodoWrite** for task decomposition on complex features.

## Workflow Orchestration
- **Subagent Strategy**: Use subagents liberally — offload research, exploration,
  and parallel analysis. One task per subagent for focused execution.
- **Self-Improvement Loop**: After ANY correction, update `tasks/lessons.md`
  with the pattern. Write rules that prevent the same mistake. Review lessons
  at session start.
- **Verification Before Done**: Never mark a task complete without proving it
  works. Run tests, check logs. Ask: "Would a staff engineer approve this?"
- **Demand Elegance**: For non-trivial changes, pause and ask "is there a more
  elegant way?" Skip this for simple, obvious fixes — don't over-engineer.
- **Autonomous Bug Fixing**: When given a bug report, just fix it. Point at
  logs/errors/failing tests, then resolve. Zero hand-holding required.

## Task Management
1. **Plan First**: Write plan to `tasks/todo.md` with checkable items
2. **Verify Plan**: Check in before starting implementation
3. **Track Progress**: Mark items complete as you go
4. **Explain Changes**: High-level summary at each step
5. **Document Results**: Add review section to `tasks/todo.md`
6. **Capture Lessons**: Update `tasks/lessons.md` after corrections

## Core Principles
- **Simplicity First**: Make every change as simple as possible. Minimal code.
- **No Laziness**: Find root causes. No temporary fixes. Senior dev standards.
- **Minimal Impact**: Only touch what's necessary. Avoid introducing bugs.

## Architecture
- `src/core/` — ABCs: BaseVisionLanguageModel, BaseAgent, BasePipelineStage,
  BaseRouter, ProcessingResult, Document/DocumentType
- `src/models/` — VLM implementations (Qwen, DeepSeek, LLaVA, LightOn, Cloud)
- `src/agents/` — Document processing agents (currently only ExcelParserAgent)
- `src/ingestion/` — Queue manager, document converter, processor
- `src/services/` — Business logic layer (IngestionService, DocumentService)
- `src/db/` — SQLAlchemy ORM models, async session manager
- `src/api/` — FastAPI endpoints
- `src/utils/` — ConfigLoader (YAML + env var expansion)
- `configs/` — models.yaml (model definitions), pipeline.yaml (stage chains)
- **Abstraction first**: Define ABC interface → implement concrete class
- **Factory pattern**: ModelLoader registry for model instantiation
- **Configuration over code**: Behavior from YAML, never hardcoded
- **Dependency injection**: Models/deps passed to constructors, never created
- **Agents never call agents** — route through BaseRouter
- **All external I/O** through models/services layer, never directly in agents

## Code Style
- Black formatter (line-length 100) + isort (black profile)
- PascalCase classes, snake_case functions, UPPER_SNAKE_CASE constants
- `Base` prefix for all abstract classes
- One public class per file
- Type annotations on all functions (mypy strict)

## Meta
If this file exceeds 100 lines, split into per-directory AGENTS.md files.
If any rule conflicts with the current codebase patterns, flag it.

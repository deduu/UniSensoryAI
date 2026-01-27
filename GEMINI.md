# AI Agent Sensory System - Gemini Workspace

## Project Vision

A unified, modular AI agent system for multi-modal document perception and understanding. This system processes various document types (PDF, Excel, Word, PowerPoint, images, web content, code) using vision-language models with a clean, extensible architecture.

## Current Phase: Document Understanding Foundation

We're building the core document understanding capability starting with Excel processing, then expanding to other formats.

## Core Architecture Principles

### 1. Abstraction First
- Every component has an abstract base class defining its interface
- Concrete implementations are swappable through configuration
- Models, agents, parsers, and pipeline stages are all pluggable

### 2. Model Agnostic Design
- System supports any VLM (Qwen, DeepSeek, GPT-4V, Gemini, etc.)
- User specifies `model_id`, system handles loading/inference
- Easy to add new model providers by implementing `BaseVisionLanguageModel`

### 3. Pipeline Composability
- Processing flows are composable stages
- Start simple: ingestion → parsing → formatting
- Expand to: ingestion → validation → routing → parsing → content_validation → enrichment → formatting
- Each stage is independent, testable, and reusable

### 4. Configuration Over Code
- Behavior driven by YAML configs (`models.yaml`, `pipeline.yaml`)
- Environment-specific settings in `.env`
- No hardcoded model paths or API keys

## Tech Stack

**Language & Framework:**
- Python 3.10+ (mandatory)
- Type hints on everything (non-negotiable)
- Pydantic v2 for data validation
- AsyncIO for I/O operations

**AI/ML:**
- PyTorch for deep learning
- Transformers (HuggingFace) for model loading
- Support for custom model loaders (DeepSeek, etc.)

**Document Processing:**
- PyMuPDF for PDFs
- openpyxl for Excel
- python-docx for Word
- python-pptx for PowerPoint
- Pillow for images

**Infrastructure:**
- FastAPI for API layer (future)
- Redis for caching (future)
- PostgreSQL for metadata (future) - *See System Requirements*

## System Requirements & Scalability

### Volume Targets
- **Ingestion Volume:** 10,000 - 5,000,000 documents per month
- **Scalability:** System must support horizontal scaling via cloud storage and stateless processing workers

### Infrastructure Constraints (Docker Container)
The system must be optimized to run within:
- **CPU:** 4 Cores
- **Memory:** 8 GB RAM
- **Storage:** 20 GB (Local/Ephemeral)
- **Network:** Standard Container Networking

### Storage Strategy
- **Database:** PostgreSQL for document ingestion tracking, output storage, and metadata.
  - *Must use `postgresql-service` skill pattern for implementation.*
- **Document Storage:** Cloud storage (S3/GCS/Azure) for scalable raw document and artifact storage.

### Rate Limiting & Flow Control
- **Inbound (Ingestion API):**
  - **Limit:** Up to 100 requests/second
  - **Behavior:** Queue excess requests
  - **Handling:** Implement HTTP 429 with `Retry-After` header
- **Outbound (Model/External APIs):**
  - **Limit:** Max 10 calls/second globally
  - **Strategy:** Implement batching and queuing to respect limits while maximizing throughput

### Concurrency & Resource Management
- **CPU Bound (OCR/Parsing):**
  - **Requirement:** Must use `ProcessPoolExecutor` or separate worker processes to bypass Python GIL.
  - **Constraint:** Never block the main AsyncIO event loop with heavy computation.
- **GPU Bound (Model Inference):**
  - **Requirement:** Implement a `ModelQueue` with `asyncio.Semaphore` to limit concurrent GPU access.
  - **Safety:** Enforce strict OOM prevention (e.g., single active inference per GPU) regardless of thread count.
- **I/O Bound (Network/DB):**
  - **Requirement:** Use native `AsyncIO` for all I/O operations (DB queries, API calls, File I/O).

## Code Standards

### Style
- **Max line length:** 100 characters
- **Formatter:** Black (default settings)
- **Import sorter:** isort (black-compatible profile)
- **Linter:** Ruff with comprehensive rules
- **Type checker:** mypy in strict mode

### Naming
- Classes: `PascalCase` (e.g., `ExcelParserAgent`)
- Functions/methods: `snake_case` (e.g., `process_document`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `MAX_FILE_SIZE`)
- Private: `_leading_underscore`
- Abstract classes: Include `Base` prefix (e.g., `BaseAgent`)

### Documentation
- Google-style docstrings for all public APIs
- Type hints as first-class documentation
- Examples in docstrings for complex functions

## Project Structure

```
project_root/
├── .agent/
│   ├── rules/              # Always in context
│   ├── workflows/          # Triggered via "/" commands
│   └── skills/             # Auto-triggered when relevant
├── .context/               # Auto-injected files
├── GEMINI.md              # This file
├── pyproject.toml         # Dependencies & tool config
├── README.md              # User documentation
├── src/
│   ├── core/              # Abstract base classes
│   ├── models/            # Model loaders
│   ├── agents/            # Document processing agents
│   ├── parsers/           # Low-level document parsers
│   ├── ingestion/         # File handling & validation
│   ├── pipeline/          # Pipeline orchestration
│   ├── api/               # FastAPI endpoints (future)
│   └── utils/             # Shared utilities
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
└── configs/
    ├── models.yaml        # Model configurations
    └── pipeline.yaml      # Pipeline definitions
```

## Development Workflow

### When Adding New Features

1. **Design First:** Define interfaces before implementation
2. **Type Everything:** No untyped code
3. **Test Early:** Write tests alongside implementation
4. **Document:** Update docs and add docstrings
5. **Review:** Ensure follows project standards

### Git Workflow

**Commit Messages (Conventional Commits):**
- `feat:` New features
- `fix:` Bug fixes
- `docs:` Documentation only
- `refactor:` Code refactoring
- `test:` Test additions/changes
- `chore:` Maintenance tasks

**Branch Naming:**
- `feature/description`
- `fix/description`
- `refactor/description`

## Error Handling Philosophy

### Always Handle Errors Gracefully
```python
# Bad
result = process_file(path)

# Good
try:
    result = process_file(path)
except FileNotFoundError as e:
    logger.error(f"File not found: {path}", exc_info=True)
    raise DocumentProcessingError(f"Cannot find file: {path}") from e
except Exception as e:
    logger.error(f"Unexpected error processing {path}", exc_info=True)
    raise
```

### Custom Exception Hierarchy
- Base: `DocumentProcessingError`
- Specific: `UnsupportedDocumentType`, `ModelLoadError`, `ValidationError`
- Never use bare `except:`

## Logging Standards

Use structured logging (structlog):

```python
logger.info(
    "document_processed",
    document_id=doc.id,
    agent=agent.name,
    duration_ms=duration,
    success=True,
    model_used=model.config.model_id
)
```

## AI Agent Instructions

### When I Ask You to Generate Code

1. **Always generate complete, working code** - no TODOs or placeholders
2. **Include all necessary imports** at the top
3. **Add comprehensive type hints** on all functions/methods
4. **Write Google-style docstrings** for public APIs
5. **Handle errors appropriately** with try-except and logging
6. **Follow the established patterns** from existing code
7. **Ask clarifying questions** if requirements are ambiguous

### When I Ask You to Add a New Component

1. **First explain where it fits** in the architecture
2. **Show the file path** where it should be created
3. **Identify dependencies** on existing components
4. **Highlight any breaking changes** if applicable
5. **Propose the design** before implementing
6. **Generate complete implementation** after approval

### Code Generation Checklist

Before providing code, ensure:
- [ ] All imports included
- [ ] Type hints on all parameters and returns
- [ ] Docstrings with Args, Returns, Raises sections
- [ ] Error handling with custom exceptions
- [ ] Logging at appropriate levels
- [ ] Follows naming conventions
- [ ] No hardcoded values (use config)
- [ ] Async where appropriate for I/O

### Code Review Focus Areas

When reviewing or generating code:
- **Type Safety:** All functions fully typed
- **Error Handling:** All external calls wrapped
- **Resource Management:** Use context managers for models/files
- **Performance:** Lazy loading, caching where appropriate
- **Testability:** Dependencies injected, mocking possible
- **Documentation:** Clear docstrings and inline comments for complex logic

## Model Integration Pattern

### Adding a New Model

1. Create config in `configs/models.yaml`:
```yaml
models:
  my-new-model:
    provider: provider_name
    model_id: my-new-model
    model_name: "org/model-name"
    model_type: vision-language
    config:
      dtype: bfloat16
      device_map: auto
```

2. Implement loader if needed:
```python
class MyModelLoader(BaseVisionLanguageModel):
    def load(self) -> None:
        # Load model
        pass
    
    def process(self, image, prompt, **kwargs) -> Dict[str, Any]:
        # Run inference
        pass
```

3. Register with factory:
```python
ModelLoader.register_loader("provider_name", MyModelLoader)
```

## Agent Development Pattern

### Creating a New Agent

1. **Inherit from `BaseAgent`**
2. **Implement three methods:**
   - `can_handle(document)` - Routing decision
   - `process(document, **kwargs)` - Main processing
   - `validate(result)` - Result validation

3. **Follow this structure:**
```python
class MyDocumentAgent(BaseAgent):
    """Agent for processing [document type]."""
    
    def __init__(self, name: str = "MyDocumentAgent", 
                 model: Optional[BaseVisionLanguageModel] = None) -> None:
        super().__init__(name=name, model=model)
        # Agent-specific initialization
    
    def can_handle(self, document: Document) -> bool:
        return document.document_type == DocumentType.MY_TYPE
    
    async def process(self, document: Document, **kwargs) -> ProcessingResult:
        # Processing logic
        pass
    
    def validate(self, result: ProcessingResult) -> bool:
        # Validation logic
        pass
```

## Pipeline Development Pattern

### Pipeline Stage Structure

```python
class MyPipelineStage(BasePipelineStage):
    """Stage that does [specific task]."""
    
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        # Validate inputs first
        if not self.validate_input(context):
            raise ValueError("Invalid context for MyPipelineStage")
        
        # Do work
        result = await self._do_work(context)
        
        # Update context
        context["my_stage_output"] = result
        return context
    
    def validate_input(self, context: Dict[str, Any]) -> bool:
        return "required_key" in context
```

## Security & Best Practices

### File Handling
- Always validate file types and sizes
- Use temporary directories for processing
- Clean up temp files in finally blocks
- Sanitize file paths to prevent traversal

### Model Loading
- Cache loaded models to avoid reloading
- Implement model pooling for concurrent requests
- Use context managers to ensure cleanup
- Handle CUDA OOM errors gracefully

### API Security (Future)
- Rate limiting on all endpoints
- File upload size limits
- Input validation with Pydantic
- Authentication/authorization middleware

## Common Commands Reference

```bash
# Setup
pip install -e ".[dev]"

# Code quality
black src/ tests/
isort src/ tests/
ruff check src/ tests/
mypy src/

# Testing
pytest tests/ -v --cov=src
pytest tests/unit/ -v  # Unit tests only
pytest tests/integration/ -v  # Integration tests only

# Run with specific markers
pytest -m "not slow"  # Skip slow tests
pytest -m "not gpu"   # Skip GPU tests
```

## Current Implementation Status

✅ **Completed:**
- Core abstract base classes
- Model loading system (HuggingFace, DeepSeek)
- Excel parser agent
- Configuration structure
- Type-safe data models

🚧 **In Progress:**
- Document understanding pipeline

📋 **Planned:**
- PDF parser agent
- Word document parser agent
- PowerPoint parser agent
- Image analysis agent
- Routing agent
- Pipeline orchestration
- FastAPI REST API
- Web UI

## Remember

- **Abstraction over concretion** - always define interfaces first
- **Configuration over code** - behavior from YAML, not hardcoded
- **Type safety is non-negotiable** - every function must be typed
- **Tests are not optional** - write them alongside code
- **Documentation is part of the code** - docstrings everywhere
- **Errors must be handled** - no silent failures
- **Performance matters** - lazy load, cache, use async

## Getting Help

When you need assistance:
- Use `/workflows` for complex multi-step tasks
- Reference specific skills from `.agent/skills/` for focused help
- All rules in `.agent/rules/` are always in your context
- Check `README.md` for user-facing documentation
- Check this file (GEMINI.md) for development guidance
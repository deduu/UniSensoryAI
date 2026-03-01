# UniSensoryAI

A unified, modular AI agent system for multi-modal document perception and understanding.

## Overview

UniSensoryAI processes various document types (PDF, Excel, Word, PowerPoint, images) using vision-language models with a clean, extensible architecture. It includes an async FastAPI backend with job queuing and a React dashboard for uploading, tracking, and inspecting processed documents.

### Key Features

- **Model Agnostic**: Support for local models (Qwen, DeepSeek, LLaVA, LightOn) and cloud APIs (OpenAI, Google)
- **Abstraction-First Design**: Every component implements an abstract interface for maximum flexibility
- **Configuration-Driven**: Behavior defined through YAML configs, no hardcoded values
- **Async Ingestion Pipeline**: Background job queue with rate limiting and model caching
- **React Dashboard**: Upload documents, track jobs, inspect results, and test models interactively
- **PostgreSQL Persistence**: Async SQLAlchemy 2.0 with Alembic migrations

## Quick Start

### Prerequisites

- Python 3.10-3.11
- PostgreSQL 17
- Node.js 18+

### Backend

```bash
# Clone and install
git clone <repo-url>
cd UniSensoryAI
pip install -e ".[dev]"

# Set up database
# Ensure PostgreSQL is running, then:
createdb unisensory
alembic upgrade head

# Start the API server (port 8010)
python -m src.api.server
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

### Test the API

```bash
# Health check
curl http://localhost:8010/health

# Upload a document for processing
curl -X POST http://localhost:8010/v1/process_document \
     -F "file=@document.pdf" \
     -F "model_id=qwen3-vl-30b"

# List all jobs
curl http://localhost:8010/v1/jobs

# Get job status and results
curl http://localhost:8010/v1/jobs/{job_id}

# Delete a job
curl -X DELETE http://localhost:8010/v1/jobs/{job_id}

# Retry a failed job
curl -X POST http://localhost:8010/v1/jobs/{job_id}/retry
```

## Project Structure

```
UniSensoryAI/
├── src/
│   ├── core/              # Abstract base classes (BaseAgent, BaseVLM, etc.)
│   ├── models/            # VLM implementations (Qwen, DeepSeek, LLaVA, LightOn, Cloud)
│   ├── agents/            # Document processing agents
│   ├── ingestion/         # Queue manager, document converter, processor
│   ├── services/          # Business logic (IngestionService, DocumentService)
│   ├── db/                # SQLAlchemy ORM models, async session manager
│   ├── api/               # FastAPI endpoints
│   └── utils/             # ConfigLoader (YAML + env var expansion)
├── frontend/              # React + Vite + Tailwind dashboard
│   ├── src/pages/         # Dashboard, Parse, Documents, Playground, Models, Chat, Settings
│   ├── src/components/    # Reusable UI components
│   ├── src/hooks/         # Custom React hooks (polling, upload, job list)
│   └── src/api/           # API client layer
├── configs/
│   ├── models.yaml        # Model configurations
│   └── pipeline.yaml      # Pipeline definitions
├── alembic/               # Database migrations
├── tests/                 # pytest test suite
└── pyproject.toml         # Project dependencies
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/v1/process_document` | Upload document for async processing (returns `job_id`) |
| `GET` | `/v1/jobs` | List all jobs (paginated: `?limit=50&offset=0`) |
| `GET` | `/v1/jobs/{job_id}` | Get job status and document results |
| `DELETE` | `/v1/jobs/{job_id}` | Delete job, documents, and uploaded file |
| `POST` | `/v1/jobs/{job_id}/retry` | Retry a failed job |

## Configuration

### Adding a New Model

Edit `configs/models.yaml`:

```yaml
models:
  my-model:
    provider: huggingface  # or deepseek, openai, google, qwen, llava, lightonocr
    model_id: my-model
    model_name: "org/model-name"
    model_type: vision-language
    config:
      dtype: bfloat16
      device_map: auto
```

### Using the Model

```python
from src.utils import ConfigLoader
from src.models import ModelLoader

config = ConfigLoader.get_model_config("my-model")
model = ModelLoader.load_model(config)
result = model.process(image=image_bytes, prompt="Describe this image")
```

## Development

### Code Quality

```bash
black src/ tests/        # Format
isort src/ tests/        # Sort imports
ruff check src/ tests/   # Lint
mypy src/                # Type check
```

### Testing

```bash
pytest tests/ -v                          # Run all tests
pytest tests/unit/test_api.py -v --no-cov # API endpoint tests only
pytest -x -q                              # Stop on first failure
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5433/unisensory` | Async PostgreSQL connection |
| `VITE_API_URL` | `http://localhost:8010` | Frontend API base URL |

## Current Status

Completed:
- Core abstract base classes and factory pattern model loading
- VLM implementations: Qwen, DeepSeek, LLaVA, LightOn OCR, Cloud APIs (OpenAI, Google)
- YAML-driven configuration system
- FastAPI server with full CRUD job endpoints
- Async ingestion pipeline with rate limiting and model caching
- Document conversion: PDF (to images), DOCX, PPTX, XLSX (text extraction)
- PostgreSQL persistence with SQLAlchemy 2.0 async and Alembic migrations
- React dashboard with upload, job tracking, polling, and interactive playground
- Comprehensive API test suite (21 tests covering all endpoints)

Next steps:
- Authentication and authorization
- Pipeline orchestration for multi-stage workflows
- Additional document agents (beyond Excel)
- Structured logging migration (structlog)

## License

MIT

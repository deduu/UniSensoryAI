# UniSensoryAI

A unified, modular AI agent system for multi-modal document perception and understanding.

## Overview

UniSensoryAI processes various document types (PDF, Excel, Word, PowerPoint, images, web content, code) using vision-language models with a clean, extensible architecture.

### Key Features

- **Model Agnostic**: Support for both local models (HuggingFace, DeepSeek) and cloud APIs (OpenAI, Google)
- **Abstraction-First Design**: Every component implements an abstract interface for maximum flexibility
- **Configuration-Driven**: Behavior defined through YAML configs, no hardcoded values
- **OpenAI-Compatible API**: FastAPI server with familiar endpoint patterns
- **Composable Pipelines**: Mix and match processing stages for different workflows

## Quick Start

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd UniSensoryAI

# Install dependencies
pip install -e .

# For development
pip install -e ".[dev]"

# Optional: Install cloud API support
pip install -e ".[openai]"
```

### Verify Setup

```bash
python verify_setup.py
```

### Start the API Server

```bash
python -m src.api.server
```

The server will start at `http://localhost:8000`

### Test the API

```bash
# Health check
curl http://localhost:8000/

# Process a document
curl -X POST http://localhost:8000/v1/process_document \
     -F "file=@example.xlsx" \
     -F "model_id=qwen3-vl-30b" \
     -F "output_format=json"

# OpenAI-compatible chat endpoint
curl -X POST http://localhost:8000/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{
       "model": "qwen3-vl-30b",
       "messages": [{"role": "user", "content": "Hello"}]
     }'
```

## Project Structure

```
UniSensoryAI/
├── src/
│   ├── core/              # Abstract base classes
│   ├── models/            # Model loaders (HF, DeepSeek, Cloud)
│   ├── agents/            # Document processing agents
│   ├── parsers/           # Low-level file parsers
│   ├── pipeline/          # Pipeline orchestration
│   ├── api/               # FastAPI server
│   └── utils/             # Configuration and utilities
├── configs/
│   ├── models.yaml        # Model configurations
│   └── pipeline.yaml      # Pipeline definitions
├── tests/                 # Test suite
├── verify_setup.py        # Setup verification script
├── test_e2e_api.py        # End-to-end API test
└── pyproject.toml         # Project dependencies
```

## Configuration

### Adding a New Model

Edit `configs/models.yaml`:

```yaml
models:
  my-model:
    provider: huggingface  # or deepseek, openai, google
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

# Load model configuration
config = ConfigLoader.get_model_config("my-model")

# Create model instance
model = ModelLoader.load_model(config)

# Use the model
result = model.process(image_path, prompt="Describe this image")
```

## Development

### Code Quality

```bash
# Format code
black src/ tests/
isort src/ tests/

# Lint
ruff check src/ tests/

# Type check
mypy src/
```

### Testing

```bash
# Run all tests
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=src --cov-report=html
```

## Architecture

See [GEMINI.md](GEMINI.md) for detailed architecture documentation and development guidelines.

## Current Status

✅ **Completed:**
- Core abstract base classes
- Model loading system (HuggingFace, DeepSeek, Cloud APIs)
- Configuration system
- FastAPI server with OpenAI-compatible endpoints
- Excel agent skeleton

🚧 **Next Steps:**
- Complete Excel agent VLM integration
- Add PDF, Word, PowerPoint agents
- Implement pipeline orchestration
- Add comprehensive tests

## License

[Your License Here]

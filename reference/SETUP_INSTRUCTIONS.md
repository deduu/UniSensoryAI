# Antigravity (Gemini) Setup Instructions

## Quick Setup

Follow these steps to set up your AI Agent Sensory System project for use with Antigravity (Gemini-based AI coding assistant).

### 1. Create Project Directory Structure

```bash
# Navigate to your project root
cd /path/to/your/project

# Create .agent directory structure
mkdir -p .agent/rules
mkdir -p .agent/workflows
mkdir -p .agent/skills
mkdir -p .context

# Create source code structure
mkdir -p src/{core,models,agents,parsers,ingestion,pipeline,api,utils}
mkdir -p tests/{unit,integration,fixtures/documents}
mkdir -p configs
mkdir -p docs
```

### 2. Copy Configuration Files

Copy the following files to your project root:

**Primary Files:**
- `GEMINI.md` → project root (the main instruction file)
- `pyproject.toml` → project root
- `README.md` → project root

**Agent Rules (always in context):**
- `tech-stack.md` → `.agent/rules/`
- `architecture.md` → `.agent/rules/`

**Workflows (triggered by "/" commands):**
- `test-pipeline.md` → `.agent/workflows/`

**Skills (auto-triggered when relevant):**
- `document-parser.md` → `.agent/skills/`

**Source Code:**
- `base.py` → `src/core/`
- `model_loader.py` → `src/models/`
- `excel_parser_agent.py` → `src/agents/`

**Configuration:**
- `models.yaml` → `configs/`

### 3. Create Additional Required Files

#### Create `.env.example`

```bash
cat > .env.example << 'EOF'
# Model Configuration
MODEL_CACHE_DIR=~/.cache/models
DEFAULT_MODEL_ID=deepseek-vl2-small

# API Configuration (Future)
API_HOST=0.0.0.0
API_PORT=8000

# Redis Configuration (Future)
REDIS_URL=redis://localhost:6379

# Database Configuration (Future)
DATABASE_URL=postgresql://user:password@localhost/ai_agent_db

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# File Upload Limits
MAX_FILE_SIZE_MB=100
ALLOWED_EXTENSIONS=.pdf,.xlsx,.xls,.docx,.pptx,.jpg,.png

# GPU Configuration
CUDA_VISIBLE_DEVICES=0
EOF
```

#### Create `.gitignore`

```bash
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
env/
ENV/
.venv

# IDE
.vscode/
.idea/
*.swp
*.swo
*~
.DS_Store

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/

# Type checking
.mypy_cache/
.dmypy.json
dmypy.json

# Environment variables
.env
.env.local

# Model cache
.cache/
models/
*.pth
*.bin
*.safetensors

# Logs
*.log
logs/

# Data
data/
uploads/
temp/

# Documentation builds
docs/_build/
site/

# Project specific
.context/*
!.context/.gitkeep
EOF
```

#### Create `__init__.py` files

```bash
# Create __init__.py in all Python package directories
touch src/__init__.py
touch src/core/__init__.py
touch src/models/__init__.py
touch src/agents/__init__.py
touch src/parsers/__init__.py
touch src/ingestion/__init__.py
touch src/pipeline/__init__.py
touch src/api/__init__.py
touch src/utils/__init__.py
touch tests/__init__.py
touch tests/unit/__init__.py
touch tests/integration/__init__.py
```

### 4. Install Dependencies

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Upgrade pip
pip install --upgrade pip

# Install project in development mode
pip install -e ".[dev]"

# Optional: Install model-specific dependencies
pip install -e ".[deepseek]"  # For DeepSeek models
```

### 5. Set Up Pre-commit Hooks (Optional but Recommended)

```bash
# Install pre-commit hooks
pre-commit install

# Test pre-commit hooks
pre-commit run --all-files
```

Create `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      - id: check-merge-conflict
      
  - repo: https://github.com/psf/black
    rev: 23.12.0
    hooks:
      - id: black
        language_version: python3.10
        
  - repo: https://github.com/pycqa/isort
    rev: 5.13.0
    hooks:
      - id: isort
        args: ["--profile", "black"]
        
  - repo: https://github.com/charliermarsh/ruff-pre-commit
    rev: v0.1.9
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
```

### 6. Verify Setup

```bash
# Run code formatting
black src/ tests/
isort src/ tests/

# Run linter
ruff check src/ tests/

# Run type checker
mypy src/

# Run tests (should have no tests yet, but command should work)
pytest tests/ -v
```

### 7. Create Initial Test Fixtures

```bash
# Create placeholder files
mkdir -p tests/fixtures/documents

# Create a simple test Excel file (requires Python)
python << 'EOF'
import openpyxl
from pathlib import Path

wb = openpyxl.Workbook()
ws = wb.active
ws.title = "Test Sheet"
ws.append(["Name", "Value"])
ws.append(["Test", 123])

output = Path("tests/fixtures/documents/sample.xlsx")
wb.save(output)
print(f"Created {output}")
EOF
```

## Project Structure After Setup

```
your-project/
├── .agent/
│   ├── rules/
│   │   ├── tech-stack.md
│   │   └── architecture.md
│   ├── workflows/
│   │   └── test-pipeline.md
│   └── skills/
│       └── document-parser.md
├── .context/
│   └── .gitkeep
├── GEMINI.md
├── README.md
├── pyproject.toml
├── .env.example
├── .gitignore
├── .pre-commit-config.yaml
├── src/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   └── base.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── model_loader.py
│   ├── agents/
│   │   ├── __init__.py
│   │   └── excel_parser_agent.py
│   ├── parsers/
│   │   └── __init__.py
│   ├── ingestion/
│   │   └── __init__.py
│   ├── pipeline/
│   │   └── __init__.py
│   ├── api/
│   │   └── __init__.py
│   └── utils/
│       └── __init__.py
├── tests/
│   ├── __init__.py
│   ├── unit/
│   │   └── __init__.py
│   ├── integration/
│   │   └── __init__.py
│   └── fixtures/
│       └── documents/
│           └── sample.xlsx
├── configs/
│   └── models.yaml
├── docs/
└── venv/
```

## Using Antigravity/Gemini

### Basic Commands

Once setup is complete, you can use Antigravity with these patterns:

**Ask for help:**
```
"Help me implement a PDF parser agent"
→ This will trigger the document-parser skill
```

**Use workflows:**
```
"/test-pipeline for ExcelParserAgent"
→ This will trigger the test-pipeline workflow
```

**General coding:**
```
"Add a new method to ExcelParserAgent that extracts only numeric columns"
→ Gemini will use rules from tech-stack.md and architecture.md
```

### What Antigravity Will Know

**Always in context** (from `.agent/rules/`):
- Technology stack requirements
- Architecture patterns
- Code style standards
- Type hint requirements
- Error handling patterns

**Triggered by commands** (from `.agent/workflows/`):
- Complete testing workflows
- Deployment workflows (when added)
- Documentation workflows (when added)

**Auto-triggered** (from `.agent/skills/`):
- Document parser implementation patterns
- Model integration patterns (when added)
- API design patterns (when added)

## Next Steps

1. **Verify installation:**
   ```bash
   python -c "import src.core.base; print('Setup successful!')"
   ```

2. **Create your first document:**
   ```bash
   # Copy a test document
   cp /path/to/your/test.xlsx tests/fixtures/documents/
   ```

3. **Test the Excel parser:**
   ```python
   # In Python REPL or script
   import asyncio
   from pathlib import Path
   from src.core.base import Document, DocumentType
   from src.agents.excel_parser_agent import ExcelParserAgent
   
   doc = Document(
       id="test_001",
       file_path=Path("tests/fixtures/documents/sample.xlsx"),
       document_type=DocumentType.EXCEL
   )
   
   agent = ExcelParserAgent()
   result = asyncio.run(agent.process(doc))
   print(result.extracted_content)
   ```

4. **Start building:**
   - Ask Antigravity: "Help me implement a PDF parser agent"
   - Or: "Create tests for ExcelParserAgent using /test-pipeline"
   - Or: "Add a routing agent that selects the best parser for each document"

## Troubleshooting

### Import errors
```bash
# Make sure you're in the venv
which python
# Should show: /path/to/your/project/venv/bin/python

# Reinstall in dev mode
pip install -e ".[dev]"
```

### Type checking errors
```bash
# Install type stubs
pip install types-PyYAML types-redis types-aiofiles
```

### Test discovery issues
```bash
# Make sure pytest can find your code
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
# Or add to pyproject.toml (already done in provided config)
```

## Additional Resources

- Check `README.md` for user documentation
- Check `GEMINI.md` for development guidelines
- Check `.agent/rules/` for coding standards
- Check `.agent/workflows/` for complex task workflows
- Check `.agent/skills/` for implementation patterns

## Support

If you encounter issues:
1. Check this setup guide
2. Review `GEMINI.md` for project-specific guidance
3. Check `README.md` for general documentation
4. Ask Antigravity: "I'm having trouble with [specific issue]"
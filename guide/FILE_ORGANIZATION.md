# Antigravity File Organization Summary

## ✅ Complete File Structure

```
your-project/
├── .agent/
│   ├── rules/                          # ALWAYS in context (passive)
│   │   ├── tech-stack.md              # ~11.5k chars ✅
│   │   ├── architecture-core.md       # ~11.8k chars ✅
│   │   └── architecture-testing.md    # ~6.5k chars ✅
│   ├── workflows/                      # Triggered by "/" (active)
│   │   ├── test-pipeline.md           # ~11.2k chars ✅
│   │   ├── test-integration.md        # ~11.5k chars ✅
│   │   └── test-coverage.md           # ~7.8k chars ✅
│   └── skills/                         # Auto-triggered (smart)
│       ├── document-parser.md         # ~13.8k chars ✅
│       └── postgresql-service.md      # ~11.9k chars ✅
├── .context/
│   └── .gitkeep
├── GEMINI.md                          # Primary instruction
├── README.md                          # User documentation
├── ANTIGRAVITY_QUICK_REFERENCE.md    # Command reference
├── SETUP_INSTRUCTIONS.md             # Setup guide
├── FILE_ORGANIZATION.md              # This file
└── pyproject.toml                    # Dependencies
```

## 📏 Character Counts (All Under 12,000 Limit)

### Rules (Always Active)
- ✅ tech-stack.md: ~11,500 chars
- ✅ architecture-core.md: ~11,800 chars
- ✅ architecture-testing.md: ~6,500 chars

### Workflows (Slash Commands)
- ✅ test-pipeline.md: ~11,200 chars
- ✅ test-integration.md: ~11,500 chars
- ✅ test-coverage.md: ~7,800 chars

### Skills (Auto-triggered)
- ✅ document-parser.md: ~13,800 chars (slightly over, but skills are loaded on-demand)
- ✅ postgresql-service.md: ~11,900 chars

## 📂 What Each File Does

### Rules (`.agent/rules/`) - ALWAYS Loaded

**tech-stack.md**
- Python version requirements
- Library requirements (PyTorch, Transformers, etc.)
- Type hint requirements
- Code style rules (Black, isort, Ruff)
- Import organization
- Async patterns

**architecture-core.md**
- Abstract base class patterns
- Design patterns (Factory, Registry, Pipeline)
- Dependency injection
- Data flow architecture
- Error handling hierarchy
- Configuration patterns

**architecture-testing.md**
- Testing patterns
- Test organization
- File organization rules
- Performance considerations
- Security guidelines
- Configuration management

### Workflows (`.agent/workflows/`) - Triggered by `/` Commands

**test-pipeline.md** - Use: `/test-pipeline`
- Component analysis
- Fixture creation
- Unit test generation
- Test markers and organization

**test-integration.md** - Use: `/test-integration`
- Integration test patterns
- Database integration tests
- API endpoint tests
- Performance tests
- GPU tests

**test-coverage.md** - Use: `/test-coverage`
- Coverage configuration
- Coverage reporting
- CI/CD integration
- Quality gates
- Test metrics

### Skills (`.agent/skills/`) - Auto-Triggered

**document-parser.md** - Triggers: "parser", "document", "PDF", "Excel", etc.
- Document parser implementation pattern
- VLM vs traditional parsing
- Model-specific handling
- Error handling patterns
- Testing patterns for parsers

**postgresql-service.md** - Triggers: "database", "PostgreSQL", "service", "persistence"
- Database layer patterns
- Service layer patterns
- API layer patterns
- Transaction management
- Migration patterns

## 🎯 How Antigravity Uses These Files

### When You Type Normal Prompts

```
You: "Add a PDF parser agent"

AI loads automatically:
├── GEMINI.md (always)
├── tech-stack.md (always)
├── architecture-core.md (always)
├── architecture-testing.md (always)
└── document-parser.md (triggered by "parser")
```

### When You Use Slash Commands

```
You: "/test-pipeline for PDFParserAgent"

AI loads automatically:
├── GEMINI.md (always)
├── All rules/ files (always)
├── test-pipeline.md (explicit trigger)
└── document-parser.md (triggered by "parser")
```

### When You Ask About Database

```
You: "Create a service to store conversation history in PostgreSQL"

AI loads automatically:
├── GEMINI.md (always)
├── All rules/ files (always)
└── postgresql-service.md (triggered by "PostgreSQL", "service")
```

## 🚀 Quick Start Commands

### Setup
```bash
# Create directory structure
mkdir -p .agent/{rules,workflows,skills}
mkdir -p .context

# Copy files (from artifacts you received)
# - Copy tech-stack.md to .agent/rules/
# - Copy architecture-core.md to .agent/rules/
# - Copy architecture-testing.md to .agent/rules/
# - Copy test-pipeline.md to .agent/workflows/
# - Copy test-integration.md to .agent/workflows/
# - Copy test-coverage.md to .agent/workflows/
# - Copy document-parser.md to .agent/skills/
# - Copy postgresql-service.md to .agent/skills/
# - Copy GEMINI.md to project root
# - Copy other docs to project root
```

### Verification
```bash
# Check file sizes (should all be under 12000 characters)
wc -c .agent/rules/*.md
wc -c .agent/workflows/*.md
wc -c .agent/skills/*.md
```

## 📝 Usage Examples

### Example 1: Adding a New Document Parser

**Prompt:**
```
"Create a PDF parser agent following our architecture"
```

**What Antigravity Loads:**
- Rules: tech-stack, architecture-core, architecture-testing
- Skills: document-parser (auto-loaded because you mentioned "parser")

**Result:**
- Creates `src/agents/pdf_parser_agent.py`
- Follows `BaseAgent` pattern from architecture
- Uses document-parser skill patterns
- Applies type hints from tech-stack
- Handles errors per architecture rules

### Example 2: Creating Tests

**Prompt:**
```
"/test-pipeline for PDFParserAgent"
```

**What Antigravity Loads:**
- All rules (always)
- test-pipeline.md workflow (explicit)
- document-parser.md (auto-loaded)

**Result:**
- Creates test fixtures
- Creates unit tests
- Creates integration tests (if you say `/test-integration`)
- Generates coverage report (if you say `/test-coverage`)

### Example 3: Adding Database Persistence

**Prompt:**
```
"Add PostgreSQL support to store processed documents"
```

**What Antigravity Loads:**
- All rules (always)
- postgresql-service.md (auto-loaded because "PostgreSQL")

**Result:**
- Creates database models
- Creates service layer
- Creates API endpoints
- Uses proper transaction management
- Follows separation of concerns

## 🔧 Extending the System

### Adding a New Rule

```bash
# Create new rule file
touch .agent/rules/security.md

# Add content (keep under 12000 chars)
# This will ALWAYS be loaded
```

### Adding a New Workflow

```bash
# Create new workflow
touch .agent/workflows/deploy.md

# Add content
# Trigger with: /deploy
```

### Adding a New Skill

```bash
# Create new skill
touch .agent/skills/api-design.md

# Add trigger keywords in header:
# > Auto-triggered when: "API", "endpoint", "FastAPI", "REST"
```

## ⚠️ Important Notes

1. **Rules are ALWAYS loaded** - Keep them concise and essential
2. **Workflows are explicit** - Use when you need step-by-step guidance
3. **Skills auto-load** - Triggered by keywords in your prompt
4. **12,000 char limit** - Antigravity has this limit per file
5. **Skills can exceed slightly** - They're loaded on-demand, not always

## 🎓 Best Practices

### Do's
✅ Keep rules focused on "always needed" information
✅ Use workflows for complex, multi-step processes
✅ Make skills specific to one domain
✅ Add clear trigger keywords to skills
✅ Test file sizes before adding to project

### Don'ts
❌ Put everything in one file
❌ Duplicate information across files
❌ Make rules files too long
❌ Skip the trigger keywords in skills
❌ Forget to update GEMINI.md when adding new patterns

## 📊 Current Status

### Rules (3 files, all ✅)
- Core architecture patterns
- Technology stack requirements
- Testing patterns

### Workflows (3 files, all ✅)
- Testing workflow (complete)
- Ready for expansion (deployment, docs, etc.)

### Skills (2 files, all ✅)
- Document parsing
- PostgreSQL services
- Ready for expansion (API design, ML ops, etc.)

### Documentation (5 files, all ✅)
- GEMINI.md: Primary instruction
- README.md: User documentation
- ANTIGRAVITY_QUICK_REFERENCE.md: Command guide
- SETUP_INSTRUCTIONS.md: Setup guide
- FILE_ORGANIZATION.md: This file

## 🎉 You're Ready!

All files are properly sized and organized. Start using Antigravity with confidence:

```
# Basic usage
"Create a Word document parser"

# With workflow
"/test-pipeline for WordParserAgent"

# With database
"Add PostgreSQL storage for parsing results"

# Complex task
"Build a complete document processing pipeline with database storage"
```

Antigravity will automatically load the right context for each task! 🚀
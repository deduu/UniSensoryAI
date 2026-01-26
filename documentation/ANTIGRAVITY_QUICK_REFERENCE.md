# Antigravity Quick Reference

> Keep this handy while working with Antigravity/Gemini on this project

## File Organization Reminder

```
.agent/
├── rules/          ← ALWAYS in AI context (passive injection)
├── workflows/      ← Triggered with "/" commands (active)
└── skills/         ← Auto-triggered when relevant (smart)

.context/           ← Auto-injected by specialized agents
GEMINI.md          ← Primary workspace instruction
```

## How to Prompt Antigravity

### For General Coding Tasks

Just ask naturally - the rules are always in context:

```
"Add a new field to the Document class for storing file size"

"Refactor the ExcelParserAgent to support streaming large files"

"Fix the type hints in model_loader.py"
```

**What happens:** Antigravity uses `.agent/rules/tech-stack.md` and `.agent/rules/architecture.md` automatically.

### For Workflow-Based Tasks

Use "/" commands to trigger specific workflows:

```
"/test-pipeline for ExcelParserAgent"
→ Creates comprehensive tests following test-pipeline.md

"/test-pipeline for the new PDF parser I'm about to create"
→ Same workflow, different component
```

**What happens:** Antigravity follows the step-by-step workflow in `.agent/workflows/test-pipeline.md`.

### For Skill-Specific Tasks

Just mention the topic - skills auto-trigger:

```
"Help me implement a PDF parser agent"
→ Triggers document-parser skill

"I need to add support for Word documents"
→ Triggers document-parser skill

"How do I parse PowerPoint files with VLM?"
→ Triggers document-parser skill
```

**What happens:** Antigravity loads the pattern from `.agent/skills/document-parser.md` and applies it.

## Common Prompts & Expected Behaviors

### Implementation Requests

| Prompt | Expected Behavior |
|--------|------------------|
| "Implement a PDF parser agent" | Uses document-parser skill + architecture rules |
| "Add a new pipeline stage for validation" | Uses architecture.md patterns |
| "Create a router that selects agents based on document type" | Follows BaseRouter pattern from base.py |
| "Add support for the Gemini Vision model" | Extends ModelLoader following the pattern |

### Testing Requests

| Prompt | Expected Behavior |
|--------|------------------|
| "/test-pipeline for PDFParserAgent" | Executes complete test workflow |
| "Write unit tests for the router" | Creates focused unit tests |
| "Add integration test for Excel → PDF pipeline" | Creates end-to-end test |

### Refactoring Requests

| Prompt | Expected Behavior |
|--------|------------------|
| "Refactor to use async file I/O throughout" | Applies tech-stack.md async rules |
| "Add type hints to all functions in utils/" | Enforces type hint requirements |
| "Make the model loading more efficient" | Suggests caching, lazy loading per architecture |

### Configuration Requests

| Prompt | Expected Behavior |
|--------|------------------|
| "Add Llama 3.2 Vision to models.yaml" | Follows model config schema |
| "Create a pipeline for document classification → parsing → storage" | Uses pipeline pattern from architecture.md |

## What Antigravity Knows Automatically

### From `.agent/rules/tech-stack.md` (Always Active)

- ✅ Must use Python 3.10+
- ✅ Must add type hints everywhere
- ✅ Must use Pydantic for data models
- ✅ Must use async for I/O
- ✅ Must use specific libraries (PyTorch, Transformers, openpyxl, etc.)
- ✅ Code style rules (Black, isort, Ruff)
- ✅ Import organization patterns

### From `.agent/rules/architecture.md` (Always Active)

- ✅ Abstract base class pattern
- ✅ Factory pattern for models
- ✅ Registry pattern for agents
- ✅ Pipeline composition pattern
- ✅ Dependency injection
- ✅ Error handling hierarchy
- ✅ Configuration-driven behavior

### From `GEMINI.md` (Always Active)

- ✅ Project vision and goals
- ✅ Current implementation status
- ✅ Development workflow
- ✅ Git commit conventions
- ✅ File organization rules
- ✅ Security best practices

## Quick Command Reference

### Development Commands

```bash
# Format code
black src/ tests/
isort src/ tests/

# Lint
ruff check src/ tests/ --fix

# Type check
mypy src/

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=src --cov-report=html

# Run only fast tests
pytest tests/ -v -m "not slow"

# Run only unit tests
pytest tests/unit/ -v
```

### Prompts for Common Tasks

#### Adding a New Agent

```
"Create a PDF parser agent following the same pattern as ExcelParserAgent"
→ Will use document-parser skill

"Now add comprehensive tests for the PDF parser"
→ Use: "/test-pipeline for PDFParserAgent"
```

#### Adding a New Model

```
"Add support for OpenAI GPT-4V in the model loader"
→ Will follow ModelLoader pattern from architecture.md

"Update models.yaml with GPT-4V configuration"
→ Will follow schema from models.yaml
```

#### Building Pipelines

```
"Create a pipeline that validates → routes → parses → formats documents"
→ Will use BasePipelineStage pattern

"Add a content validation stage to check extraction quality"
→ Will create new pipeline stage following pattern
```

#### Debugging & Fixes

```
"The Excel parser is failing on large files - optimize it"
→ Will suggest streaming, chunking, async improvements

"Add better error handling to the model loader"
→ Will add try-except with custom exceptions per architecture.md

"Fix type errors in agents/excel_parser_agent.py"
→ Will add/fix type hints per tech-stack.md rules
```

## Advanced Usage

### Creating Custom Workflows

You can add your own workflows to `.agent/workflows/`:

```markdown
# .agent/workflows/deploy-agent.md

> Trigger: /deploy-agent

## Steps
1. Run all tests
2. Build Docker image
3. Push to registry
4. Update k8s deployment
...
```

Then use: `/deploy-agent`

### Creating Custom Skills

Add domain-specific skills to `.agent/skills/`:

```markdown
# .agent/skills/api-endpoint.md

> Auto-triggered when: User asks about API endpoints

## Pattern for FastAPI endpoints...
```

Antigravity will automatically use it when relevant.

### Creating Custom Rules

Add project-specific rules to `.agent/rules/`:

```markdown
# .agent/rules/security.md

> Always active

## Security Requirements
- All file uploads must be scanned
- API keys must never be logged
...
```

These will always be in context.

## Tips for Effective Prompting

### ✅ Good Prompts

- "Implement a Word document parser following our architecture"
  - Clear intent, lets AI use existing patterns
  
- "Add caching to the model loader to avoid reloading"
  - Specific improvement, AI will apply architecture rules
  
- "/test-pipeline for the routing agent"
  - Uses workflow system properly

### ❌ Avoid

- "Just write some code to parse PDFs"
  - Too vague, might not follow patterns
  
- "Make it work like the other parsers"
  - Unclear which patterns to follow
  
- "Add tests" without specifying workflow
  - Better to use `/test-pipeline`

### 🎯 Best Practices

1. **Be specific about what you want:**
   - Good: "Add async file reading to the PDF parser"
   - Bad: "Make it faster"

2. **Reference existing patterns:**
   - Good: "Create a PowerPoint parser like ExcelParserAgent"
   - Bad: "Create a PowerPoint parser"

3. **Use workflows for complex tasks:**
   - Good: "/test-pipeline for PDFParserAgent"
   - Bad: "Write tests for PDF parser" (might miss steps)

4. **Ask for explanations when needed:**
   - "Explain why we use dependency injection in agents"
   - "Walk me through the model loading process"

5. **Request reviews of your code:**
   - "Review this code I wrote for the router - does it follow our architecture?"
   - "Check if my type hints are correct"

## Understanding AI Context

### What AI Sees When You Prompt

```
Your prompt: "Add a PDF parser agent"

AI receives:
├── Your prompt
├── GEMINI.md (entire file)
├── .agent/rules/tech-stack.md (entire file)
├── .agent/rules/architecture.md (entire file)
├── .agent/skills/document-parser.md (auto-loaded because "parser" mentioned)
└── Recent conversation history
```

### What AI Doesn't See (Unless You Mention It)

- Specific code files (unless you reference them)
- Test files
- Configuration files
- Recent git commits

**How to include them:**
```
"Look at src/agents/excel_parser_agent.py and create a similar PDF parser"
→ AI will fetch that file and use it as reference
```

## Troubleshooting Prompts

### When AI Suggests Wrong Pattern

```
"That approach doesn't follow our architecture rules. Please use the BaseAgent pattern from architecture.md"
```

### When AI Forgets Context

```
"Remember that we use Pydantic for all data models - please regenerate using BaseModel"
```

### When You Need Clarification

```
"Before implementing, show me the design for how this fits into our architecture"
```

## Quick Checklist Before Asking AI

Before major requests, ensure:
- [ ] You're clear on what you want
- [ ] You know which pattern to follow (or let AI suggest)
- [ ] You've specified any constraints (performance, compatibility, etc.)
- [ ] You're ready to use `/workflow` if it's a complex task

## Examples of Complex Interactions

### Multi-Step Development

```
You: "I want to add PDF support. What's the best approach?"

AI: [Suggests using document-parser skill pattern]

You: "Great, implement PDFParserAgent following that pattern"

AI: [Creates PDFParserAgent]

You: "/test-pipeline for PDFParserAgent"

AI: [Creates comprehensive tests]

You: "Now add it to the routing logic"

AI: [Updates router to handle PDF documents]
```

### Debugging Session

```
You: "ExcelParserAgent is crashing on large files"

AI: [Asks for error details]

You: [Provides stack trace]

AI: [Analyzes, suggests streaming approach]

You: "Implement that solution"

AI: [Refactors with streaming]

You: "Update tests to verify it works with large files"

AI: [Adds performance tests]
```

## Remember

- **Rules are always active** - don't repeat them in prompts
- **Workflows are for complex tasks** - use "/" commands
- **Skills auto-trigger** - just mention the topic
- **Be specific** - clear requests get better results
- **Reference patterns** - "like ExcelParserAgent" helps AI understand
- **Use the project vocabulary** - "agent", "parser", "pipeline", "VLM"

## Need Help?

Ask Antigravity:
- "What workflows are available?"
- "What skills do you have?"
- "Show me examples of using the document-parser skill"
- "Explain our architecture patterns"
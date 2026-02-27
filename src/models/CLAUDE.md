# src/models/ — VLM Implementations

Factory + registry pattern. ModelLoader dispatches by provider string.

## Adding a New Model
1. Create `src/models/your_model.py`
2. Extend `HuggingFaceBaseModel` (local) or `BaseVisionLanguageModel` (cloud)
3. Override 4 methods: `_get_model_class()`, `_get_processor_class()`,
   `_prepare_inputs(img, prompt)`, `_decode_output(inputs, generated_ids)`
4. Register in `__init__.py`: `ModelLoader.register_loader("provider", YourModel)`
5. Add config to `configs/models.yaml`

## Registered Providers
qwen, deepseek, llava, lightonocr, openai, google

## Gotchas
- **Config nesting**: quantization/max_memory live under `config["config"]`,
  not at top level. See `huggingface.py:20-21`.
- **Device mismatch**: Always call `_move_inputs_to_device()` before generate.
  CUDA device errors are silent and produce garbage output.
- **Quantization optional**: `bitsandbytes` is imported inside try/except.
  Falls back to full precision if missing. `bnb_4bit_quant_type`: "nf4" or "fp4".
- **max_memory values are strings**: `{"0": "10GB", "cpu": "5GB"}` — not ints.
- **Memory cleanup**: `torch.cuda.empty_cache()` after load, after process,
  after unload. `use_cache=False` always set for memory efficiency.
- **Image resize**: Default max 768px via `_resize_image()`. Large PDFs will
  OOM without this.
- **model.process() is sync** — callers must wrap in `run_in_executor()`.

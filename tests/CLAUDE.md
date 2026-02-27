# tests/ — Testing Conventions

## Framework
pytest + pytest-asyncio + pytest-cov. Coverage configured in `pyproject.toml`.

## Structure
- `tests/unit/` — Unit tests (mock all external I/O)
- `tests/integration/` — Integration tests (planned, not yet created)
- Test file maps to source: `src/ingestion/queue_manager.py` →
  `tests/unit/test_ingestion_queue.py`

## Async Tests
- Use `@pytest.mark.asyncio` decorator + `async def test_*()`
- Mock async methods with `AsyncMock`, sync with `Mock(spec=BaseClass)`

## Mocking Pattern (from existing tests)
```python
with patch("src.ingestion.queue_manager.session_manager") as mock_manager:
    mock_session = AsyncMock()
    mock_manager.session.return_value.__aenter__.return_value = mock_session
```
- Always mock DB sessions — never hit real database
- Always mock model inference — never load real models
- Use `MagicMock(spec=IngestionJob)` for ORM objects

## Fixtures
- Define reusable fixtures in `conftest.py` (create as needed — none exist yet)
- Keep fixtures minimal: mock_session, mock_service, sample_document

## TDD
Write failing test FIRST, then implement. Test file must exist before source.

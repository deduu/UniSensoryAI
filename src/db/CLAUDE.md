# src/db/ — Async Database Layer

SQLAlchemy 2.0 async with read/write engine split.

## Session Pattern
```python
async with session_manager.session() as db:
    # ... do work ...
    await db.commit()  # CALLER MUST COMMIT
```
- Auto-rollback on exception (silent — no logging)
- Read-only: `session_manager.session(read_only=True)` — smaller pool (10 vs 20)
- `expire_on_commit=False` on write sessions, `autoflush=False`

## ORM Conventions
- Use `Mapped[]` + `mapped_column()` syntax (SQLAlchemy 2.0, not legacy `Column`)
- Table names auto-generated: `IngestionJob` → `ingestionjobs`
- Enums: `Enum(IngestionStatus, native_enum=False)` for DB portability
- Timestamps: `created_at` (server_default=utc_now), `updated_at` (onupdate=utc_now)
- Foreign keys: `ondelete="SET NULL"` for soft references

## Relationships
- Use `selectinload()` only in targeted queries (e.g., get_by_id with children)
- Default is lazy loading — avoid N+1 by being explicit in list queries

## Global Instance
- `session_manager` is `None` until `init_db(write_url)` is called
- `get_db()` is the FastAPI dependency — yields a session from session_manager
- Always check `session_manager is not None` before use in background workers

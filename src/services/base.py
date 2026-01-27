from typing import Type, TypeVar, Generic, Any, Optional, Sequence
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from .exceptions import NotFoundException, IntegrityException

T = TypeVar('T')

class BaseService(Generic[T]):
    def __init__(self, db: AsyncSession, model: Type[T]):
        self.db = db
        self.model = model

    async def get_by_id(self, item_id: Any, raise_not_found: bool = True) -> Optional[T]:
        result = await self.db.get(self.model, item_id)
        if not result and raise_not_found:
            raise NotFoundException(self.model.__name__, item_id)
        return result

    async def list(self, limit: int = 100, offset: int = 0) -> Sequence[T]:
        stmt = select(self.model).limit(limit).offset(offset)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def create(self, **data: Any) -> T:
        obj = self.model(**data)
        self.db.add(obj)
        try:
            await self.db.flush()
            await self.db.refresh(obj)
            return obj
        except IntegrityError:
            raise IntegrityException(f"Failed to create {self.model.__name__}")

    async def update(self, item_id: Any, **data: Any) -> T:
        obj = await self.get_by_id(item_id)
        # Type check for mypy: obj is T which we assume matches Base functionality roughly, 
        # but T is generic. In SQLAlchemy models, this is fine.
        if obj is None: # Should be caught by get_by_id if raise_not_found=True
             raise NotFoundException(self.model.__name__, item_id)

        for key, value in data.items():
            setattr(obj, key, value)
        try:
            await self.db.flush()
            await self.db.refresh(obj)
            return obj
        except IntegrityError:
             raise IntegrityException(f"Failed to update {self.model.__name__} {item_id}")

    async def delete(self, item_id: Any) -> bool:
        obj = await self.get_by_id(item_id)
        if obj:
            await self.db.delete(obj)
            await self.db.flush()
            return True
        return False

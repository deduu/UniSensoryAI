from sqlalchemy.orm import DeclarativeBase, declared_attr
from datetime import datetime, timezone

class Base(DeclarativeBase):
    @declared_attr.directive
    def __tablename__(cls) -> str:
        return cls.__name__.lower() + 's'
    
    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

def utc_now():
    return datetime.now(timezone.utc)

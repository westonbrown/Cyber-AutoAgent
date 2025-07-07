from .session import engine
from .models import Base


def init_db() -> None:
    """Create tables if they’re missing (TODO: Remove this. Here for convenience)."""
    Base.metadata.create_all(bind=engine)

from __future__ import annotations

from loguru import logger

# Basic configuration can be extended later
logger.add(
	"reports_app.log",
	rotation="10 MB",
	retention="7 days",
	enqueue=True,
	level="INFO",
)

__all__ = ["logger"] 
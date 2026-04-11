"""
Initialization script: creates DB tables, indexes knowledge into Qdrant,
and pulls the Ollama model if not already present.
"""
import asyncio
import logging
import sys

import httpx

from app.config import settings
from app.database import engine
from app.models import Base
from app.agent.rag import index_knowledge

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def create_tables() -> None:
    logger.info("Creating database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created.")


async def pull_model() -> None:
    model = settings.ollama_model
    base = settings.ollama_base_url
    logger.info("Checking if model '%s' is available...", model)

    async with httpx.AsyncClient(timeout=600.0) as client:
        try:
            resp = await client.get(f"{base}/api/tags")
            resp.raise_for_status()
            models = [m["name"] for m in resp.json().get("models", [])]
            if model in models:
                logger.info("Model '%s' already pulled.", model)
                return
        except Exception:
            logger.warning("Could not check existing models, will attempt pull.")

        logger.info("Pulling model '%s' (this may take several minutes)...", model)
        resp = await client.post(
            f"{base}/api/pull",
            json={"name": model, "stream": False},
            timeout=1800.0,
        )
        resp.raise_for_status()
        logger.info("Model '%s' pulled successfully.", model)


async def main() -> None:
    await create_tables()

    logger.info("Indexing knowledge base into Qdrant...")
    index_knowledge()
    logger.info("Knowledge base indexed.")

    await pull_model()

    logger.info("Initialization complete.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error("Init failed: %s", e, exc_info=True)
        sys.exit(1)

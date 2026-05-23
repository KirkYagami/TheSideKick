import os
import logging

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from utils.env_helper import load_environment


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


DEFAULT_MEMORY = MemorySaver


async def get_persistence_memory_type():
    """
    Initialize and return the configured LangGraph checkpointer.

    Supported persistence types:
    - in_memory
    - sqlite

    Returns:
        A valid LangGraph checkpoint saver instance.
    """

    load_environment()

    persistence_type = os.getenv(
        "PERSISTENCE_TYPE",
        "in_memory",
    ).strip().lower()

    valid_types = {
        "in_memory",
        "sqlite",
    }

    if persistence_type not in valid_types:

        logger.warning(
            "Invalid PERSISTENCE_TYPE '%s'. "
            "Falling back to in_memory.",
            persistence_type,
        )

        persistence_type = "in_memory"

    # -----------------------------
    # In-Memory Persistence
    # -----------------------------

    if persistence_type == "in_memory":

        logger.info(
            "Using in-memory persistence."
        )

        return MemorySaver()

    # -----------------------------
    # SQLite Persistence
    # -----------------------------

    if persistence_type == "sqlite":

        db_path = os.getenv(
            "SQLITE_DB_PATH",
            "./memory.db",
        )

        try:

            # Ensure directory exists
            db_dir = os.path.dirname(db_path)

            if db_dir:

                os.makedirs(
                    db_dir,
                    exist_ok=True,
                )

            logger.info(
                "Using SQLite persistence at: %s",
                db_path,
            )

            # IMPORTANT:
            # from_conn_string() returns an async
            # context manager in latest LangGraph

            saver_context = (
                AsyncSqliteSaver.from_conn_string(
                    db_path
                )
            )

            saver = await saver_context.__aenter__()

            logger.info(
                "SQLite persistence initialized successfully."
            )

            return saver

        except Exception as e:

            logger.exception(
                "Failed to initialize SQLite persistence: %s",
                e,
            )

            logger.warning(
                "Falling back to in-memory persistence."
            )

            return DEFAULT_MEMORY()

    # -----------------------------
    # Final Fallback
    # -----------------------------

    logger.warning(
        "Unexpected persistence configuration. "
        "Using in-memory persistence."
    )

    return DEFAULT_MEMORY()


if __name__ == "__main__":

    import asyncio

    async def main():

        persistence = (
            await get_persistence_memory_type()
        )

        logger.info(
            "Persistence initialized: %s",
            persistence.__class__.__name__,
        )

    asyncio.run(main())
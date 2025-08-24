import os
import logging
import sqlite3
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from utils.env_helper import load_environment

# Configure logging
logging.basicConfig(level=logging.INFO)

# Default persistence type
DEFAULT_MEMORY = MemorySaver

def get_persistence_memory_type():
    """Determine the persistence memory type based on environment variables.
    
    Returns:
        A persistence memory instance (e.g., MemorySaver, SqliteSaver).
    
    Raises:
        sqlite3.Error: If SQLite connection fails.
    """
    load_environment()
    
    persistence_type = os.getenv("PERSISTENCE_TYPE")
    if persistence_type not in ["in_memory", "sqlite", None]:
        logging.warning(f"Invalid PERSISTENCE_TYPE '{persistence_type}', using default")
    
    if persistence_type == "in_memory":
        return MemorySaver()
    elif persistence_type == "sqlite":
        db_path = os.getenv("SQLITE_DB_PATH", "memory.db")
        try:
            conn = sqlite3.connect(db_path, check_same_thread=False)
            return SqliteSaver(conn)
        except sqlite3.Error as e:
            logging.error(f"Failed to connect to SQLite database {db_path}: {e}")
            return DEFAULT_MEMORY()
    else:
        return DEFAULT_MEMORY()

if __name__ == "__main__":
    persistence = get_persistence_memory_type()
    logging.info(f"Using persistence type: {persistence.__class__.__name__}")
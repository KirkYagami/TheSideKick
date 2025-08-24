from dotenv import load_dotenv

def load_environment():
    """Load environment variables with override enabled."""
    load_dotenv(override=True)
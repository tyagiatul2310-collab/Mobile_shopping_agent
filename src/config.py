import os
from dotenv import load_dotenv
from src.utils.logger import setup_logging

load_dotenv()

# Initialize logging
logger = setup_logging(log_level="INFO", log_file="logs/app.log")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

GEMINI_FLASH = "gemini-2.0-flash"  
GEMINI_PRO = "gemini-2.5-pro"      


def get_gemini_url(model: str = GEMINI_FLASH) -> str:
    """Get Gemini API URL for specified model."""
    return GEMINI_BASE_URL.format(model=model)

TABLE_SCHEMA = [
    'Company Name', 'Model Name', 'Processor', 'Launched Year', 'User Rating.1', 'User Review.1',
    'User Camera Rating', 'User Battery Life Rating', 'User Design Rating', 'User Display Rating',
    'User Performance Rating', 'Memory (GB)', 'Mobile Weight (g)', 'RAM (GB)', 'Front Camera (MP)',
    'Back Camera (MP)', 'Battery Capacity (mAh)', 'Launched Price (INR)', 'Screen Size (inches)'
]

CSV_PATH = "data/mobiles_india_preprocessed.csv"
DB_PATH = "data/mobiles_india_preprocessed.db"
TABLE_NAME = "mobiles_india_preprocessed"

PINECONE_INDEX_NAME = "mobile-names"
EMBEDDING_MODEL = "models/text-embedding-004"
EMBEDDING_DIM = 768

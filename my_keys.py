import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("Error: No se encontró la variable GEMINI_API_KEY. Configúrala en tu entorno o archivo .env")
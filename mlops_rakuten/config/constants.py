from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

# Load environment variables from .env file if it exists
load_dotenv()

# Paths
PROJ_ROOT = Path(__file__).resolve().parents[2]
logger.info(f"PROJ_ROOT path is: {PROJ_ROOT}")

DATA_DIR = PROJ_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
RAKUTEN_DATA_DIR = RAW_DATA_DIR / "rakuten"
SEEDS_DATA_DIR = RAKUTEN_DATA_DIR / "seeds"
INTERIM_DATA_DIR = DATA_DIR / "interim"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
EXTERNAL_DATA_DIR = DATA_DIR / "external"
UPLOADS_DATA_DIR = RAW_DATA_DIR / "uploads"

MODELS_DIR = PROJ_ROOT / "models"

REPORTS_DIR = PROJ_ROOT / "reports"

MODULE_DIR = PROJ_ROOT / "mlops_rakuten"
AUTH_DIR = MODULE_DIR / "auth"
CONFIG_DIR = MODULE_DIR / "config"
CONFIG_FILE_PATH = CONFIG_DIR / "config.yml"

logger.info(f"RAW_DATA_DIR is {RAW_DATA_DIR}")
logger.info(f"MODULE_DIR is {MODULE_DIR}")
logger.info(f"MODELS_DIR is {MODELS_DIR}")


# fichier de logs
LOGS_DIR = PROJ_ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# fichier complet de logs
logger.add(
    LOGS_DIR / "logs.log",
    rotation="10 MB",
    retention="30 days",
    compression="zip",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {name}:{function}:{line} | {level} | {message}",
)

# Fichier erreurs (erreurs uniquement avec traceback)
logger.add(
    LOGS_DIR / "errors.log",
    rotation="10 MB",
    retention="90 days",
    compression="zip",
    level="ERROR",
    format="{time:YYYY-MM-DD HH:mm:ss} | {name}:{function}:{line} | {level} | {message}\n{exception}",
    backtrace=True,
    diagnose=True,
)


# If tqdm is installed, configure loguru with tqdm.write
# https://github.com/Delgan/loguru/issues/135
try:
    from tqdm import tqdm

    logger.remove(0)
    logger.add(lambda msg: tqdm.write(msg, end=""), colorize=True)
except ModuleNotFoundError:
    pass

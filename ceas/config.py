from pathlib import Path

from dotenv import load_dotenv
from loguru import logger
import json
# Load environment variables from .env file if it exists
load_dotenv()

# Paths
PROJ_ROOT = Path(__file__).resolve().parents[1]
logger.info(f"PROJ_ROOT path is: {PROJ_ROOT}")

DATA_DIR = PROJ_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
INTERIM_DATA_DIR = DATA_DIR / "interim"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
EXTERNAL_DATA_DIR = DATA_DIR / "external"
MODELS_DIR = PROJ_ROOT / "models"
REPORTS_DIR = PROJ_ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"

# gform_map.json is a json file that contains the mapping of columns in the google form to the columns in the data
with open(PROJ_ROOT / "gform_map.json" ) as f:
    GFORM_MAP = json.load(f)
GFORM_COLS_MAP = GFORM_MAP["cols_map"]
SCHOOL_NAME_MAP = GFORM_MAP["school_name_map"]
ED_MAPPING = GFORM_MAP["ED_MAPPING"]

# necesitamos el inverso de ED_MAPPING
ED_MAPPING_INV = {v: k for k, v in ED_MAPPING.items()}
# config_categories.json is a json file that contains categories for some variables

with open(PROJ_ROOT / "config_categories.json" ) as f:
    CONFIG_CATEGORIES = json.load(f)
NIVELES_EDUCATIVOS = CONFIG_CATEGORIES["niveles_educativos"]
CURSOS_POR_NIVEL_EDUCATIVO = CONFIG_CATEGORIES["cursos_por_nivel_educativo"]

ASIGNATURAS_POR_NIVEL_EDUCATIVO = CONFIG_CATEGORIES["asignaturas_por_nivel_educativo"]

# Mapping of Spanish weekdays to English for availability parsing
# DAY_MAP = {
#     "Lunes": "Monday",
#     "Martes": "Tuesday",
#     "Miércoles": "Wednesday",
#     "Jueves": "Thursday",
#     "Viernes": "Friday"
# }
DAY_MAP = {
    "Monday": "Lunes",
    "Tuesday": "Martes",
    "Wednesday": "Miércoles",
    "Thursday": "Jueves",
    "Friday": "Viernes"
}
# Subject normalization: allowed subjects and special-case multi-comma subject
ALLOWED_SUBJECTS = {
    "Artes Visuales",
    "Biología",
    "Ciencias Naturales",
    "Ciencias Sociales",
    "Educación Física",
    "Filosofía",
    "Física",
    "Formación Ciudadana",
    "Historia",
    "Inglés",
    "Lenguaje y Comunicación",
    "Matemática",
    "Música y Artes",
    "Química",
    "TP - Contabilidad"
}
# When a subject string contains this full text (including commas), treat as single subject
SPECIAL_SUBJECT = "Historia, geografía y Ciencias Sociales"


# If tqdm is installed, configure loguru with tqdm.write
# https://github.com/Delgan/loguru/issues/135
try:
    from tqdm import tqdm

    logger.remove(0)
    logger.add(lambda msg: tqdm.write(msg, end=""), colorize=True)
except ModuleNotFoundError:
    pass

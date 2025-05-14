"""
Constants for the Aula MCP integration
"""
from enum import Enum

# API constants
API_BASE = "https://www.aula.dk/api/v"
API_VERSION = "20"
MIN_UDDANNELSE_API = "https://api.minuddannelse.net/aula"
MEEBOOK_API = "https://app.meebook.com/aulaapi"
SYSTEMATIC_API = "https://systematic-momo.dk/api/aula"
EASYIQ_API = "https://api.easyiq.dk/api/aula"
LOGIN_URL = "https://login.aula.dk/auth/login.php"

# Calendar constants
DEFAULT_CALENDAR_DAYS = 14

# Update constants
MIN_TIME_BETWEEN_UPDATES_MINUTES = 10

# Feature flags
class Features(str, Enum):
    SCHOOL_SCHEDULE = "schoolschedule"
    UGEPLAN = "ugeplan"
    MU_OPGAVER = "mu_opgaver" 
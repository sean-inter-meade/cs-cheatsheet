from __future__ import annotations

import os

INTERCOM_API_TOKEN = os.getenv("INTERCOM_API_TOKEN", "")
INTERCOM_API_BASE = os.getenv("INTERCOM_API_BASE", "https://api.intercom.io")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "300"))
CACHE_MAX_SIZE = int(os.getenv("CACHE_MAX_SIZE", "100"))
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "30"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))

# Custom Data Attribute key names — must match the exact attribute name in Intercom
CDA_SEGMENT_KEY = os.getenv("CDA_SEGMENT_KEY", "Support team customer segment")
CDA_REGION_KEY = os.getenv("CDA_REGION_KEY", "Support team customer region")
CDA_SETTINGS_ACCESS_KEY = os.getenv("CDA_SETTINGS_ACCESS_KEY", "Can access workspace settings")
CDA_IMPERSONATION_KEY = os.getenv("CDA_IMPERSONATION_KEY", "Has impersonation consent")
CDA_COMPANY_CREATED_AT_KEY = os.getenv("CDA_COMPANY_CREATED_AT_KEY", "Company created at")

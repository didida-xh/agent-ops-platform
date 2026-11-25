"""配置
加载项目根目录 .env，导出 PG_DSN / REDIS_URL / SQL_DIR。
"""


import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

PG_DSN = os.getenv("PG_DSN", "postgresql://agent:agent@localhost:5434/agent_service")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6380/0")
SQL_DIR = ROOT / "sql"

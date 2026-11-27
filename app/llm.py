"""模型客户端

读取 .env，构造 ChatOpenAI（temperature=0、显式超时）。
"""


import os

import httpx
from langchain_openai import ChatOpenAI

from app.config import ROOT  # noqa: F401  确保 .env 已加载

llm = ChatOpenAI(
    model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    temperature=0,
    http_client=httpx.Client(trust_env=False, timeout=60),
)
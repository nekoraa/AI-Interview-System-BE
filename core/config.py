import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # API 密钥，优先从环境变量读取
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "YOUR_DEFAULT_API_KEY")

    # Gemini 模型名称
    MODEL_NAME: str = "gemini-2.5-flash-native-audio-preview-12-2025"

    # Gemini WebSocket 地址模板
    GEMINI_WS_URL: str = "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key={api_key}"

    class Config:
        env_file = ".env"


settings = Settings()
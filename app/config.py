from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    APP_NAME: str = "智慧能源园区用能与碳账服务"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    SECRET_KEY: str = "your-secret-key-here-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    DATABASE_URL: str = "sqlite:///./smart_energy_park.db"

    ELECTRICITY_PEAK_PRICE: float = 1.2
    ELECTRICITY_FLAT_PRICE: float = 0.8
    ELECTRICITY_VALLEY_PRICE: float = 0.4
    GAS_PRICE: float = 3.5
    HEAT_PRICE: float = 35.0
    WATER_PRICE: float = 4.5

    CARBON_FACTOR_ELECTRICITY: float = 0.5810
    CARBON_FACTOR_GAS: float = 2.1622
    CARBON_FACTOR_HEAT: float = 0.1100
    CARBON_FACTOR_WATER: float = 0.9100

    DEMAND_RESPONSE_PRICE: float = 0.5

    class Config:
        env_file = ".env"


settings = Settings()

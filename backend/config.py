from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    anthropic_api_key: str
    db_host: str = "localhost"
    db_port: int = 3306
    db_user: str
    db_password: str
    db_name: str = "tertulia_db"


settings = Settings()

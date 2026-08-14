from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://cyberlearn:cyberlearn@localhost:55432/cyberlearn"
    redis_url: str = "redis://localhost:6380/0"
    cookie_name: str = "cl_session"
    cookie_secure: bool = True
    session_ttl_pending_seconds: int = 300
    session_ttl_authenticated_seconds: int = 60 * 60 * 24 * 7
    login_max_attempts: int = 5
    login_lockout_seconds: int = 900
    labs_terminal_relay_port: int = 8765

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()

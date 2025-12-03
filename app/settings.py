import os
import sys
import logging
from pydantic import ValidationError
from pydantic_settings import BaseSettings
from urllib.parse import quote_plus

config_logger = logging.getLogger("config_loader")
config_logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
if not config_logger.handlers:
    config_logger.addHandler(stream_handler)


# --- Main Settings Class Definition ---
class Settings(BaseSettings):
    model_config = {
        'extra': 'ignore'
    }

    MYSQL_DATABASE: str
    MYSQL_USER: str
    MYSQL_PASSWORD: str
    MYSQL_HOST: str

    TWILIO_SID: str
    TWILIO_KEY: str
    TWILIO_FROM: str
    TWILIO_TO: str

    @property
    def database_url(self) -> str:
        """
        Assembles the database URL for SQLAlchemy with PyMySQL driver.
        Correctly URL-encodes the password to handle special characters.
        """
        # URL-encode the password to handle special characters
        encoded_password = quote_plus(self.MYSQL_PASSWORD)

        # Assemble the full URL for SQLAlchemy with PyMySQL driver
        return f"mysql+pymysql://{self.MYSQL_USER}:{encoded_password}@{self.MYSQL_HOST}:3306/{self.MYSQL_DATABASE}"


def get_settings() -> Settings:
    """
    Tries to create the main Settings object. If it fails due to missing
    core variables, it logs a fatal error and exits the application.
    """
    try:
        return Settings()
    except ValidationError as e:
        missing_vars = [
            err['loc'][0].upper()
            for err in e.errors()
            if err['type'] == 'missing' and err['loc'][0] in Settings.model_fields
        ]
        if missing_vars:
            config_logger.critical(
                f"🚨 START CANCELED: Missing environment variables: {', '.join(missing_vars)}")
        else:
            config_logger.critical(
                "🚨 START CANCELED: All required environment variables are present, but settings failed to load.")
        sys.exit(1)

# Cached settings instance
settings = get_settings()

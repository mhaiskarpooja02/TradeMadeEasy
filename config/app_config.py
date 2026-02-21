import os

class AppConfig:
    """
    Controls application environment (DEV / PROD)

    - DEV  → API allowed
    - PROD → Controlled mode
    """

    ENV = os.getenv("APP_ENV", "DEV")  # default DEV

    @classmethod
    def is_dev(cls):
        return cls.ENV == "DEV"

    @classmethod
    def is_prod(cls):
        return cls.ENV == "PROD"

    @classmethod
    def set_env(cls, value: str):
        cls.ENV = value

from pydantic import BaseSettings, Field, SecretStr


class AWSConfig(BaseSettings):
    region: str = Field(..., env='AWS_REGION')
    access_key: SecretStr = Field(..., env='AWS_ACCESS_KEY_ID')
    secret_access_key: SecretStr = Field(..., env='AWS_SECRET_ACCESS_KEY')


class DynamoDBConfig(BaseSettings):
    port: str = Field(..., env='DYNAMODB_PORT')
    host: SecretStr = Field(..., env='DYNAMODB_HOST')

    @property
    def endpoint_url(self) -> str:
        return f'{self.host.get_secret_value()}:{self.port}'


class TelegramConfig(BaseSettings):
    bot_token: SecretStr = Field(..., env='TG_BOT_TOKEN')
    webhook_host: str = Field(..., env='API_URL')
    webhook_port: str = Field(..., env='WEBHOOK_PORT')
    webhook_url_path: SecretStr = Field(..., env='WEBHOOK_URL_PATH')

    @property
    def webhook_url(self) -> str:
        return f'{self.webhook_host}:{self.webhook_port}{self.webhook_url_path.get_secret_value()}'


class ApiConfig(BaseSettings):
    host: str = Field(..., env='WEBAPP_HOST')
    port: int = Field(..., env='WEBAPP_PORT')
    notifications_path: SecretStr = Field(..., env='NOTIFICATIONS_PATH')

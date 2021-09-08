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


class API(BaseSettings):
    url: str = Field(..., env='API_URL')
    path: SecretStr = Field(..., env='NOTIFICATIONS_PATH')

    @property
    def api_url(self) -> str:
        return f'{self.url}/{self.path.get_secret_value()}'

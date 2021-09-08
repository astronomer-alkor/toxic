from pydantic import BaseSettings, Field, SecretStr


class AWSConfig(BaseSettings):
    region: str = Field(..., env='AWS_REGION')
    access_key: SecretStr = Field(..., env='AWS_ACCESS_KEY_ID')
    secret_access_key: SecretStr = Field(..., env='AWS_SECRET_ACCESS_KEY')


class DynamoDBConfig(BaseSettings):
    port: str = Field(..., env='DYNAMODB_PORT')
    host: SecretStr = Field(..., env='DYNAMODB_HOST')

    @property
    def endpoint_url(self):
        return f'{self.host.get_secret_value()}:{self.port}'


class WhaleAlertsConfig(BaseSettings):
    api_key: SecretStr = Field(..., env='WHALE_ALERTS_API_KEY')

import hashlib
import hmac
import json
from typing import Any, Dict
from urllib.parse import urlencode, quote


def convert_payload_to_params(payload: Dict[str, Any]) -> str:
    payload = json.loads(json.dumps(payload, sort_keys=True))
    payload = {k: quote(v) if isinstance(v, str) else v for k, v in payload.items()}
    return urlencode(payload)


def generate_signature(secret_api_key: str, params: str):
    return hmac.new(secret_api_key.encode(), msg=params.encode(), digestmod=hashlib.sha256).hexdigest()

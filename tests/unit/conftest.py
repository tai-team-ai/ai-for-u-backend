import os
import pytest
from fixtures.test_settings import lambda_settings, api_gateway_settings, dynamodb_settings

os.environ["FRONTEND_CORS_URL"] = "https://d22zhq6xynxzgi.cloudfront.net"

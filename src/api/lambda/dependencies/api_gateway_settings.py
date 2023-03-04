from pydantic import BaseSettings, validator
from typing import Dict, List, Any, Optional

class APIGatewaySettings(BaseSettings):
    """Lambda Environment Model"""
    openai_route_prefix: str = "openai"
    deployment_stage: str = "dev"
    frontend_cors_url: str = "https://aiforu.com"
    development_cors_urls: str = ""

    class Config:
        case_sensitive = False

    @validator("development_cors_urls")
    def validate_cors_urls(cls, development_cors_urls: Optional[str], values: Dict[str, Any]) -> Optional[str]:
        """Validate the cors urls."""
        if values['deployment_stage'] == 'dev' and development_cors_urls is None:
            return "http://localhost:3000"
        return development_cors_urls
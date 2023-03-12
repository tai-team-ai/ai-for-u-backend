from pydantic import BaseSettings, validator
from typing import Dict, List, Any, Optional
from enum import Enum


class DeploymentStage(Enum):
    """Deployment Stage Enum"""
    DEVELOPMENT = "dev"
    PRODUCTION = "prod"


class APIGatewaySettings(BaseSettings):
    """Lambda Environment Model"""
    openai_route_prefix: str = "openai"
    deployment_stage: DeploymentStage = DeploymentStage.DEVELOPMENT
    frontend_cors_url: str = "https://aiforu.com"
    development_cors_url: str = ""

    class Config:
        case_sensitive = False
        use_enum_values = True

    @validator("development_cors_url")
    def validate_cors_urls(cls, development_cors_url: Optional[str], values: Dict[str, Any]) -> Optional[str]:
        """Validate the cors urls."""
        if values['deployment_stage'] == 'dev' and development_cors_url is None:
            return "http://localhost:3000"
        return development_cors_url

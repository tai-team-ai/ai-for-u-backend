import logging
import os
import sys
import traceback
from openai.error import RateLimitError
from mangum import Mangum
from uuid import UUID
from fastapi import FastAPI, APIRouter, Request, status , Response
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError




dir_name = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(dir_name, "../dependencies"))
sys.path.append(dir_name)
from api_gateway_settings import APIGatewaySettings, DeploymentStage
from ai_tools_lambda_settings import AIToolsLambdaSettings
from routers import ( 
    text_revisor,
    cover_letter_writer,
    catchy_title_creator,
    sandbox_chatgpt,
    text_summarizer
)
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), "utils"))
from utils import prepare_response, UserTokenNotFoundError, initialize_openai, AUTHENTICATED_USER_ENV_VAR_NAME, UUID_HEADER_NAME


API_DESCRIPTION = """
This is the API for the AI for U project. It is a collection of endpoints that
use OpenAI's GPT-3 API to generate text. All requests must include a uuid header.
This uuid is used to check if the user is authenticated and to track usage of the API.
"""

logger = logging.getLogger()
logger.setLevel(logging.INFO)


lambda_settings = AIToolsLambdaSettings()
api_gateway_settings = APIGatewaySettings()
router = APIRouter()


@router.get(f"/status")
def get_status(request: Request, response: Response):
    """Return status okay."""
    response_body = {"status": "ok"}
    return response_body

def get_error_message(error: Exception) -> str:
    """Return error message."""
    traceback_str = "\n".join(traceback.format_exception(type(error), error, error.__traceback__))
    logger.error(traceback_str)
    if api_gateway_settings.deployment_stage == DeploymentStage.DEVELOPMENT.value:
        return traceback_str
    return str(error)

def get_error_response(request: Request, content: dict) -> Response:
    """Return error response."""
    response = JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=content
    )
    prepare_response(response, request)
    return response

def handle_request_validation_error(request: Request, exc: RequestValidationError):
    """Handle exception."""
    msg = get_error_message(exc)
    content = {"Validation Exception": msg}
    return get_error_response(request, content)

def handle_user_token_error(request: Request, exc: UserTokenNotFoundError):
    """Handle exception."""
    msg = get_error_message(exc)
    content = {"userTokenException": msg}
    return get_error_response(request, content)

def handle_generic_exception(request: Request, exc: Exception):
    """Handle exception."""
    msg = get_error_message(exc)
    content = {"Exception Raised": msg}
    return get_error_response(request, content)

def handle_rate_limit_exception(request: Request, exc: RateLimitError):
    """Handle exception."""
    msg = get_error_message(exc)
    content = {"Rate Limit Exception": msg}
    return get_error_response(request, content)


def create_fastapi_app():
    """Create FastAPI app."""
    root_path = f"/{api_gateway_settings.deployment_stage}"
    if api_gateway_settings.deployment_stage == DeploymentStage.LOCAL.value:
        root_path = ""

    app = FastAPI(
        root_path=root_path,
        docs_url=f"/{api_gateway_settings.openai_route_prefix}/docs",
        openapi_url=f"/{api_gateway_settings.openai_route_prefix}/openapi.json",
        redoc_url=None,
        description=API_DESCRIPTION,
    )

    @app.middleware("http")
    async def check_if_header_is_present(request: Request, call_next):
        """Check if user is authenticated."""
        path = request.url.path
        allowed_paths = {
            f"{root_path}/{api_gateway_settings.openai_route_prefix}/docs",
            f"{root_path}/{api_gateway_settings.openai_route_prefix}/openapi.json",
        }
        uuid_str = request.headers.get(UUID_HEADER_NAME)
        logger.info("uuid_str: %s", uuid_str)
        try:
            UUID(uuid_str, version=4)
        except Exception:
            if path not in allowed_paths:
                raise UserTokenNotFoundError("User token not found.")
        authenticated = True
        if authenticated:
            os.environ[AUTHENTICATED_USER_ENV_VAR_NAME] = "TRUE"
        else:
            os.environ[AUTHENTICATED_USER_ENV_VAR_NAME] = "FALSE"
        response = await call_next(request)
        prepare_response(response, request)
        return response


    routers = [
        router,
        text_summarizer.router,
        text_revisor.router,
        catchy_title_creator.router,
        cover_letter_writer.router,
        sandbox_chatgpt.router
    ] 
    initialize_openai()
    for router_ in routers:
        add_router_with_prefix(app, router_, f"/{api_gateway_settings.openai_route_prefix}")
    app.add_exception_handler(RequestValidationError, handle_request_validation_error)
    app.add_exception_handler(Exception, handle_generic_exception)
    app.add_exception_handler(UserTokenNotFoundError, handle_user_token_error)
    app.add_exception_handler(RateLimitError, handle_rate_limit_exception)
    
    return app

def add_router_with_prefix(app: FastAPI, router: APIRouter, prefix: str) -> None:
    """Add router with prefix."""
    app.include_router(router, prefix=prefix)

def lambda_handler(event, context):
    """Lambda handler that starts a FastAPI server with uvicorn."""
    app = create_fastapi_app()
    handler = Mangum(app=app)
    return handler(event, context)

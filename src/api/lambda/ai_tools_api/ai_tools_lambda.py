import logging
import os
import sys
from mangum import Mangum
from fastapi import FastAPI, APIRouter, Request, status , Response
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError


dir_name = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(dir_name, "../dependencies"))
sys.path.append(dir_name)
from api_gateway_settings import APIGatewaySettings
from ai_tools_lambda_settings import AIToolsLambdaSettings
from routers import note_summarizer, text_revisor, \
    resignation_email_generator, catchy_title_creator, \
    sales_inquiry_email_generator, dalle_prompt_coach, sandbox_chatgpt
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), "utils"))
from utils import prepare_response, UserTokenNotFoundError, initialize_openai, CamelCaseModel,\
                    log_to_s3, authenticate_user


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

def handle_request_validation_error(request: Request, exc: RequestValidationError):
    """Handle exception."""
    logger.error(exc)
    response = JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"Validation Exception": str(exc)}
    )
    prepare_response(response, request)
    return response

def handle_user_token_error(request: Request, exc: UserTokenNotFoundError):
    """Handle exception."""
    logger.error(exc)
    response = JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"userTokenException": str(exc)}
    )
    prepare_response(response, request)
    return response

def handle_generic_exception(request: Request, exc: Exception):
    """Handle exception."""
    logger.error(exc)
    response = JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"Exception Raised": str(exc)}
    )
    prepare_response(response, request)
    return response


def create_fastapi_app():
    """Create FastAPI app."""
    app = FastAPI(
        root_path=f"/{api_gateway_settings.deployment_stage}",
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
            f"/{api_gateway_settings.deployment_stage}/{api_gateway_settings.openai_route_prefix}/docs",
            f"/{api_gateway_settings.deployment_stage}/{api_gateway_settings.openai_route_prefix}/openapi.json",
        }
        if request.headers.get("UUID") is None or request.headers.get("UUID") == "":
            if path not in allowed_paths:
                raise UserTokenNotFoundError(f"{path}\n{allowed_paths}User identifier not found in request headers.")
        response = await call_next(request)
        prepare_response(response, request)
        return response


    routers = [
        router,
        note_summarizer.router,
        # text_revisor.router,
        # catchy_title_creator.router,
        # resignation_email_generator.router,
        # sales_inquiry_email_generator.router,
        # dalle_prompt_coach.router,
        sandbox_chatgpt.router
    ] 
    for router_ in routers:
        add_router_with_prefix(app, router_, f"/{api_gateway_settings.openai_route_prefix}")
    app.add_exception_handler(RequestValidationError, handle_request_validation_error)
    app.add_exception_handler(Exception, handle_generic_exception)
    
    return app

def add_router_with_prefix(app: FastAPI, router: APIRouter, prefix: str) -> None:
    """Add router with prefix."""
    app.include_router(router, prefix=prefix)

def lambda_handler(event, context):
    """Lambda handler that starts a FastAPI server with uvicorn."""
    app = create_fastapi_app()
    handler = Mangum(app=app)
    return handler(event, context)
    

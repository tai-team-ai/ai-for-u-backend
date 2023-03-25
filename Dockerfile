FROM python:3.9-slim-buster AS install
LABEL api_stage=1

WORKDIR /app

COPY src/api/lambda/ai_tools_api/requirements-lambda.txt ./tmp/requirements-lambda.txt
RUN pip install -r ./tmp/requirements-lambda.txt
RUN pip install uvicorn

FROM install
LABEL api_stage=2

CMD cd ai_tools_api && uvicorn "ai_tools_lambda:create_fastapi_app" --factory --reload --host 0.0.0.0 --port ${DEV_PORT}
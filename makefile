dev: install-dev
	
install-dev: install-prod
	pip install -r requirements-dev.txt

install-prod:
	pip install -r src/api/lambda/ai_tools_api/requirements-lambda.txt
	pip install -r requirements.txt

unit-test:
	export LAMBDA_ROLE_ARN=arn:aws:iam::645860363137:role/AIWriterBackendStack-openailambdaServiceRoleEDA4A7-3L8WULRYXOP7 && \
	export FRONTEND_CORS_URL=https://d22zhq6xynxzgi.cloudfront.net && \
	export LOG_BUCKET_NAME=test-log-bucket-name && \
	pytest --junitxml=test_unit_results.xml --cov-report xml:test_unit_coverage.xml --cov=. tests/unit

docker:
	docker build -t openai-api .
	docker run openai-api

docker-clean:
	docker stop $$(docker ps -a -q)
	docker system prune --all --force
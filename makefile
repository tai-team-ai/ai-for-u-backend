dev: install-dev
	
install:
	pip install -r src/api/lambda/ai_tools_api/requirements-lambda.txt
	pip install -r requirements.txt

unit-test:
	pytest --junitxml=test_unit_results.xml --cov-report xml:test_unit_coverage.xml --cov=. tests/unit

docker:
	docker build -t openai-api .
	docker run openai-api

docker-clean:
	docker stop $$(docker ps -a -q)
	docker system prune --all --force
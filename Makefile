.PHONY: install test lint format demo serve docker-build clean

install:
	pip install -e ".[dev]"

test:
	pytest -q

lint:
	ruff check . && ruff format --check .

format:
	ruff format . && ruff check . --fix

demo:            ## genera datos sintéticos, entrena y corre el pipeline completo
	obrapulse demo

serve:
	obrapulse serve

docker-build:
	docker build -t obrapulse:latest .

clean:
	rm -rf reports/* data/runtime models/*.joblib models/*.json .pytest_cache .ruff_cache
	touch reports/.gitkeep

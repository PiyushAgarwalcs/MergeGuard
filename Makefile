.PHONY: install check test fmt eval-fast serve dashboard

install:
	python -m pip install -e '.[dev]'

check:
	ruff check .
	black --check .
	mypy src
	pytest -q

test:
	pytest -q

fmt:
	black .
	ruff check --fix .

eval-fast:
	python -m evals.run --layer components --mode replay
	python -m evals.run --layer integration --mode replay

serve:
	python -m uvicorn mergeguard.api:app --reload

dashboard:
	streamlit run dashboard/app.py

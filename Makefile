PYTHON ?= python3
API_DIR := apps/api
WEB_DIR := apps/web

.PHONY: api-install api-dev api-dev-mock api-dev-axidraw api-test web-install web-dev web-test

api-install:
	cd $(API_DIR) && $(PYTHON) -m pip install ".[dev]"

api-dev:
	cd $(API_DIR) && PYTHONPATH=src $(PYTHON) -m uvicorn learn_to_draw_api.main:app --reload

api-dev-mock:
	cd $(API_DIR) && LEARN_TO_DRAW_PLOTTER_DRIVER=mock PYTHONPATH=src $(PYTHON) -m uvicorn learn_to_draw_api.main:app --reload

api-dev-axidraw:
	cd $(API_DIR) && LEARN_TO_DRAW_PLOTTER_DRIVER=axidraw PYTHONPATH=src $(PYTHON) -m uvicorn learn_to_draw_api.main:app --reload

api-test:
	cd $(API_DIR) && PYTHONPATH=src $(PYTHON) -m pytest

web-install:
	cd $(WEB_DIR) && npm install

web-dev:
	cd $(WEB_DIR) && npm run dev

web-test:
	cd $(WEB_DIR) && npm run test

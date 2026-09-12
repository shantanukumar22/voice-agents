# MediKiosk local runners — from repo root: `make bot`, `make api`, `make client`

.PHONY: bot api client doctor sync

sync:
	uv sync --project bot
	npm install --prefix client
	npm install --prefix doctor-app

bot:
	cd bot && uv run server.py

api:
	uv run --project bot uvicorn backend.server:app --host 127.0.0.1 --port 8000

client:
	npm run dev --prefix client

doctor:
	npm run dev --prefix doctor-app

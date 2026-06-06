UVICORN := .venv/bin/uvicorn
PYTEST  := .venv/bin/python -m pytest
PID_BE  := .pids/backend.pid
PID_FE  := .pids/frontend.pid
LOG_DIR := logs

.PHONY: help install dev dev-be dev-fe stop stop-be stop-fe \
        status restart build deploy install-services \
        test test-be test-fe logs logs-app clean

help:
	@printf "\nAgora — comandos\n\n"
	@printf "  make install          Instala dependencias Python (.venv) y npm\n"
	@printf "  make dev              Arranca backend (8001) + frontend dev (5173)\n"
	@printf "  make dev-be           Solo backend con --reload\n"
	@printf "  make dev-fe           Solo frontend dev\n"
	@printf "  make stop             Para backend y frontend\n"
	@printf "  make restart          Para y vuelve a arrancar\n"
	@printf "  make status           Muestra si los procesos están corriendo\n"
	@printf "  make build            Build de producción del frontend\n"
	@printf "  make deploy           Build + instala nginx config (requiere sudo)\n"
	@printf "  make install-services Instala y habilita los servicios systemd (sudo)\n"
	@printf "  make test      Todos los tests (backend + frontend)\n"
	@printf "  make test-be   Tests del backend\n"
	@printf "  make test-fe   Tests del frontend\n"
	@printf "  make logs      tail -f del stdout del backend\n"
	@printf "  make logs-app  tail -f del log de la app (tertulia.log)\n"
	@printf "  make clean     Borra .pids/ y frontend/dist/\n\n"

# ── Instalación ──────────────────────────────────────────────────────────────

install:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt
	cd frontend && npm install

# ── Desarrollo ───────────────────────────────────────────────────────────────

dev: .pids
	$(UVICORN) backend.main:app --host 127.0.0.1 --port 8001 --reload \
	  > $(LOG_DIR)/backend.log 2>&1 & echo $$! > $(PID_BE)
	cd frontend && npm run dev > ../$(LOG_DIR)/frontend.log 2>&1 & echo $$! > $(PID_FE)
	@sleep 1
	@echo ""
	@echo "  Backend  → http://127.0.0.1:8001  (PID $$(cat $(PID_BE)))"
	@echo "  Frontend → http://localhost:5173   (PID $$(cat $(PID_FE)))"
	@echo ""
	@echo "  make stop     para parar"
	@echo "  make logs     stdout del backend"
	@echo "  make logs-app tertulia.log (LogCentral)"
	@echo ""

dev-be: .pids
	$(UVICORN) backend.main:app --host 127.0.0.1 --port 8001 --reload \
	  > $(LOG_DIR)/backend.log 2>&1 & echo $$! > $(PID_BE)
	@echo "Backend → http://127.0.0.1:8001  (PID $$(cat $(PID_BE)))"

dev-fe: .pids
	cd frontend && npm run dev > ../$(LOG_DIR)/frontend.log 2>&1 & echo $$! > $(PID_FE)
	@echo "Frontend → http://localhost:5173  (PID $$(cat $(PID_FE)))"

# ── Control de procesos ───────────────────────────────────────────────────────

stop: stop-be stop-fe

stop-be:
	@if [ -f $(PID_BE) ]; then \
	  pid=$$(cat $(PID_BE)); \
	  kill $$pid 2>/dev/null \
	    && echo "Backend parado (PID $$pid)" \
	    || echo "Backend: proceso $$pid ya no existía"; \
	  rm -f $(PID_BE); \
	else echo "Backend: no hay PID guardado"; fi

stop-fe:
	@if [ -f $(PID_FE) ]; then \
	  pid=$$(cat $(PID_FE)); \
	  kill $$pid 2>/dev/null \
	    && echo "Frontend parado (PID $$pid)" \
	    || echo "Frontend: proceso $$pid ya no existía"; \
	  rm -f $(PID_FE); \
	else echo "Frontend: no hay PID guardado"; fi

restart: stop dev

status:
	@echo ""
	@printf "  Backend  (8001): "
	@if [ -f $(PID_BE) ] && kill -0 $$(cat $(PID_BE)) 2>/dev/null; \
	  then echo "✓ corriendo (PID $$(cat $(PID_BE)))"; \
	  else echo "✗ parado"; fi
	@printf "  Frontend (5173): "
	@if [ -f $(PID_FE) ] && kill -0 $$(cat $(PID_FE)) 2>/dev/null; \
	  then echo "✓ corriendo (PID $$(cat $(PID_FE)))"; \
	  else echo "✗ parado"; fi
	@echo ""

# ── Build y despliegue ────────────────────────────────────────────────────────

build:
	cd frontend && npm run build
	@echo "Bundle listo en frontend/dist/"

deploy: build
	@echo "Instalando config nginx..."
	sudo cp frontend/nginx.conf /etc/nginx/sites-available/agora
	sudo ln -sf /etc/nginx/sites-available/agora /etc/nginx/sites-enabled/agora
	sudo nginx -t && sudo systemctl reload nginx
	@echo ""
	@echo "✓ Agora en producción → http://seb01:5151 (Tailscale)"
	@echo ""

install-services:
	@echo "Instalando servicios systemd..."
	sudo cp agora-backend.service /etc/systemd/system/agora-backend.service
	sudo cp agora-frontend.service /etc/systemd/system/agora-frontend.service
	sudo systemctl daemon-reload
	sudo systemctl enable agora-backend agora-frontend
	sudo systemctl start agora-backend agora-frontend
	@echo ""
	@echo "✓ Servicios instalados y arrancados"
	@echo "  Backend  → systemctl status agora-backend"
	@echo "  Frontend → systemctl status agora-frontend"
	@echo "  Logs     → journalctl -u agora-backend -u agora-frontend -f"
	@echo ""

# ── Tests ─────────────────────────────────────────────────────────────────────

test: test-be test-fe

test-be:
	$(PYTEST) backend/tests/ -v

test-fe:
	cd frontend && npx vitest run

# ── Logs ─────────────────────────────────────────────────────────────────────

logs:
	@tail -f $(LOG_DIR)/backend.log

logs-app:
	@tail -f $(LOG_DIR)/tertulia.log

# ── Directorios y limpieza ────────────────────────────────────────────────────

.pids:
	@mkdir -p .pids $(LOG_DIR)

clean:
	rm -rf .pids frontend/dist

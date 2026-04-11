SHELL := /bin/bash

ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
LAUNCHER := $(ROOT)/dev-launch.sh
TERMINAL ?=

.PHONY: help run stop fastapi backend admin-backend frontend admin-frontend

help:
	@echo "make run     # open all 5 services in separate terminals"
	@echo "make stop    # stop all running project services"
	@echo "make fastapi # run FastAPI in the current terminal"
	@echo "make backend"
	@echo "make admin-backend"
	@echo "make frontend"
	@echo "make admin-frontend"
	@echo ""
	@echo "Optional:"
	@echo "  make run TERMINAL=gnome-terminal"
	@echo ""
	@echo "If no GUI terminal app is found, make run falls back to background mode"
	@echo "and writes logs in .run-logs/ (similar to run-dev.sh)."

run:
	@$(MAKE) stop >/dev/null
	@$(call open_terminal,Photon FastAPI,fastapi)
	@$(call open_terminal,Photon Backend,backend)
	@$(call open_terminal,Photon Admin Backend,admin-backend)
	@$(call open_terminal,Photon Frontend,frontend)
	@$(call open_terminal,Photon Admin Frontend,admin-frontend)
	@echo "Started project services."
	@echo "(Uses separate terminals when available, otherwise background fallback.)"
	@echo "Frontend:       http://127.0.0.1:5173"
	@echo "Admin frontend: http://127.0.0.1:5174/admin"

stop:
	@pkill -f 'uvicorn main:app --host 127.0.0.1 --port 8000' 2>/dev/null || true
	@pkill -f '$(ROOT)/backend/node_modules/.bin/nodemon index.js' 2>/dev/null || true
	@pkill -f '$(ROOT)/backend.*node index.js' 2>/dev/null || true
	@pkill -f '$(ROOT)/admin-backend.*node index.js' 2>/dev/null || true
	@pkill -f '$(ROOT)/frontend/node_modules/.bin/vite --host 127.0.0.1 --port 5173' 2>/dev/null || true
	@pkill -f '$(ROOT)/admin-frontend/node_modules/.bin/vite --host 127.0.0.1 --port 5174' 2>/dev/null || true
	@true

fastapi:
	@bash "$(LAUNCHER)" fastapi

backend:
	@bash "$(LAUNCHER)" backend

admin-backend:
	@bash "$(LAUNCHER)" admin-backend

frontend:
	@bash "$(LAUNCHER)" frontend

admin-frontend:
	@bash "$(LAUNCHER)" admin-frontend

define open_terminal
	if [ -n "$(TERMINAL)" ]; then \
		term="$(TERMINAL)"; \
	else \
		term=""; \
		for candidate in gnome-terminal kgx konsole xfce4-terminal tilix kitty alacritty xterm; do \
			if command -v $$candidate >/dev/null 2>&1; then \
				term="$$candidate"; \
				break; \
			fi; \
		done; \
	fi; \
	if [ -z "$$term" ]; then \
		mkdir -p "$(ROOT)/.run-logs" "$(ROOT)/.run-pids"; \
		pid_file="$(ROOT)/.run-pids/$(2).pid"; \
		log_file="$(ROOT)/.run-logs/$(2).log"; \
		if [ -f "$$pid_file" ] && kill -0 "$$(cat "$$pid_file")" >/dev/null 2>&1; then \
			echo "$(2) is already running with PID $$(cat "$$pid_file")"; \
		else \
			nohup bash "$(LAUNCHER)" $(2) >"$$log_file" 2>&1 & \
			echo $$! >"$$pid_file"; \
			echo "Started $(2) in background (PID $$(cat "$$pid_file"))"; \
			echo "Log: $$log_file"; \
		fi; \
		exit 0; \
	fi; \
	case "$$term" in \
		gnome-terminal) gnome-terminal --title="$(1)" -- bash "$(LAUNCHER)" $(2) --hold >/dev/null 2>&1 & ;; \
		kgx) kgx --title "$(1)" bash "$(LAUNCHER)" $(2) --hold >/dev/null 2>&1 & ;; \
		konsole) konsole --new-tab -p tabtitle="$(1)" --hold -e bash "$(LAUNCHER)" $(2) --hold >/dev/null 2>&1 & ;; \
		xfce4-terminal) xfce4-terminal --title="$(1)" --hold -e "bash $(LAUNCHER) $(2) --hold" >/dev/null 2>&1 & ;; \
		tilix) tilix --title "$(1)" -e "bash $(LAUNCHER) $(2) --hold" >/dev/null 2>&1 & ;; \
		kitty) kitty --title "$(1)" bash "$(LAUNCHER)" $(2) --hold >/dev/null 2>&1 & ;; \
		alacritty) alacritty -T "$(1)" -e bash "$(LAUNCHER)" $(2) --hold >/dev/null 2>&1 & ;; \
		xterm) xterm -T "$(1)" -hold -e bash "$(LAUNCHER)" $(2) --hold >/dev/null 2>&1 & ;; \
		*) echo "Unsupported TERMINAL=$$term"; exit 1 ;; \
	esac
endef

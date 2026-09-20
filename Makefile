# ==============================================================================
# Multimedia Tool: Autonomous Retro Pixel & AI Video Engine
# ==============================================================================

SHELL := /bin/bash
PYTHON := uv run python

.PHONY: help install setup dev serve remotion cli cli-grok test clean check

# Default Target
help:
	@echo "====================================================================="
	@echo "   MULTIMEDIA TOOL - Developer & Service Orchestration"
	@echo "====================================================================="
	@echo "  make install    Create .venv and install all Python (uv) & Node deps"
	@echo "  make dev        Launch Web Studio & FastAPI API (http://localhost:8000)"
	@echo "  make serve      Alias for 'make dev'"
	@echo "  make remotion   Start Remotion player development server"
	@echo "  make cli        Run demo pipeline with BytePlus Seedance (watermark-free)"
	@echo "  make cli-grok   Run demo pipeline with xAI Grok Imagine Video"
	@echo "  make test       Run test suite with pytest via uv"
	@echo "  make clean      Remove build artifacts, caches, and temp render files"
	@echo "====================================================================="

# Environment & Dependency Installation using uv and npm
install: setup

setup:
	@echo "--> Setting up Python environment with uv..."
	uv venv
	uv pip install -r requirements.txt
	uv pip install -e .
	@echo "--> Installing Remotion dependencies with npm..."
	cd remotion && npm install
	@echo "--> Setup complete! Ready to launch services."

# Launch FastAPI Web Server & Interactive Studio
dev: serve

serve:
	@echo "--> Launching Multimedia Web Studio at http://localhost:8000 ..."
	$(PYTHON) -m src.server

# Launch Remotion Preview Player
remotion:
	@echo "--> Starting Remotion preview engine..."
	cd remotion && npm start

# Run CLI Pipeline (Seedance default)
cli:
	@echo "--> Executing pipeline with BytePlus Seedance..."
	$(PYTHON) -m src.cli \
		--topic "How Local LLMs Work on Apple Silicon" \
		--provider seedance \
		--chapters 4 \
		--skip-video-gen

# Run CLI Pipeline with xAI Grok
cli-grok:
	@echo "--> Executing pipeline with xAI Grok Imagine..."
	$(PYTHON) -m src.cli \
		--topic "How Local LLMs Work on Apple Silicon" \
		--provider grok \
		--chapters 4 \
		--skip-video-gen

# Run Test Suite
test:
	@echo "--> Running test suite with pytest..."
	uv run pytest tests/ -v

# Clean Temporary Render Artifacts and Caches
clean:
	@echo "--> Cleaning render artifacts and python bytecode..."
	rm -rf renders/cutscenes/* temp/* .pytest_cache .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@echo "--> Clean complete."

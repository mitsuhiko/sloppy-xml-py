.PHONY: all format check format-check lint sync test build clean help

all: sync check test

# Format code automatically
format:
	@uv run ruff format

# Check code style and quality
check: format-check lint

# Check if code formatting is correct without changing files
format-check:
	@uv run ruff format --check

# Run linting
lint:
	@uv run ruff check

# Install/update dependencies and sync environment
sync:
	@uv sync

# Run all tests
test:
	@uv run pytest

# Build source distribution and wheel packages
build:
	@uv build

# Clean build artifacts
clean:
	@rm -rf dist/ build/ *.egg-info/

# Show available targets
help:
	@echo "Available targets:"
	@echo "  format       - Format code automatically"
	@echo "  check        - Check code style and quality"
	@echo "  format-check - Check if code formatting is correct"
	@echo "  lint         - Run linting"
	@echo "  sync         - Install/update dependencies"
	@echo "  test         - Run all tests"
	@echo "  build        - Build packages"
	@echo "  clean        - Clean build artifacts"
	@echo "  help         - Show this help message"

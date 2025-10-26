## Development Environment Setup

This guide outlines the steps to set up your local development environment. This project uses **`make`** as a command
runner and **`uv`** for fast Python package and virtual environment management.

### 1\. Prerequisites

Before you begin, ensure you have the following tools installed on your system:

* **Python**: Version 3.10 or newer.
* **make**: The standard build automation tool.
* **git**: For version control.
* **uv**: A fast Python package installer. If you don't have it, install it with:
  ```bash
  # On macOS, Linux, or WSL
  curl -LsSf https://astral.sh/uv/install.sh | sh

  # Or via pip
  pip install uv
  ```
* **pipx**: Recommended for installing Python CLI applications globally.
  ```bash
  pip install pipx
  pipx ensurepath
  ```
* **changelogmanager**: A tool for validating the changelog format, installed via `pipx`.
  ```bash
  pipx install keepachangelog-manager
  ```

-----

### 2\. Initial Setup

Follow these steps to get the project running locally.

1. **Clone the Repository**

   ```bash
   git clone <repository-url>
   cd <repository-name>
   ```

2. **Create a Virtual Environment**
   Create a new virtual environment in the project root using `uv`.

   ```bash
   uv venv
   ```

   This will create a `.venv` directory.

3. **Activate the Environment**

   ```bash
   source .venv/bin/activate
   ```

   Your shell prompt should now indicate that you are in the `.venv` environment.

4. **Install Dependencies**
   The `Makefile` is configured to handle everything. Simply run **`make`**.

   ```bash
   make
   ```

   This command will trigger `uv sync`, which reads the `pyproject.toml` file and installs the exact dependency versions
   specified in the `uv.lock` file. This ensures a consistent and reproducible environment.

-----

### 3\. Common Development Commands

All common tasks are automated through `make` targets.

#### Code Quality & Testing

These are the most frequent commands you will use.

* **`make black`**: Automatically formats all Python code using `isort` and `black`.
* **`make test`**: Runs the entire test suite using `pytest`. It also generates test coverage reports (`htmlcov/`) and
  checks for a minimum coverage threshold.
* **`make pylint`**: Lints the codebase with `ruff` and `pylint` to catch potential errors and style issues.
* **`make mypy`**: Runs static type checking on the source code.
* **`make check`**: 🥇 This is the **primary command** to run before committing your code. It's a comprehensive check
  that runs tests, linting, type checking, and security analysis.

#### Documentation

* **`make make_docs`**: Generates HTML documentation for the source code in the `docs/` directory using `pdoc`.
* **`make check_all_docs`**: Validates documentation by checking for broken links, linting Markdown files, and checking
  for spelling errors in the code and documentation.

#### Housekeeping

* **`make clean`**: Removes temporary files like Python bytecode (`.pyc`), coverage data, and test artifacts.

-----

### 4\. Publishing

* **`make publish`**: Builds the source distribution and wheel for the package using `hatch`. This prepares the package
  for publishing to a repository like PyPI.
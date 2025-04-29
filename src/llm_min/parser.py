import json
import logging
import re
from pathlib import Path

import toml

logger = logging.getLogger(__name__)


def parse_requirements(file_path: str | Path) -> list[str]:
    """Parses a requirements.txt file and extracts package names.

    Handles:
        - Basic package names (e.g., requests)
        - Version specifiers (e.g., requests>=2.0)
        - Comments (# ...)
        - Blank lines
        - Editable installs (-e .)
    """
    packages = []
    try:
        with open(file_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("-e"):
                    continue

                # Use regex to extract the base package name
                # Handles specifiers (>=, <=, ==, ~=, etc.), extras ([...]), URLs (@ ...)
                match = re.match(r"^[a-zA-Z0-9._-]+", line)
                if match:
                    package_name = match.group(0)
                    # Simple heuristic to avoid potential file paths mistakenly parsed
                    if "." not in package_name or package_name.endswith(".py"):
                        packages.append(package_name)
                else:
                    logger.warning(f"Could not parse package name from line: '{line}'")

    except FileNotFoundError:
        logger.error(f"Requirements file not found: {file_path}")
        raise
    except Exception as e:
        logger.error(f"Error reading requirements file {file_path}: {e}", exc_info=True)
        raise

    logger.info(f"Extracted {len(packages)} packages from {file_path}")
    return packages


def parse_pyproject_toml(file_path: str | Path) -> list[str]:
    """Parses a pyproject.toml file and extracts package names from [tool.poetry.dependencies]."""
    packages = []
    try:
        with open(file_path, encoding="utf-8") as f:
            data = toml.load(f)
            # Assuming poetry dependencies for now
            dependencies = (
                data.get("tool", {}).get("poetry", {}).get("dependencies", {})
            )
            for package, version in dependencies.items():
                if package.lower() != "python":  # Exclude python itself
                    packages.append(package)
    except FileNotFoundError:
        logger.error(f"pyproject.toml file not found: {file_path}")
        raise
    except Exception as e:
        logger.error(
            f"Error reading pyproject.toml file {file_path}: {e}", exc_info=True
        )
        raise
    logger.info(f"Extracted {len(packages)} packages from {file_path}")
    return packages


def parse_package_json(file_path: str | Path) -> list[str]:
    """Parses a package.json file and extracts package names from dependencies and devDependencies."""
    packages = []
    try:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
            dependencies = data.get("dependencies", {})
            dev_dependencies = data.get("devDependencies", {})
            for package in dependencies:
                packages.append(package)
            for package in dev_dependencies:
                packages.append(package)
    except FileNotFoundError:
        logger.error(f"package.json file not found: {file_path}")
        raise
    except json.JSONDecodeError:
        logger.error(f"Error decoding JSON in package.json file: {file_path}")
        raise
    except Exception as e:
        logger.error(f"Error reading package.json file {file_path}: {e}", exc_info=True)
        raise
    logger.info(f"Extracted {len(packages)} packages from {file_path}")
    return packages


def parse_dependency_file(file_path: str | Path) -> list[str]:
    """
    Parses a single dependency file and extracts dependencies.

    Supported files: pyproject.toml, requirements.txt, package.json
    """
    file_path = Path(file_path)
    if file_path.name == "pyproject.toml":
        return parse_pyproject_toml(file_path)
    elif file_path.name == "requirements.txt":
        return parse_requirements(file_path)
    elif file_path.name == "package.json":
        return parse_package_json(file_path)
    else:
        logger.warning(f"Unsupported dependency file type: {file_path.name}")
        return []


def scan_for_dependencies(directory_path: str | Path) -> set[str]:
    """
    Scans a directory recursively for common dependency files and extracts dependencies.

    Supported files: pyproject.toml, requirements.txt, package.json
    """
    all_dependencies: set[str] = set()
    directory_path = Path(directory_path)
    if not directory_path.is_dir():
        logger.warning(f"Directory not found or is not a directory: {directory_path}")
        return all_dependencies

    for file_path in directory_path.rglob("*"):
        if file_path.is_file():
            try:
                if file_path.name == "pyproject.toml":
                    all_dependencies.update(parse_pyproject_toml(file_path))
                elif file_path.name == "requirements.txt":
                    all_dependencies.update(parse_requirements(file_path))
                elif file_path.name == "package.json":
                    all_dependencies.update(parse_package_json(file_path))
            except Exception as e:
                logger.error(
                    f"Error parsing dependency file {file_path}: {e}", exc_info=True
                )  # Log error and continue
    return all_dependencies

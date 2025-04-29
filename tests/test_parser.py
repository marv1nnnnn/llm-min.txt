import json
import logging
import os
import tempfile
from pathlib import Path

import pytest

from llm_min.parser import (
    parse_dependency_file,
    parse_package_json,
    parse_pyproject_toml,
    parse_requirements,
    scan_for_dependencies,
)


# Fixture to create a temporary file
@pytest.fixture
def temp_file():
    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as f:
        file_path = Path(f.name)
    yield file_path
    os.unlink(file_path)


# Fixture to create a temporary directory
@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        dir_path = Path(d)
        yield dir_path


# Tests for parse_requirements
def test_parse_requirements_basic(temp_file):
    content = "requests\npytest\n"
    temp_file.write_text(content)
    packages = parse_requirements(temp_file)
    assert packages == ["requests", "pytest"]


def test_parse_requirements_with_versions(temp_file):
    content = "requests>=2.28.1\npytest==7.1.2\n"
    temp_file.write_text(content)
    packages = parse_requirements(temp_file)
    assert packages == ["requests", "pytest"]


def test_parse_requirements_with_comments_and_blank_lines(temp_file):
    content = "# This is a comment\n\nrequests\n  # Another comment\npytest\n"
    temp_file.write_text(content)
    packages = parse_requirements(temp_file)
    assert packages == ["requests", "pytest"]


def test_parse_requirements_with_editable_install(temp_file):
    content = "-e .\nrequests\n"
    temp_file.write_text(content)
    packages = parse_requirements(temp_file)
    assert packages == ["requests"]


def test_parse_requirements_empty_file(temp_file):
    content = ""
    temp_file.write_text(content)
    packages = parse_requirements(temp_file)
    assert packages == []


def test_parse_requirements_file_not_found():
    with pytest.raises(FileNotFoundError):
        parse_requirements("non_existent_file.txt")


# TODO: Add more tests for parse_requirements (e.g., extras, urls, complex specifiers)


# Tests for parse_pyproject_toml
def test_parse_pyproject_toml_basic(temp_file):
    content = """
[tool.poetry.dependencies]
python = "^3.8"
requests = "^2.28.1"
pytest = "^7.1.2"
"""
    temp_file.write_text(content)
    packages = parse_pyproject_toml(temp_file)
    assert sorted(packages) == sorted(["requests", "pytest"])


def test_parse_pyproject_toml_no_dependencies(temp_file):
    content = """
[tool.poetry]
name = "my-package"
version = "1.0.0"
"""
    temp_file.write_text(content)
    packages = parse_pyproject_toml(temp_file)
    assert packages == []


def test_parse_pyproject_toml_file_not_found():
    with pytest.raises(FileNotFoundError):
        parse_pyproject_toml("non_existent_pyproject.toml")


def test_parse_pyproject_toml_invalid_toml(temp_file):
    content = """
[tool.poetry.dependencies
  requests = "^2.28.1"
"""
    temp_file.write_text(content)
    with pytest.raises(Exception):  # toml.load raises different exceptions
        parse_pyproject_toml(temp_file)


# TODO: Add tests for parse_package_json


# Tests for parse_package_json
def test_parse_package_json_basic(temp_file):
    content = """
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "devDependencies": {
    "jest": "^29.7.0"
  }
}
"""
    temp_file.write_text(content)
    packages = parse_package_json(temp_file)
    assert sorted(packages) == sorted(["react", "react-dom", "jest"])


def test_parse_package_json_no_dependencies(temp_file):
    content = """
{
  "name": "my-package",
  "version": "1.0.0"
}
"""
    temp_file.write_text(content)
    packages = parse_package_json(temp_file)
    assert packages == []


def test_parse_package_json_file_not_found():
    with pytest.raises(FileNotFoundError):
        parse_package_json("non_existent_package.json")


def test_parse_package_json_invalid_json(temp_file):
    content = """
{
  "dependencies": {
    "react": "^18.2.0",
"""  # Missing closing brace
    temp_file.write_text(content)
    with pytest.raises(json.JSONDecodeError):
        parse_package_json(temp_file)


# Tests for parse_dependency_file
def test_parse_dependency_file_requirements_txt(temp_dir):
    file_path = temp_dir / "requirements.txt"
    content = "requests\npytest\n"
    file_path.write_text(content)
    packages = parse_dependency_file(file_path)
    assert packages == ["requests", "pytest"]


def test_parse_dependency_file_pyproject_toml(temp_dir):
    file_path = temp_dir / "pyproject.toml"
    content = """
[tool.poetry.dependencies]
python = "^3.8"
requests = "^2.28.1"
"""
    file_path.write_text(content)
    packages = parse_dependency_file(file_path)
    assert packages == ["requests"]


def test_parse_dependency_file_package_json(temp_dir):
    file_path = temp_dir / "package.json"
    content = """
{
  "dependencies": {
    "react": "^18.2.0"
  }
}
"""
    file_path.write_text(content)
    packages = parse_dependency_file(file_path)
    assert packages == ["react"]


def test_parse_dependency_file_unsupported_file(temp_dir):
    # Create an unsupported file directly
    unsupported_file_path = temp_dir / "unsupported.yaml"
    unsupported_file_path.write_text("dummy content")

    packages = parse_dependency_file(unsupported_file_path)
    assert packages == []  # Should return empty list for unsupported
    # No need to manually clean up, temp_dir fixture handles it.


def test_parse_dependency_file_not_found(caplog):
    # For unsupported file types, it should log a warning and return []
    file_path = Path("non_existent_file.xyz")
    # Ensure it doesn't raise FileNotFoundError for unsupported types
    # (it only raises if the specific parser fails to find the file)
    with caplog.at_level(logging.WARNING):
        packages = parse_dependency_file(file_path)

    assert packages == []
    # Check for the specific warning log
    assert f"Unsupported dependency file type: {file_path.name}" in caplog.text


# Tests for scan_for_dependencies
def test_scan_for_dependencies_basic(temp_dir):
    (temp_dir / "requirements.txt").write_text("requests\npytest\n")
    (temp_dir / "package.json").write_text('{"dependencies": {"react": "^18.0.0"}}')
    (temp_dir / "unsupported.txt").write_text("some text")  # Should be ignored

    dependencies = scan_for_dependencies(temp_dir)
    assert sorted(list(dependencies)) == sorted(["requests", "pytest", "react"])


def test_scan_for_dependencies_nested_directories(temp_dir):
    subdir1 = temp_dir / "subdir1"
    subdir1.mkdir()
    (subdir1 / "requirements.txt").write_text("numpy\n")

    subdir2 = temp_dir / "subdir2"
    subdir2.mkdir()
    (subdir2 / "package.json").write_text('{"devDependencies": {"jest": "^29.0.0"}}')

    (temp_dir / "pyproject.toml").write_text("""
[tool.poetry.dependencies]
pandas = "^1.0.0"
""")

    dependencies = scan_for_dependencies(temp_dir)
    assert sorted(list(dependencies)) == sorted(["numpy", "jest", "pandas"])


def test_scan_for_dependencies_no_supported_files(temp_dir):
    (temp_dir / "readme.md").write_text("# My Project")
    (temp_dir / "config.yaml").write_text("key: value")
    dependencies = scan_for_dependencies(temp_dir)
    assert dependencies == set()


def test_scan_for_dependencies_empty_directory(temp_dir):
    dependencies = scan_for_dependencies(temp_dir)
    assert dependencies == set()


def test_scan_for_dependencies_non_existent_directory(caplog):
    # scan_for_dependencies uses rglob, which returns an empty iterator for non-existent paths.
    # It should return an empty set without logging an error.
    non_existent_path = Path("./non_existent_dir_for_test")
    # with caplog.at_level(logging.ERROR): # Remove log check
    dependencies = scan_for_dependencies(non_existent_path)
    assert dependencies == set()
    # assert f"Directory not found: {non_existent_path}" in caplog.text # Remove log check


def test_scan_for_dependencies_with_error_file(temp_dir, caplog):
    # Create a malformed pyproject.toml
    malformed_toml_path = temp_dir / "pyproject.toml"
    malformed_toml_path.write_text("""
[tool.poetry.dependencies
  requests = "^2.28.1"
""")
    # Create a valid requirements.txt
    valid_req_path = temp_dir / "requirements.txt"
    valid_req_path.write_text("pytest\n")

    # Expect an error log during parsing, but scan should continue
    with caplog.at_level(logging.ERROR):
        dependencies = scan_for_dependencies(temp_dir)

    # Check that the error for the TOML file was logged
    assert f"Error reading pyproject.toml file {malformed_toml_path}" in caplog.text
    # Check that dependencies from the valid file were still found
    assert dependencies == {"pytest"}

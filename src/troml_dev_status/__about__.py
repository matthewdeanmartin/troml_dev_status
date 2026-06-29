"""Metadata for troml-dev-status."""

__all__ = [
    "__credits__",
    "__dependencies__",
    "__description__",
    "__keywords__",
    "__readme__",
    "__requires_python__",
    "__status__",
    "__title__",
    "__version__",
]

__title__ = "troml-dev-status"
__version__ = "0.7.0"
__keywords__ = ["development status", "trove classifiers", "python packaging"]
__description__ = "Objectively infer PyPI Development Status classifiers from code and release artifacts."
__readme__ = "README.md"
__credits__ = [{"name": "Matthew Dean Martin", "email": "matthewdeanmartin@gmail.com"}, {"name": "Gemini"}, {"name": "ChatGPT"}]
__requires_python__ = ">=3.9"
__status__ = "5 - Production/Stable"
__dependencies__ = [
    "textstat>= 0.7.10",
    "rich>=14.1.0",
    "pydantic>=2.12.0; python_version >= '3.14'",
    "pydantic>=2.11.9",
    "httpx[http2]>=0.28.1",
    "pyyaml>=6.0.2",
    "packaging>=25.0",
    "tomli>1.0.0; python_version < '3.11'",
    "tomlkit>=0.13.3",
    "pathspec>=0.12.1",
    "llvm-diagnostics>=3.0.1",
    "semantic-version>=2.10.0",
    "jinja2>=3.1.6",
    "pytest>0.0.0",
    "openai>=2.6.1",
    "pydantic_settings>1.0.0",
    "python-dotenv>=1.1.1",
]

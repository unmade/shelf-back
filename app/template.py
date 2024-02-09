from jinja2 import Environment, PackageLoader, select_autoescape

__all__ = [
    "engine",
]


engine = Environment(
    loader=PackageLoader("app"),
    autoescape=select_autoescape(),
    enable_async=True,
)

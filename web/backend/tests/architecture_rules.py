"""Static import guardrails; deliberately does not import application modules."""

import ast
from graphlib import CycleError, TopologicalSorter
from pathlib import PurePosixPath


def module_name(path: str) -> str:
    parts = list(PurePosixPath(path).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def business_module(name: str) -> tuple[str, str] | None:
    parts = name.split(".")
    if parts[:2] != ["app", "modules"]:
        return None
    layer = parts[3] if len(parts) > 3 else ""
    layer = {"controllers": "controller", "repositories": "repository"}.get(layer, layer)
    layer = {
        ("changes", "analysis"): "service",
        ("changes", "config_diff"): "graph",
        ("results", "diff"): "schemas",
    }.get((parts[2] if len(parts) > 2 else "", layer), layer)
    return (parts[2] if len(parts) > 2 else "", layer)


def check_sources(sources: dict[str, str]) -> list[str]:
    violations = []
    graph: dict[str, set[str]] = {}
    for path, source in sources.items():
        name = module_name(path)
        package = name if path.endswith("/__init__.py") else name.rpartition(".")[0]
        origin = business_module(name)
        imports: list[tuple[int, str]] = []
        tree = ast.parse(source, filename=path)
        importlib_aliases = {"importlib"}
        import_module_aliases = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append((node.lineno, alias.name))
                    if alias.name == "importlib":
                        importlib_aliases.add(alias.asname or alias.name)
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                if node.level:
                    prefix = package.split(".")[: len(package.split(".")) - node.level + 1]
                    base = ".".join(prefix + ([base] if base else []))
                for alias in node.names:
                    imports.append((node.lineno, base + "." + alias.name))
                    if base == "importlib" and alias.name == "import_module":
                        import_module_aliases.add(alias.asname or alias.name)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            dynamic = (
                isinstance(fn, ast.Name) and fn.id in import_module_aliases | {"__import__"}
            ) or (
                isinstance(fn, ast.Attribute)
                and fn.attr == "import_module"
                and isinstance(fn.value, ast.Name)
                and fn.value.id in importlib_aliases
            )
            if dynamic and origin:
                violations.append(f"{path}:{node.lineno}: dynamic imports bypass layer checking")
        for line, target in imports:
            reason = None
            destination = business_module(target)
            sdk = target == "pybatfish" or target.startswith("pybatfish.")
            sdk = sdk or target.startswith("app.infrastructure.sdk")
            sdk_factory = name == "app.infrastructure.sdk" or name.startswith(
                "app.infrastructure.sdk."
            )
            if sdk and not (sdk_factory or origin and origin[1] == "controller"):
                reason = "SDK access requires controller or infrastructure SDK factory"
            if target.split(".")[0] in {"fastapi", "starlette"} and (
                name.startswith("app.contracts") or origin and origin[1] != "api"
            ):
                reason = "HTTP framework outside API/infrastructure"
            if origin and target.startswith(("app.composition", "app.main")):
                reason = "business module cannot depend on composition"
            if destination and name != "app.composition":
                if not origin:
                    reason = "shared code cannot depend on business modules"
                elif not destination[1] or destination[1] == "*":
                    reason = "import the explicit module layer"
                elif origin[0] != destination[0]:
                    if origin[1] != "service" or destination[1] != "service":
                        reason = "cross-module dependencies must use services"
                    else:
                        graph.setdefault(origin[0], set()).add(destination[0])
                else:
                    allowed = {
                        "api": {"api", "service", "schemas"},
                        "service": {
                            "service",
                            "controller",
                            "repository",
                            "schemas",
                            "registry",
                            "export",
                            "graph",
                        },
                        "export": {"export", "schemas"},
                        "graph": {"graph", "schemas"},
                        "registry": {"registry", "schemas"},
                        "controller": {"controller", "schemas"},
                        "repository": {"repository", "schemas", "models", "archive"},
                        "archive": {"archive", "schemas"},
                        "schemas": {"schemas"},
                        "models": {"models"},
                    }
                    if destination[1] not in allowed.get(origin[1], set()):
                        reason = "forbidden dependency between module layers"
            if reason:
                violations.append(f"{path}:{line}: {reason}: {target}")
    try:
        tuple(TopologicalSorter(graph).static_order())
    except CycleError as exc:
        violations.append(f"cross-module service cycle: {exc.args[1]}")
    return violations

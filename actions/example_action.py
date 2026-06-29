"""Example Fiona Action.

This is a template/example action that demonstrates the expected interface.
Each action module should expose a ``run()`` function that accepts a context
dictionary and returns a result dictionary.
"""

__all__ = ["run"]


def run(context: dict | None = None) -> dict:
    """Execute the example action.

    Args:
        context: Optional dictionary with execution context (args, workspace, etc.)

    Returns:
        dict with keys:
            - success: bool
            - message: str
            - data: any
    """
    name = context.get("name", "World") if context else "World"
    return {
        "success": True,
        "message": f"Hello, {name}!",
        "data": {"greeting": f"Hello, {name}!"},
    }


if __name__ == "__main__":
    result = run({"name": "Fiona"})
    print(result)

from nicegui import app


def set_selected_environment(env: str):
    """Set the selected environment."""
    app.storage.user["selected_environment"] = env


def get_selected_environment() -> str | None:
    """Get the selected environment."""
    return app.storage.user.get("selected_environment")


def set_selected_step_function_arn(machine_arn: str):
    """Set the selected step function ARN."""
    app.storage.user["selected_step_function_arn"] = machine_arn


def get_selected_step_function_arn() -> str | None:
    """Get the selected step function ARN."""
    return app.storage.user.get("selected_step_function_arn")


def set_selected_step_function_config_name(machine_config_name: str):
    """Set the selected step function config name."""
    app.storage.user["selected_step_function_config_name"] = machine_config_name


def get_selected_step_function_config_name() -> str | None:
    """Get the selected step function config name."""
    return app.storage.user.get("selected_step_function_config_name")

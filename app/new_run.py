import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pytz
from manager import StepFunctionManager
from nicegui import ui
from utils.aws_manager import aws_manager
from utils.config_loader import SFC
from utils.nicegui_utils import show_notification


@dataclass
class FormElement:
    ui_element: Any
    input_type: str
    default_value: Any = None

    def get_value(self) -> Any:
        return self.ui_element.value if self.ui_element else self.default_value


def create_valid_name(user_input: str) -> str:
    MAX_NAME_LENGTH = 80
    TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"

    cleaned_name = re.sub(r"[^a-zA-Z0-9-_]", "_", user_input)
    cleaned_name = re.sub(r"_+", "_", cleaned_name)
    cleaned_name = cleaned_name.strip("_")

    timestamp = datetime.now(tz=pytz.UTC).strftime(TIMESTAMP_FORMAT)
    execution_name = f"{cleaned_name}_{timestamp}"

    if len(execution_name) > MAX_NAME_LENGTH:
        max_name_length = MAX_NAME_LENGTH - len(timestamp) - 1
        execution_name = f"{cleaned_name[:max_name_length]}_{timestamp}"

    return execution_name


class NewRunViewer(StepFunctionManager):
    def __init__(self, initial_values: dict[str, Any] | None = None):
        super().__init__()
        self.parameters = SFC.get_step_function_params(self.step_function_selected)
        self.form_elements: dict[str, FormElement] = {}
        self.initial_values = initial_values or {}
        self.UI_CLASSES = {
            "card": "w-full rounded-lg",
            "title": "text-2xl font-bold mb-4",
            "parameter_label": "text-lg font-medium text-gray-800",
            "description": "text-sm text-gray-500 break-all",
            "input_container": "w-full gap-0 -mb-2",
            "input_element": "w-full -mt-1",
        }
        self.UI_PROPS = {"input": "borderless"}

    async def create_ui(self) -> None:
        ui.label(f"New run for {self.step_function_name}").classes(self.UI_CLASSES["title"])
        self.create_execution_name_card()

        if self.parameters:
            for param_name, param_config in self.parameters.items():
                self.create_parameter_card(param_name, param_config)

    def create_execution_name_card(self) -> None:
        with ui.card().classes(self.UI_CLASSES["card"]):
            with ui.column().classes(self.UI_CLASSES["input_container"]):
                ui.label("execution_name").classes(self.UI_CLASSES["parameter_label"])

                with ui.column().classes("w-full"):
                    ui.label("Identify this build with a message. Optional.").classes(self.UI_CLASSES["description"])

                default_value = self.initial_values.get("execution_name", "")
                element = (
                    ui.input(value=default_value).classes(self.UI_CLASSES["input_element"]).props(self.UI_PROPS["input"])
                )

                self.form_elements["execution_name"] = FormElement(
                    ui_element=element, input_type="string", default_value=default_value
                )

    def create_parameter_card(self, param_name: str, param_config: dict[str, Any]) -> None:
        with ui.card().classes(self.UI_CLASSES["card"]):
            with ui.column().classes(self.UI_CLASSES["input_container"]):
                with ui.row().classes("w-full gap-0"):
                    with ui.column().classes("w-1/2"):
                        ui.label(param_name).classes(self.UI_CLASSES["parameter_label"])

                    with ui.column().classes("w-full"):
                        if description := param_config.get("description", ""):
                            ui.label(description).classes(self.UI_CLASSES["description"])

                param_type = param_config.get("type")
                default_value = self.initial_values.get(param_name, param_config.get("default"))
                element = self.create_input_element(param_type, default_value, param_config)

                self.form_elements[param_name] = FormElement(
                    ui_element=element,
                    input_type=param_type,
                    default_value=default_value,
                )

    def create_input_element(self, param_type: str, default_value: Any, param_config: dict[str, Any]) -> Any:
        input_elements = {
            "string": lambda: ui.input(value=default_value),
            "text": lambda: ui.textarea(value=default_value).style("max-height: 100px; overflow-y: auto"),
            "boolean": lambda: ui.switch(value=default_value),
            "integer": lambda: ui.number(value=default_value),
            "select": lambda: ui.select(
                value=default_value,
                multiple=param_config.get("multiple"),
                options=param_config.get("options"),
            ),
        }

        if param_type not in input_elements:
            error_msg = f"Unsupported parameter type: {param_type}"
            raise ValueError(error_msg)

        element = input_elements[param_type]()
        return element.classes(self.UI_CLASSES["input_element"]).props(self.UI_PROPS["input"])

    def get_form_values(self) -> dict[str, Any]:
        return {key: element.get_value() for key, element in self.form_elements.items()}

    async def handle_submit(self) -> None:
        form_values = self.get_form_values()
        execution_name = form_values.pop("execution_name", None)
        execution_name = create_valid_name(execution_name)

        execution_params = {
            "step_function_arn": self.step_function_arn_selected,
            "input_data": json.dumps(form_values),
        }

        if execution_name:
            execution_params["execution_name"] = execution_name

        try:
            response = aws_manager.start_execution(**execution_params)
            execution_arn = response["executionArn"]
            execution_id = execution_arn.split(":")[-1]

            show_notification("Run submitted successfully!", notification_type="success")
            ui.navigate.to(f"/execution/{self.step_function_name}/{execution_id}")
        except Exception as e:
            show_notification(
                f"Error while launching a Step Function execution.\n{e!s}",
                notification_type="error",
            )
            raise

    async def submit(self, dialog: Any, refresh_f: Callable | None = None) -> None:
        await self.handle_submit()
        dialog.close()

        if refresh_f:
            await refresh_f()

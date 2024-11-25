from ast import literal_eval

from nicegui import ui


class InputViewer:
    def __init__(self, step_function_details: str):
        self.input_json = step_function_details.get("input")
        self.input_json = self.input_json.replace("true", "True").replace("false", "False").replace("null", "None")

    async def show_json_popup(self):
        # Line numbers and code content container
        with ui.row().classes("w-full"):
            ui.json_editor(
                {"content": {"json": literal_eval(self.input_json)}},
            ).classes("w-full").props("readonly=True")

        return literal_eval(self.input_json)

import os
from enum import Enum
from functools import partial

from detail_executions import show_execution  # noqa
from loguru import logger as log
from manager import StepFunctionManager
from new_run import NewRunViewer
from nicegui import app, ui
from utils.app_storage import (
    get_selected_step_function_config_name,
    set_selected_environment,
    set_selected_step_function_arn,
    set_selected_step_function_config_name,
)
from utils.aws_manager import aws_manager
from utils.config_loader import SFC
from utils.date_utils import format_duration
from utils.nicegui_utils import button_disable_context, show_notification


class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Home(StepFunctionManager):
    def __init__(self):
        super().__init__()

    async def create_ui(self):
        """Create the main UI layout."""
        with ui.card().classes("main-container w-full h-full max-w-full break-words overflow-x-auto"):
            with ui.splitter(value=25).classes("w-full h-full ") as splitter:
                await self.sidebar(splitter)
                await self.main_content(splitter)

    async def sidebar(self, splitter):
        """Create the sidebar containing environment selector and step functions list."""
        with splitter.before:
            with ui.card().classes("w-full h-full"):
                ui.label("Environments").classes("text-2xl font-bold text-gray-700")
                self.environment_selector()
                ui.separator().classes("mb-2")
                await self.step_functions_list()

    async def main_content(self, splitter):
        """Create the main content area."""
        with splitter.after:
            await self.show_details_panel()

    def environment_selector(self):
        """Create the environment selection dropdown."""
        ui.select(
            options=[env.value for env in Environment],
            label="Select Environment",
            value=self.environment_selected,
            on_change=self.handle_environment_change,
        ).classes(
            "w-full mb-0 -mt-2 rounded-lg " "bg-white dark:bg-gray-800 " "text-gray-700 " "shadow-sm " "cursor-pointer "
        )

    @ui.refreshable
    async def step_functions_list(self):
        """Create the UI for displaying step functions."""
        with ui.column().classes("w-full overflow-auto"):
            ui.label(f"{str(self.environment_selected).capitalize()} step functions").classes(
                "text-2xl font-bold text-gray-800 mb-0 px-0"
            ) if self.environment_selected else None

            with ui.scroll_area().classes("w-full h-[calc(100vh-200px)]"):
                with ui.column().classes("w-full max-w-full px-2"):
                    for sm in self.step_functions:
                        await self.step_function_card(sm)

    async def step_function_card(self, sm: str):
        """Create a card for a single step functions."""

        def get_card_classes(is_selected: bool) -> str:
            """Get the CSS classes for a step functions card."""
            base_classes = "w-full max-w-full break-words overflow-x-auto hover:bg-gray-300 cursor-pointer transition-colors"
            bg_class = "bg-gray-300" if is_selected else "bg-white"
            return f"{base_classes} {bg_class}"

        is_selected = get_selected_step_function_config_name() == sm
        card_classes = get_card_classes(is_selected)

        with ui.card().tight().classes(card_classes).on("click", lambda: self.handle_step_function_click(sm)):
            with ui.row().classes("w-full justify-between items-center p-2 h-14"):
                ui.label(sm).classes("text-md font-medium text-gray-700")
                ui.icon("arrow_forward").classes("text-gray-700")

    async def handle_step_function_click(self, sm: str):
        """Handle click event on step function card."""

        self.step_function_selected = sm
        self.step_function_arn_selected = SFC.get_arn(sm, self.environment_selected)
        set_selected_step_function_config_name(self.step_function_selected)
        set_selected_step_function_arn(self.step_function_arn_selected)
        self.step_functions_list.refresh()
        self.show_details_panel.refresh()

    async def handle_environment_change(self, event):
        """Handle environment selection change."""
        if event.value:
            self.environment_selected = event.value
            set_selected_environment(event.value)
            self.step_functions = SFC.list_step_functions_per_environment(event.value)
            self.step_functions_list.refresh()
            self.step_function_arn_selected = SFC.get_arn(self.step_function_selected, event.value)
            set_selected_step_function_arn(self.step_function_arn_selected)
            self.show_details_panel.refresh()

    @ui.refreshable
    async def show_details_panel(self):
        """Display the details panel for the selected step function."""

        def show_empty_state():
            """Show empty state when no step function is selected."""

            with ui.card().classes("w-full h-[120px] p-7 m-4 max-w-full break-words"):
                with ui.row().classes("w-full justify-center items-center gap-4 -mt-2"):
                    ui.icon("info_outline", size="2em").classes("text-gray-600")
                    ui.label("Select a step function.").classes("text-gray-600 text-xl font-bold")
                with ui.row().classes("w-full justify-center mt-3"):
                    ui.label("Select an environment and a step function from the drop-down menu on the left.").classes(
                        "text-gray-600"
                    )

        if not self.step_function_selected:
            show_empty_state()
            return

        with ui.scroll_area().classes("w-full h-full"):
            viewer = StepFunctionViewer()
            await viewer.create_ui()


class StepFunctionViewer(StepFunctionManager):
    def __init__(self):
        super().__init__()
        self.executions = None
        self.execution_counts = None
        self.step_function_details = None
        self.max_executions = 20
        self.executions_card = None
        self.stats_card = None
        self.exists = False
        self.refresh_data()

    def refresh_data(self):
        """Refresh all data from AWS"""
        try:
            self.step_function_details = aws_manager.get_step_function_details(self.step_function_arn_selected)
            if self.step_function_details:
                self.exists = True
                self.execution_counts = aws_manager.get_execution_counts(self.step_function_arn_selected)
                self.executions = aws_manager.list_executions(self.step_function_arn_selected, self.max_executions)
            else:
                self.exists = False
                self.execution_counts = {}
                self.executions = []

        except Exception as e:
            error_msg = f"Error refreshing data: {e!s}"
            log.error(error_msg)

            self.exists = False
            self.step_function_details = None
            self.execution_counts = {}
            self.executions = []

    async def refresh_all(self) -> None:
        """Refresh all data and UI components."""
        self.refresh_data()
        self.stats_card.refresh()
        self.executions_card.refresh()

    async def slow_refresh(self, sender: ui.button) -> None:
        """Perform a slow refresh with button disable animation."""
        await self.refresh_all()
        show_notification("Refreshed successfully", notification_type="success")

        async with button_disable_context(sender):
            import asyncio

            await asyncio.sleep(5)

    def stats_table(self):
        @ui.refreshable
        def stats_table():
            if not self.exists:
                return

            with ui.card().classes("w-full h-[150px] flex no-shadow"):
                with ui.element("div").classes("w-full"):
                    ui.label("Execution Statistics").classes("text-lg font-bold mb-4")
                    if self.step_function_details and self.execution_counts:
                        with ui.element("div").classes("grid grid-cols-5 w-full gap-3"):
                            for status, count in self.execution_counts.items():
                                with ui.element("div").classes("p-3 text-center w-full -mb-10"):
                                    ui.label(status if status != "TIMED_OUT" else "TIMED OUT").classes(
                                        "font-semibold text-sm text-gray-600"
                                    )
                                    ui.label(str(count)).classes("text-2xl font-bold mt-2 text-gray-800")
                    else:
                        ui.label("Step function not found").classes("text-red-500")

        return stats_table

    def executions_table(self):
        @ui.refreshable
        def executions_table():
            if not self.exists:
                return
            ui.add_head_html("""
                <link rel="stylesheet" href="/assets/styles/table.css">
            """)

            with ui.card().classes("w-full no-shadow"):
                if self.executions:
                    ui.label(f"Last {self.max_executions} executions").classes("text-lg font-bold mb-2")

                    with ui.element("div").classes("overflow-x-auto -mb-6"):
                        table_html = """
                            <table class="q-table">
                                <thead>
                                    <tr>
                                        <th style="text-align: left;">Execution Name</th>
                                        <th>Status</th>
                                        <th>Start Time</th>
                                        <th>End Time</th>
                                        <th>Duration</th>
                                        <th>Details</th>
                                        <th>Nerdy</th>
                                    </tr>
                                </thead>
                                <tbody>
                        """

                        for execution in self.executions:
                            status = execution.get("status", "")
                            start_date = execution.get("startDate")
                            stop_date = execution.get("stopDate")

                            # Format dates for display
                            start_date_str = start_date.strftime("%Y-%m-%d %H:%M:%S") if start_date else "-"
                            stop_date_str = stop_date.strftime("%Y-%m-%d %H:%M:%S") if stop_date else "-"

                            # Calculate duration
                            duration = format_duration(start_date, stop_date) if start_date and stop_date else "-"

                            execution_url = aws_manager.get_execution_url(execution.get("executionArn", ""))
                            execution_id = execution.get("executionArn", "").split(":")[-1]

                            table_html += f"""
                                    <tr class="status-{status}">
                                        <td class="text-left">{execution.get('name', '')}</td>
                                        <td class="text-center status-cell">{status}</td>  <!-- Add status-cell class here -->
                                        <td class="text-center">{start_date_str}</td>
                                        <td class="text-center">{stop_date_str}</td>
                                        <td class="text-center">{duration}</td>
                                        <td class="text-center">
                                            <button onclick="window.location.href='/execution/{self.step_function_name}/{execution_id}'" class="details-button">
                                                View
                                            </button>
                                        </td>
                                        <td class="text-center">
                                            <a href="{execution_url}" target="_blank" class="action-link">
                                                AWS
                                            </a>
                                        </td>
                                    </tr>
                                """

                    table_html += """
                            </tbody>
                        </table>
                    """

                    ui.html(table_html).classes("w-full n-card")

                else:
                    with ui.row().classes("w-full justify-center items-center mt-20"):
                        ui.icon("warning", size="2em").classes("text-red-500")
                        ui.label("Any executions found").classes("text-red-500 text-lg")

        return executions_table

    async def create_ui(self):
        """Create the UI for the detail page."""

        with ui.card().classes("w-full h-[120px] flex gap-4 max-w-full break-words overflow-x-auto"):
            if not self.exists:
                with ui.row().classes("w-full justify-center items-center gap-4 mt-1"):
                    ui.icon("error", size="2em").classes("text-red-500")
                    ui.label("Step function does not exist").classes("text-red-500 text-xl font-bold")
                with ui.row().classes("w-full justify-center mt-3"):
                    ui.label(f'The step function "{self.step_function_selected}" was not found.').classes("text-gray-600")
                return

            with ui.element("div").classes("flex-3 w-3/4  overflow-auto"):
                ui.label(f"Information for {self.step_function_selected}").classes("text-lg font-bold mb-2")
                with ui.grid().classes("grid-cols-[100px_1fr] gap-2"):
                    ui.label("Name:").classes("font-bold")
                    ui.label(self.step_function_name).classes("truncate")
                    if self.step_function_details:
                        ui.label("ARN:").classes("font-bold")
                        ui.label(self.step_function_details["stateMachineArn"]).classes("break-words")

            with ui.element("div").classes("flex-1 w-1/4 border-l pl-4 pr-4"):
                with ui.column().classes("gap-2 justify-center"):
                    ui.button("Refresh", on_click=lambda e: self.slow_refresh(e.sender)).classes(
                        "w-40 h-10 max-w-full break-words overflow-x-auto bg-red text-white"
                    ).props("icon=refresh")

                    with ui.dialog() as dialog, ui.card().style("width: 1200px; max-width: none"):
                        new_run = NewRunViewer()
                        await new_run.create_ui()
                        with ui.row().classes("justify-end w-full gap-4"):  # Using row with justify-end and gap
                            ui.button("Close", on_click=dialog.close).classes(
                                "max-w-full break-words overflow-x-auto bg-red text-white"
                            ).props("icon=close")
                            ui.button(
                                "Submit",
                                on_click=partial(new_run.submit, dialog, self.refresh_all),
                            ).classes("max-w-full break-words overflow-x-auto bg-red text-white").props("icon=rocket_launch")

                    ui.button("Submit", on_click=dialog.open).classes(
                        "w-40 h-10 max-w-full break-words overflow-x-auto bg-red text-white"
                    ).props("icon=rocket_launch")

        # Create refreshable components
        self.stats_card = self.stats_table()
        self.executions_card = self.executions_table()

        # Display the components
        self.stats_card()
        self.executions_card()


@ui.page("/")
async def main():
    # Add Google Fonts
    ui.add_head_html("""
        <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
    """)

    ui.add_head_html("""
        <link rel="stylesheet" href="/assets/styles/main.css">
    """)

    # Rest of your code remains the same
    with ui.element("div").classes("top-banner"):
        with ui.element("div").classes("banner-content"):
            with ui.element("div").classes("logo-section"):
                ui.label("Step Functions Manager").classes("text-white text-xl font-bold")

            with ui.element("div").classes("buttons-section"):
                ui.button(
                    icon="help",
                    on_click=lambda: show_notification("Please, reach out to the NLP team", notification_type="info"),
                ).props("flat").classes("text-white")

    with ui.element("div").classes("content-wrapper"):
        page = Home()
        await page.create_ui()


if __name__ == "__main__":
    app.add_static_files("/assets", "./assets")

    ui.run(
        title="Step Functions Manager",
        storage_secret=aws_manager.get_secret(
            secret_name=os.environ.get("AWS_NICEGUI_STORAGE_SECRET"), key_to_extract="STORAGE_SECRET"
        ),
        port=int(os.environ.get("NICEGUI_PORT")),
        host=os.environ.get("NICEGUI_HOST"),
        show=False,
        reload=False,
        favicon="./assets/favicon.png",
    )

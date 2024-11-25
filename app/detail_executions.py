from datetime import datetime
from functools import lru_cache, partial

from manager import StepFunctionManager
from new_run import NewRunViewer
from nicegui import ui
from show_input import InputViewer
from utils.app_storage import (
    get_selected_step_function_config_name,
)
from utils.aws_manager import aws_manager
from utils.config_loader import SFC
from utils.date_utils import format_duration
from utils.nicegui_utils import show_notification


class ExecutionViewer(StepFunctionManager):
    def __init__(self, execution_id: str):
        super().__init__()
        self.execution_id = execution_id
        self.execution_arn = aws_manager.get_execution_arn(self.step_function_name, self.execution_id)
        self.step_function_config_name = get_selected_step_function_config_name()

        # Initialize with empty values
        self.execution_details = None
        self.definition = None
        self.states_status = None
        self.mermaid_graph = None
        self.status = None
        self.files = []

    async def initialize(self):
        """Async initialization of data"""
        self.execution_details = self.get_execution_details()
        self.definition, self.states_status = self.get_states_info()
        self.mermaid_graph = self.create_mermaid_graph()
        self.status = self.execution_details.get("status")
        self.files = self.list_created_files()

    @lru_cache(maxsize=128)
    def get_execution_details(self):
        return aws_manager.get_execution_details(self.execution_arn)

    def _abort_step_function(self):
        return aws_manager.stop_execution(self.execution_arn)

    def _redrive_step_function(self):
        return aws_manager.redrive_execution(self.execution_arn)

    @lru_cache(maxsize=128)
    def create_mermaid_graph(self):
        mermaid_graph = [
            "graph TD",
            "    %% Graph configuration",
            "    classDef default fill:#f9f9f9,stroke:#333,stroke-width:2px;",
            "    classDef running fill:#fff7e6,stroke:#ffab00,stroke-width:2px;",
            "    classDef completed fill:#e6f4ea,stroke:#34a853,stroke-width:2px;",
            "    classDef failed fill:#fce8e6,stroke:#ea4335,stroke-width:2px;",
            "    classDef notStarted fill:#f8f9fa,stroke:#dadce0,stroke-width:2px;",
            "    classDef aborted fill:#e0e0e0,stroke:#666666,stroke-width:2px;",
        ]

        states = self.definition["States"]

        # Define status to class mapping
        status_class_map = {
            "NOT_STARTED": "notStarted",
            "RUNNING": "running",
            "COMPLETED": "completed",
            "FAILED": "failed",
            "ABORTED": "aborted",
        }

        # Helper function to create node ID
        def create_node_id(state_name):
            return state_name.replace(" ", "_").replace("-", "_").replace(")", "").replace("(", "")

        # Helper function to create node class
        def get_node_class(state_name):
            status = self.states_status.get(state_name, "NOT_STARTED")
            return status_class_map.get(status, "notStarted")

        # Process each state
        for state_name, state_data in states.items():
            node_id = create_node_id(state_name)
            node_class = get_node_class(state_name)

            if self.get_execution_details().get("status") in ["TIMED_OUT", "ABORTED"] and node_class in ["running"]:
                node_class = "aborted"

            # Add state type indicator to the label
            label = f"{state_name}"

            if state_data["Type"] == "Choice":
                # Diamond shape for Choice states
                mermaid_graph.append(f'    {node_id}{{"{label}"}}:::{node_class}')
            else:
                # Rounded rectangle for all other states
                mermaid_graph.append(f'    {node_id}("{label}"):::{node_class}')

            # Handle transitions
            if state_data["Type"] == "Choice":
                if "Choices" in state_data:
                    for _idx, choice in enumerate(state_data["Choices"]):
                        if "Next" in choice:
                            next_id = create_node_id(choice["Next"])
                            # Add condition label to choice transitions
                            mermaid_graph.append(f"    {node_id} --> {next_id}")

                if "Default" in state_data:
                    default_id = create_node_id(state_data["Default"])
                    mermaid_graph.append(f"    {node_id} --> {default_id}")

            if "Next" in state_data:
                next_id = create_node_id(state_data["Next"])
                mermaid_graph.append(f"    {node_id} --> {next_id}")

        # Add some styling configurations
        mermaid_graph.insert(1, "    %% Node and edge styling")
        mermaid_graph.insert(2, "    linkStyle default stroke:#333,stroke-width:2px;")

        return "\n".join(mermaid_graph)

    @lru_cache(maxsize=128)
    def get_states_info(self):
        """
        Gets step function definition and states status with minimal API calls.
        Returns step function definition and current status of all states.
        """

        return aws_manager.get_states_info(
            self.execution_details["stateMachineArn"],
            self.execution_details["executionArn"],
        )

    @lru_cache(maxsize=128)
    def list_created_files(self):
        return aws_manager.list_s3_objects(
            "wf-nlp-tasks",
            SFC.get_files_prefix(self.step_function_config_name, self.execution_id),
        )

    @lru_cache(maxsize=128)
    def _download_file(self, file):
        link = aws_manager.get_presigned_url("wf-nlp-tasks", file)

        ui.download(link)

    async def create_ui(self):
        @ui.refreshable
        def execution_status():
            ui.label("End Time:").classes("font-bold")
            end_time = self.execution_details.get("stopDate", "N/A")
            ui.label(end_time.strftime("%Y-%m-%d %H:%M:%S") if isinstance(end_time, datetime) else end_time)

            ui.label("Duration:").classes("font-bold")
            if isinstance(self.execution_details.get("startDate"), datetime) and isinstance(end_time, datetime):
                ui.label(format_duration(start_time, end_time))
            else:
                ui.label("N/A")

            ui.label("Status:").classes("font-bold")
            ui.label(self.status).classes(
                "text-green-600"
                if self.status == "SUCCEEDED"
                else "text-red-600"
                if self.status == "FAILED"
                else "text-grey-600"
                if self.status in ["ABORTED", "TIMED_OUT"]
                else "text-blue-600"
            )

        @ui.refreshable
        def action_buttons():
            if self.status in ["FAILED", "TIMED_OUT", "ABORTED"]:
                self.redrive.enable()
            else:
                self.redrive.disable()

            if self.status in ["RUNNING"]:
                self.abort.enable()
            else:
                self.abort.disable()

        @ui.refreshable
        def mermaid_graph():
            self.mermaid_graph = self.create_mermaid_graph()
            ui.mermaid(self.mermaid_graph).classes("w-full flex justify-center")

        @ui.refreshable
        def generated_files():
            self.files = self.list_created_files()

            if not self.files:
                ui.label().classes("text-sm text-gray-700 flex items-center gap-2").add_slot(
                    "default",
                    '<i class="material-icons">warning</i> Any files generated',
                )

            for file in self.files:
                tfile = "/".join(file.split("/")[2:])
                with (
                    ui.grid(columns=2)
                    .classes("w-full items-center -px-5 -my-1 hover:bg-gray-100 rounded gap-2 -ml-2")
                    .style("grid-template-columns: 80% 20%")
                ):
                    ui.label(tfile).classes("text-sm break-all w-full")
                    ui.button(icon="download", on_click=partial(self._download_file, tfile)).props("flat dense").classes(
                        "justify-self-end aspect-square w-8 h-8 min-w-0 transition-colors bg-red text-white"
                    )

        async def check_for_updates():
            # Get fresh data, bypassing cache
            self.get_execution_details.cache_clear()
            self.get_states_info.cache_clear()

            current_details = self.get_execution_details()
            current_status = current_details.get("status")

            _, current_states_status = self.get_states_info()

            needs_refresh = False

            # Check if status changed
            if current_status != self.status:
                self.status = current_status
                self.execution_details = current_details
                needs_refresh = True

            # Check if states status changed
            if current_states_status != self.states_status:
                self.states_status = current_states_status
                needs_refresh = True

            # Only refresh if there were changes
            if needs_refresh:
                # Clear mermaid graph cache since it depends on updated data
                self.create_mermaid_graph.cache_clear()
                self.list_created_files.cache_clear()

                # Refresh all UI components that depend on the changed data
                execution_status.refresh()
                action_buttons.refresh()
                mermaid_graph.refresh()
                generated_files.refresh()

        # Update timer interval to a more reasonable value (e.g., 10 seconds)

        ui.timer(5, check_for_updates)

        with ui.card().classes("main-container p-4 h-full w-full -mt-2"):
            ui.label(f"Execution Details for {self.execution_id}").classes("text-2xl font-bold text-gray-800")

            with ui.grid(columns=2).classes("gap-4 w-full h-full -mt-2"):
                # Right column - Info, Actions, Files
                with ui.element("div").classes("w-full h-full gap-2 flex flex-col rounded"):
                    # Basic Information card
                    with ui.card().classes("n-card"):
                        ui.label("Basic Information").classes("text-xl font-bold mb-0 -mt-")
                        with ui.grid(columns=2).classes("gap-2"):
                            ui.label("Execution ID:").classes("font-bold")
                            ui.label(self.execution_id)

                            ui.label("Step Function Name:").classes("font-bold")
                            ui.label(self.step_function_name)

                            ui.label("Start Time:").classes("font-bold")
                            start_time = self.execution_details.get("startDate", "N/A")
                            ui.label(
                                start_time.strftime("%Y-%m-%d %H:%M:%S") if isinstance(start_time, datetime) else start_time
                            )

                            execution_status()

                    # Actions card
                    with ui.card().classes("n-card w-full"):
                        ui.label("Actions").classes("text-xl font-bold -mb-2 -mt-2")
                        with ui.element("div").classes("w-full grid grid-cols-2 md:grid-cols-4 gap-2"):
                            with ui.dialog() as dialog, ui.card():
                                input_json = InputViewer(self.execution_details)
                                input_json = await input_json.show_json_popup()
                                with ui.row().classes("justify-center w-full gap-4"):
                                    ui.button("Close", on_click=dialog.close).classes("w-40 bg-red text-white").props(
                                        "icon=close"
                                    )

                            ui.button("Input", on_click=dialog.open).classes("w-full bg-red text-white").props("icon=input")

                            with ui.dialog() as dialog, ui.card().style("width: 1200px; max-width: none"):
                                new_run = NewRunViewer(input_json)
                                await new_run.create_ui()
                                with ui.row().classes("justify-end w-full gap-4"):
                                    ui.button("Close", on_click=dialog.close).classes("w-40 bg-red text-white").props(
                                        "icon=close"
                                    )
                                    ui.button(
                                        "Submit",
                                        on_click=partial(new_run.submit, dialog),
                                    ).classes("w-40 bg-red text-white").props("icon=rocket_launch")

                            try:
                                ui.button("Relaunch", on_click=dialog.open).classes("w-full bg-red text-white").props(
                                    "icon=restart_alt"
                                )
                            except Exception as e:
                                show_notification(
                                    f"Error relaunching Step Function execution.\n{e!s}",
                                    notification_type="error",
                                )
                                raise

                            def abort_execution():
                                try:
                                    self._abort_step_function()
                                    ui.run_javascript("location.reload();")

                                except Exception as e:
                                    show_notification(
                                        f"Error stopping Step Function execution.\n{e!s}",
                                        notification_type="error",
                                    )
                                    raise

                            self.abort = (
                                ui.button("Abort", on_click=abort_execution)
                                .classes("w-full bg-red text-white")
                                .props("icon=cancel")
                            )

                            def redrive_execution():
                                try:
                                    self._redrive_step_function()
                                    ui.run_javascript("location.reload();")

                                except Exception as e:
                                    show_notification(
                                        f"Error redriving Step Function execution.\n{e!s}",
                                        type="error",
                                    )
                                    raise

                            self.redrive = (
                                ui.button("Redrive", on_click=redrive_execution)
                                .classes("w-full bg-red text-white")
                                .props("icon=account_tree")
                            )

                        action_buttons()

                    # Files card
                    with ui.card().classes("n-card flex-1"):
                        ui.label("Files").classes("text-xl font-bold -mb-2 -mt-2")
                        with ui.scroll_area().classes("w-full gap-0 flex h-full items-center justify-center -mt-2"):
                            generated_files()

                # Left column - State Transitions
                with ui.card().classes("n-card flex-1 h-full"):
                    ui.label("State Transitions").classes("text-xl font-bold mb-4")
                    with ui.scroll_area().classes("w-full h-full flex items-center justify-center -mt-4"):
                        mermaid_graph()


@ui.page("/execution/{step_function_name}/{execution_id}")
async def show_execution(execution_id):
    ui.page_title(execution_id)

    ui.add_head_html("""
        <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
    """)

    ui.add_head_html("""
        <link rel="stylesheet" href="/assets/styles/main.css">
    """)

    # Add the top banner
    with ui.element("div").classes("top-banner"):
        with ui.element("div").classes("banner-content"):
            # Logo section on the left
            with ui.element("div").classes("logo-section"):
                ui.label("Step Functions Manager").classes("text-white text-xl font-bold")

            # Buttons section on the right
            with ui.element("div").classes("buttons-section"):
                ui.button(icon="home", on_click=lambda: ui.navigate.to("/")).props("flat").classes("text-white")

                ui.button(icon="arrow_back", on_click=ui.navigate.back).props("flat").classes("text-white")

                ui.button(
                    icon="help",
                    on_click=lambda: ui.notify("Please, reach out to the NLP team"),
                ).props("flat").classes("text-white")

    # Wrap the main content in a container with top margin
    with ui.element("div").classes("content-wrapper"):
        viewer = ExecutionViewer(execution_id)

        await viewer.initialize()
        await viewer.create_ui()

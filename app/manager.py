from utils.app_storage import (
    get_selected_environment,
    get_selected_step_function_arn,
    get_selected_step_function_config_name,
)
from utils.config_loader import SFC


class StepFunctionManager:
    def __init__(self):
        self.environment_selected = get_selected_environment()
        self.step_functions = SFC.list_step_functions_per_environment(self.environment_selected)
        self.step_function_selected = get_selected_step_function_config_name()
        self.step_function_arn_selected = get_selected_step_function_arn()
        self.step_function_name = self.extract_step_function_name_from_arn(self.step_function_arn_selected)

    @staticmethod
    def extract_step_function_name_from_arn(arn):
        """Extract the function name from an AWS ARN."""
        try:
            return arn.split(":")[-1]
        except Exception:
            return ""

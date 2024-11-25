import os
import re
from enum import Enum
from pathlib import Path
from typing import Literal

import yaml
from loguru import logger as log
from pydantic import BaseModel, field_validator, model_validator


class ParameterType(str, Enum):
    string = "string"
    select = "select"
    text = "text"
    integer = "integer"
    boolean = "boolean"


# Define valid environment types
EnvironmentType = Literal["production", "development", "staging"]


class Environments(BaseModel):
    production: str | None = None
    development: str | None = None
    staging: str | None = None

    @field_validator("*")
    def validate_arn(cls, v):
        if v is None:
            return v
        arn_pattern = r"^arn:aws:states:[a-z0-9-]+:\d{12}:stateMachine:.+$"
        if not re.match(arn_pattern, v):
            error_msg = f"Invalid ARN format. Got: {v}."
            raise ValueError(error_msg)
        if not v.startswith("arn:aws:states:"):
            error_msg = f"Invalid ARN format. Must start with 'arn:aws:states:'. Got: {v}."
            raise ValueError(error_msg)
        return v


class Parameter(BaseModel):
    description: str
    type: ParameterType
    default: str | int | bool | None = None
    multiple: bool | None = None
    options: list[str] | None = None

    @model_validator(mode="after")
    def validate_options(self) -> "Parameter":
        if self.type == ParameterType.select:
            if not self.options:
                error_msg = "Options field is required when type is 'select'"
                raise ValueError(error_msg)
        elif self.options is not None:
            error_msg = f"Options field is not allowed when type is '{self.type}'"
            raise ValueError(error_msg)
        return self


class Files(BaseModel):
    output_directory: str


class StepFunctionYamlConfig(BaseModel):
    display_name: str
    environments: Environments
    parameters: dict[str, Parameter]
    files: Files


class StepFunctionConfig:
    def __init__(self):
        self.config_dir = "configs/"
        self.configs = self._load_all_configs()

    def _load_all_configs(self) -> dict[str, any]:
        """Load all step function configurations from YAML files."""
        configs = {}
        for filename in os.listdir(self.config_dir):
            if filename.endswith(".yaml"):
                file_path = Path(self.config_dir) / filename
                try:
                    with Path(file_path).open() as f:
                        yaml_content = yaml.safe_load(f)
                        # Validate the config using Pydantic
                        config = StepFunctionYamlConfig(**yaml_content)
                        configs[config.display_name] = yaml_content
                except Exception as e:
                    error_msg = f"Error loading config from {filename}: {e!s}"
                    log.error(error_msg)
                    continue
        return configs

    def get_step_function_params(self, name: str) -> dict[str, any]:
        """Get parameters for a specific step function."""
        config = self.configs.get(name)
        return config["parameters"] if config else {}

    def get_arn(self, name: str, environment: str) -> str:
        """Get ARN for a specific step function and environment."""
        try:
            return self.configs.get(name)["environments"].get(environment)
        except Exception:
            return ""

    def list_step_functions_per_environment(self, environment: str) -> list[str]:
        """List all step functions available for a specific environment."""
        return [k for k, v in self.configs.items() if environment in v["environments"]]

    def get_files_prefix(self, name: str, execution_id: str) -> str:
        """Get the S3 prefix for a specific step function and execution ID."""
        config = self.configs.get(name)
        output_directory = config["files"]["output_directory"] if config else ""
        return f"{output_directory}/{execution_id}/"


SFC = StepFunctionConfig()

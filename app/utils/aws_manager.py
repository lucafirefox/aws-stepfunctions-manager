import json
import os
from functools import lru_cache

import boto3
from botocore.exceptions import BotoCoreError, ClientError


class AWSManager:
    """Centralized manager for AWS operations"""

    @staticmethod
    @lru_cache(maxsize=64)
    def get_client(service_name: str):
        """Get cached boto3 client for specified service"""
        return boto3.client(service_name)

    def __init__(self):
        self.sfn_client = self.get_client("stepfunctions")
        self.s3_client = self.get_client("s3")
        self.secret_client = self.get_client("secretsmanager")

    def get_execution_details(self, execution_arn: str) -> dict:
        """Get details of a Step Function execution"""
        return self.sfn_client.describe_execution(executionArn=execution_arn)

    def get_step_function_details(self, step_function_arn: str) -> dict:
        """Get details of a Step Function state machine"""
        return self.sfn_client.describe_state_machine(stateMachineArn=step_function_arn)

    def list_executions(self, step_function_arn: str, max_results: int = 20) -> list[dict]:
        """List executions for a state machine"""
        response = self.sfn_client.list_executions(stateMachineArn=step_function_arn, maxResults=max_results)
        return response["executions"]

    def get_states_info(self, step_function_arn: str, execution_id: str) -> tuple:
        """
        Gets state machine definition and states status with minimal API calls.
        Returns state machine definition and current status of all states.
        """

        # Get state machine details - single API call
        step_function = self.get_step_function_details(step_function_arn=step_function_arn)

        # Parse definition and initialize states status
        definition_json = json.loads(step_function["definition"])
        all_states = definition_json["States"]
        states_status = {name: "NOT_STARTED" for name in all_states}

        # Get execution history and update status - paginated API calls
        paginator = self.sfn_client.get_paginator("get_execution_history")
        for page in paginator.paginate(executionArn=execution_id):
            for event in page["events"]:
                if "StateEntered" in event["type"]:
                    states_status[event["stateEnteredEventDetails"]["name"]] = "RUNNING"
                elif "StateExited" in event["type"]:
                    states_status[event["stateExitedEventDetails"]["name"]] = "COMPLETED"

        return definition_json, states_status

    def start_execution(
        self,
        step_function_arn: str,
        input_data: dict,
        execution_name: str | None = None,
    ) -> dict:
        """Start a new state machine execution"""
        params = {"stateMachineArn": step_function_arn, "input": input_data}

        if execution_name:
            params["name"] = execution_name

        return self.sfn_client.start_execution(**params)

    def stop_execution(self, execution_arn: str) -> dict:
        """Stop a running execution"""
        return self.sfn_client.stop_execution(executionArn=execution_arn)

    def redrive_execution(self, execution_arn: str) -> dict:
        """Redrive a failed execution"""
        return self.sfn_client.redrive_execution(executionArn=execution_arn)

    def list_s3_objects(self, bucket: str, prefix: str, sort_by_date: bool = True) -> list[str]:
        """
        List objects in S3 bucket with given prefix

        Args:
            bucket (str): Name of the S3 bucket
            prefix (str): Prefix to filter objects
            sort_by_date (bool): If True, sort objects by creation date (newest first)

        Returns:
            list[str]: List of object keys
        """
        response = self.s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)

        if "Contents" not in response:
            return []

        if sort_by_date:
            # Sort objects by LastModified date, newest first
            sorted_objects = sorted(response["Contents"], key=lambda x: x["LastModified"], reverse=True)
            return [obj["Key"] for obj in sorted_objects]
        return [obj["Key"] for obj in response["Contents"]]

    def get_execution_counts(self, step_function_arn: str) -> dict[str, int]:
        """Get counts of executions by status"""
        counts = {
            "RUNNING": 0,
            "SUCCEEDED": 0,
            "FAILED": 0,
            "TIMED_OUT": 0,
            "ABORTED": 0,
        }

        try:
            paginator = self.sfn_client.get_paginator("list_executions")
            for page in paginator.paginate(stateMachineArn=step_function_arn):
                for execution in page["executions"]:
                    status = execution["status"]
                    counts[status] = counts.get(status, 0) + 1

        except (BotoCoreError, ClientError) as e:
            error_msg = f"Error fetching execution counts: {e}"
            raise ValueError(error_msg) from e

        return counts

    def get_presigned_url(self, bucket_name: str, object_key: str, expiration: int = 5) -> bool:
        """Generate presigned URL for S3 object"""

        return self.s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket_name, "Key": object_key},
            ExpiresIn=expiration,
        )

    @staticmethod
    def get_execution_url(execution_arn: str) -> str:
        """Generate AWS Console URL for the execution given a Step Function execution ARN."""
        region = execution_arn.split(":")[3]
        return f"https://{region}.console.aws.amazon.com/states/home?region={region}#/executions/details/{execution_arn}"

    @staticmethod
    def get_execution_arn(
        step_function_name: str,
        execution_id: str,
        region: str = os.environ.get("AWS_DEFAULT_REGION"),
        account_id: str = os.environ.get("AWS_ACCOUNT_ID"),
    ) -> str:
        """Generate Step Function execution ARN given the required parameters."""
        return f"arn:aws:states:{region}:{account_id}:execution:{step_function_name}:{execution_id}"

    def get_secret(self, secret_name: str, key_to_extract: str) -> str:
        """Get a secret value from AWS Secrets Manager."""
        response = self.secret_client.get_secret_value(SecretId=secret_name)

        if "SecretString" in response:
            secret = json.loads(response["SecretString"])
            return secret.get(key_to_extract)

        error_msg = "SecretString not found in response"
        raise ValueError(error_msg)


aws_manager = AWSManager()

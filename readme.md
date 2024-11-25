<div align="center">
  <img src="docs/logo.svg" width="150px" alt="Logo">

  <h1>Step Function Manager</h1>
  
  <p><em>WebApp for AWS Step Functions Monitoring and Control</em></p>

  <br/>

  <p>
    <a href="#"><img src="https://img.shields.io/badge/AWS-232F3E?style=for-the-badge&logo=aws&logoColor=white" alt="AWS"></a>
    <a href="#"><img src="https://img.shields.io/badge/NiceGUI-3B82F6?style=for-the-badge&logo=python&logoColor=white" alt="NiceGUI"></a>
    <a href="#"><img src="https://img.shields.io/badge/Pydantic-E92063?style=for-the-badge&logo=Pydantic&logoColor=white" alt="Pydantic"></a>
    <a href="#"><img src="https://img.shields.io/badge/Terraform-7B42BC?style=for-the-badge&logo=Terraform&logoColor=white" alt="Terraform"></a>
    <a href="#"><img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=Python&logoColor=white" alt="Python"></a>
    <a href="#"><img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=Docker&logoColor=white" alt="Docker"></a>
    <a href="#"><img src="https://img.shields.io/badge/Poetry-60A5FA?style=for-the-badge&logo=Poetry&logoColor=white" alt="Poetry"></a>
    <a href="#"><img src="https://img.shields.io/badge/GNU%20Bash-4EAA25?style=for-the-badge&logo=GNU-Bash&logoColor=white" alt="Bash"></a>
  </p>

  <br/>
  
</div>

<div>

## About

Step Function Manager is a web-based application built with NiceGUI that provides a user-friendly interface for monitoring and controlling AWS Step Functions. The application runs a web server that allows users to:

- View all Step Function executions across different environments
- Monitor execution status and progress in real-time
- Start new Step Function executions
- Stop running executions
- Redrive failed executions
- View detailed execution histories and error messages
- Track execution metrics and duration

The interface is designed to be intuitive and responsive, making it easier to manage complex Step Function workflows without needing to use the AWS Console directly.

</div>


<div>

### Key Directories

- **app/**: Contains the main application source code, organized into modules for API, core logic, data models, and UI components
  
- **assets/**: Stores static files used by the web interface
  - CSS files for styling
  - Favicon files for browser icons
  
- **configs/**: Houses configuration files for Step Function pipelines
  - Each YAML file defines parameters for a specific pipeline
  - Used to specify input parameters, environment variables, and other pipeline-specific settings
  
</div>

<div>

## Demo

[![Demo]](https://vimeo.com/1033084453/15e3f68458?share=copy)


</div>

<br/>

<div>

## How to run it

```shell
docker run -d \
  --name stepfunctionsmanager \
  -p 8080:8080 \
  --build-arg ... \
  --restart always \
  image-name
```

</div>

<br/>

<div>

## IAM Permissions

### Required Permissions

#### Step Functions
```json
{
    "states:DescribeExecution",
    "states:DescribeStateMachine",
    "states:ListExecutions",
    "states:GetExecutionHistory",
    "states:StartExecution",
    "states:StopExecution",
    "states:RedriveExecution"
}
```

#### S3
```json
{
    "s3:ListBucket",
    "s3:GetObject"
}
```

#### Secrets Manager
```json
{
    "secretsmanager:GetSecretValue"
}
```

### Resource Scopes

| Service         | Resource Pattern                                               |
|-----------------|----------------------------------------------------------------|
| Secrets Manager | `arn:aws:secretsmanager:*:*:secret:<DEFINE YOUR SECRET>*`      |
| S3              | `arn:aws:s3:::<DEFINE YOUR BUCKET>*`                           |
| Step Functions  | `arn:aws:states:*:*:stateMachine:<DEFINE YOUR ENVIRONMENTS>-*` |

</div>

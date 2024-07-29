# DORA Metrics CDK Project

This CDK project facilitates the tracking of the four key metrics described by DORA ( DevOps Research and Assessment):

Change Failure Rate: The percentage of deployments causing a failure in production \
Deployment Frequency: How often an organization successfully releases to production \
Lead Time for Changes: The amount of time it takes a commit to get into production \
Mean Time to Restore: How long it takes an organization to recover from a failure in production


# Architecture

Our metric calculation process runs in three steps:
1.	In tooling account, we send events from AWS CodePipeline to the default event bus of Amazon EventBridge. This is not limited to the events relevant for the four keys.
2.	Targets for the event matching rules are custom event buses with stricter rules aligned to the individual metrics. We use resource-based policies to allow the tooling account to invoke custom event bus in the operations account.
3.	AWS Lambda functions put metric data to Amazon CloudWatch where it’s aggregated in the respective metrics insights. From Amazon CloudWatch, you can also push the metrics to another designated dashboard e.g., in Amazon Managed Grafana.
4.	As part of the data collection, AWS Lambda will also gather relevant commit activity from GitHub for lead time for changes metric, and OpsItem data for change failure rate and mean time to recovery metrics.

![DORA metric setup for AWS CodePipeline deployments.png](images%2FDORA%20metric%20setup%20for%20AWS%20CodePipeline%20deployments.png)

# Provisioned resources

The following figure shows the resources you’ll launch with each CloudFormation stack. This includes six AWS CloudFormation stacks in operations account. The first stack sets up log integration for GitHub commit activity. Four stacks contain a Lambda function which creates one of the DORA metrics. The sixth stack creates the consolidated dashboard in Amazon CloudWatch. The EventBridge stack in the tooling account includes Amazon EventBridge rules with a target of the central event bus in operations account, plus AWS IAM role with cross-account access to put events in the operations account.
![Figure 3. Resources provisioned with this solution.png](images%2FFigure%203.%20Resources%20provisioned%20with%20this%20solution.png)

## Metric calculation process

We calculate the DORA metrics in our solution as follows: 
1.	Deployment frequency equals the count of deployments with status Succeeded from AWS CodePipeline (per day/week/month). 
2.	Lead time for changes equals the average duration from first commit for the change until the time of deployment to production i.e., with status Succeeded from AWS CodePipeline (per day/week/month).
3.	Change failure rate equals the count of changes in production which led to service failure, logged as OpsItem, divided by all deployments with status Succeeded in production (per day/week/month). 
4.	Mean time to recovery equals the average duration from when an incident was logged in AWS OpsCenter as OpsItem to when the AWS CodePipeline has successfully launched with branch name referencing the OpsItem ID.
The following figure provides a simple visualization of the calculation logic. The deployment times of two features fall into the DORA reporting period so deployment frequency is two (deployments). Lead time for change calculates the average duration from first commit to deployment in production. One change led to service interruption so change failure rate is one out of two, or 50%. The mean time to recovery calculates the duration from service interruption until the updated change is re-deployed. The reporting period for all metrics is daily, weekly, and monthly.
![Calculating the DORA metrics along the development lifecycle](image.png)

## Project Structure
```
|-- README.md
|-- cdk
|   |-- app.py
|   |-- cdk.json
|   |-- constants.py
|   |-- stacks
|   |   |-- __init__.py
|   |   |-- change_failure_rate_stack.py
|   |   |-- deployment_frequency_stack.py
|   |   |-- lead_time_for_change_stack.py
|   |   |-- mean_time_to_restore_stack.py
|   |   |-- tooling_account_stack.py
|   |   |-- github_setup_stack.py
|   |   `-- dashboard_stack.py
|   |-- lambdas
|   |   |-- dora_custom_change_failure_rate_metric
|   |   |   `-- index.py
|   |   |-- dora_custom_deployment_frequency_metric
|   |   |   `-- index.py
|   |   |-- dora_custom_lead_time_for_change_metric
|   |   |   `-- index.py
|   |   `-- dora_custom_mean_time_to_restore_metric
|   |   |    `-- index.py
|   |   `-- kinesis_data_transformation_lambda
|   |   |   `-- index.py
|   |   `-- github_signature_verification_lambda
|   |   |   `-- index.py
|   `-- tests
|       |-- __init__.py
|       `-- unit
|           |-- __init__.py
|           `-- test_dora_stack.py
|-- requirements.txt
`-- source.bat
```

`cdk`: The main Cloud Development Kit (CDK) directory. \
`app.py`: Main application entry point. \
`cdk.json`: CDK configuration file. The `cdk.json` tells the CDK Toolkit how to execute your Dora app. \
`constants.py`: Constants utilized throughout the CDK project. \
`stacks`: Contains the CDK stacks for each of the DORA metrics. \
`change_failure_rate_stack.py`: CDK stack for the Change Failure Rate metric. \
`deployment_frequency_stack.py`: CDK stack for Deployment Frequency. \
`lead_time_for_change_stack.py`: CDK stack for Lead Time for Changes. \
`mean_time_to_restore_stack.py`: CDK stack for Mean Time to Restore. \
`tooling_account_stack.py`: CDK stack for tooling account configuration.\
`github_setup_stack.py`: CDK stack for Github logs collection and setup.\
`dashboard_stack.py` : CDK stack for creating Dashboards.\
`lambdas`: Folder for all AWS Lambda functions that are utilized by the different metric stacks. \
`dora_custom_change_failure_rate_metric/index.py`: Lambda function code for Change Failure Rate metric. \
`dora_custom_deployment_frequency_metric/index.py`: Lambda function code for Deployment Frequency. \
`dora_custom_lead_time_for_change_metric/index.py`: Lambda function code for Lead Time for Changes. \
`dora_custom_mean_time_to_restore_metric/index.py`: Lambda functions code for Mean Time to Restore. This will calculate the downtime and time taken to restore any specific incident.
`github_signature_verification_lambda/index.py`: Proxy Lambda code with is integrated in API gateway to verify Github signature.
`kinesis_data_transformation_lambda/index.py`: Lambda functions code for transforming and process the incoming records format before sending it to S3.
`tests`: Contains unit tests for the CDK stack. \
`test_dora_stack.py`: Unit tests for the main DORA CDK stack. \
`requirements.txt`: List of Python dependencies for this project.

### Configuration

Before you start deploying or working with this codebase, there are a few configurations you need to complete in the constants.py file which in the cdk/ directory.
`constants.py`
This file stores various constants that are utilized throughout the project. Here's a brief overview:

`TOOLING_ACCOUNT_ID` & `TOOLING_ACCOUNT_REGION`: These represent the AWS Account ID and region for CodePipeline where your infrastructure-as-code resides.\

`OPS_ACCOUNT_ID & OPS_ACCOUNT_REGION`: These are for your centralized Ops AWS Account ID and its region.

`TOOLING_CROSS_ACCOUNT_LAMBDA_ROLE`: The IAM Role that allows for cross-account Lambda function execution.

`DEFAULT_MAIN_BRANCH`: This is the default branch in your Code repository that's used to deploy to Production. It is set to master by default.

#### Important:
Before running any code, make sure you fill in the necessary values in the constants.py file.
The code will not work correctly without these values.


## Getting Started

This project is set up like a standard Python project.  The initialization process also creates
a virtualenv within this project, stored under the .venv directory.

### Prerequisites

Ensure you have `python3` with the `venv` package accessible in your path.

Setup AWS CLI:  https://docs.aws.amazon.com/cli/latest/userguide/getting-started-quickstart.html

If for any reason the automatic creation of the virtualenv fails, you can create the virtualenv
manually too once the init process completes

### Setting Up the Environment
1. Create a virtual environment on MacOS and Linux:

```
$ python3 -m venv .venv
```

2. Activate the virtual environment:
On MacOS and Linux:

```
$ source .venv/bin/activate
```

On Windows platform:

```
% .venv\Scripts\activate.bat
```

3. Install the required Python packages:

```
$ pip install -r requirements.txt
```
## Code Quality Checks
```bash
./scripts/code_quality_checks.sh
```

### Deployment
Switch Directory
```
$ cd cdk
```
To cdk bootstrap the environment:

```
cdk bootstrap --profile <OpsAccountProfile>
```

To synthesize the CloudFormation template for this project:

```
$ cdk synth
```
To deploy a specific stack,
```
$ cdk deploy <Stack-Name> --profile <OpsAccountProfile>

```
for example, the Change Failure Rate Stack:
```
$ cdk deploy DoraOpsChangeFailureRateStack --profile <OpsAccountProfile>
$ cdk deploy DoraToolingEventBridgeStack --profile <ToolingAccountProfile>

```

### Tests
To run the provided tests:

```
$ pytest ./tests/unit/*.py
```

## Additional Commands

 * `cdk ls`          list all stacks in the app
 * `cdk synth`       emits the synthesized CloudFormation template
 * `cdk deploy`      deploy this stack to your default AWS account/region
 * `cdk diff`        compare deployed stack with current state
 * `cdk docs`        open CDK documentation


### Security
See [CONTRIBUTING.md](CONTRIBUTING.md) for more information.

## License
This library is licensed under the MIT-0 License. See the LICENSE file.

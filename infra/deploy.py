#!/usr/bin/env python3
"""
DocuShield AWS Infrastructure Deployment Automation
===================================================
Automates 100% of the AWS infrastructure provisioning using AWS CloudFormation and Boto3.
Zero console clicks required.

Usage:
    python infra/deploy.py --deploy             # Deploy or update stack to AWS
    python infra/deploy.py --status             # Check current stack status
    python infra/deploy.py --local              # Prepare local environment config
"""

import sys
import os
import time
import argparse
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

TEMPLATE_PATH = PROJECT_ROOT / "infra" / "cloudformation-template.yaml"
ENV_FILE_PATH = PROJECT_ROOT / ".env"
STACK_NAME = os.getenv("DOCUSHIELD_STACK_NAME", "docushield-resilience-stack")
REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")


def get_boto3_session():
    try:
        import boto3
        session = boto3.Session(region_name=REGION)
        # Test credentials
        sts = session.client("sts")
        identity = sts.get_caller_identity()
        return session, identity
    except Exception as e:
        return None, str(e)


def deploy_cloudformation(session, stack_name, template_body, environment="dev"):
    cf_client = session.client("cloudformation")
    
    print(f"[*] Validating CloudFormation template at {TEMPLATE_PATH}...")
    try:
        cf_client.validate_template(TemplateBody=template_body)
        print("[+] Template is valid.")
    except Exception as e:
        print(f"[-] Template validation error: {e}")
        return False, {}

    print(f"[*] Checking if stack '{stack_name}' already exists...")
    stack_exists = False
    try:
        cf_client.describe_stacks(StackName=stack_name)
        stack_exists = True
        print(f"[*] Stack '{stack_name}' exists. Preparing update...")
    except cf_client.exceptions.ClientError:
        print(f"[*] Stack '{stack_name}' does not exist. Creating new stack...")

    params = [
        {"ParameterKey": "Environment", "ParameterValue": environment},
        {"ParameterKey": "ProjectName", "ParameterValue": "docushield"}
    ]

    try:
        if stack_exists:
            try:
                cf_client.update_stack(
                    StackName=stack_name,
                    TemplateBody=template_body,
                    Parameters=params,
                    Capabilities=["CAPABILITY_IAM", "CAPABILITY_NAMED_IAM"]
                )
                waiter_name = "stack_update_complete"
            except cf_client.exceptions.ClientError as err:
                if "No updates are to be performed" in str(err):
                    print("[+] Stack is already up to date. No changes needed.")
                    return True, get_stack_outputs(cf_client, stack_name)
                raise
        else:
            cf_client.create_stack(
                StackName=stack_name,
                TemplateBody=template_body,
                Parameters=params,
                Capabilities=["CAPABILITY_IAM", "CAPABILITY_NAMED_IAM"],
                OnFailure="ROLLBACK"
            )
            waiter_name = "stack_create_complete"

        print(f"[*] Waiting for CloudFormation operation to finish ({waiter_name})...")
        print("[*] (This typically takes 60 - 90 seconds while provisioning S3, SQS & DynamoDB)")

        waiter = cf_client.get_waiter(waiter_name)
        waiter.wait(
            StackName=stack_name,
            WaiterConfig={"Delay": 5, "MaxAttempts": 40}
        )
        print(f"[+] Stack '{stack_name}' successfully provisioned!")
        return True, get_stack_outputs(cf_client, stack_name)

    except Exception as err:
        print(f"[-] CloudFormation deployment error: {err}")
        return False, {}


def get_stack_outputs(cf_client, stack_name):
    res = cf_client.describe_stacks(StackName=stack_name)
    outputs = {}
    for stack in res.get("Stacks", []):
        for out in stack.get("Outputs", []):
            outputs[out["OutputKey"]] = out["OutputValue"]
    return outputs


def write_env_file(outputs, local_mode=False):
    if local_mode:
        env_content = f"""# ==========================================================
# DocuShield Configuration - LOCAL RESILIENCE SIMULATOR
# ==========================================================
APP_ENV=local
SIMULATE_AWS=true
AWS_DEFAULT_REGION={REGION}

# Local Storage Paths
S3_RAW_BUCKET=docushield-local-raw
S3_PROCESSED_BUCKET=docushield-local-processed

# Local Queues
SQS_TASK_QUEUE_URL=http://localhost:8000/mock-sqs/tasks
SQS_DLQ_URL=http://localhost:8000/mock-sqs/dlq

# Local Database & Alerts
DYNAMODB_JOBS_TABLE=docushield-local-jobs
SNS_ALERTS_TOPIC_ARN=arn:aws:sns:local:000000000000:docushield-alerts

# Server Configuration
PORT=8000
HOST=0.0.0.0
"""
    else:
        env_content = f"""# ==========================================================
# DocuShield Configuration - AWS PRODUCTION / CLOUD STACK
# Provisioned automatically via CloudFormation
# ==========================================================
APP_ENV=aws
SIMULATE_AWS=false
AWS_DEFAULT_REGION={REGION}

# Amazon S3 Buckets
S3_RAW_BUCKET={outputs.get("RawBucketName", "")}
S3_PROCESSED_BUCKET={outputs.get("ProcessedBucketName", "")}

# Amazon SQS Queues
SQS_TASK_QUEUE_URL={outputs.get("TaskQueueUrl", "")}
SQS_DLQ_URL={outputs.get("DeadLetterQueueUrl", "")}

# Amazon DynamoDB Table
DYNAMODB_JOBS_TABLE={outputs.get("JobsTableName", "")}

# Amazon SNS Alerting Topic
SNS_ALERTS_TOPIC_ARN={outputs.get("AlertsTopicArn", "")}

# Server Configuration
PORT=8000
HOST=0.0.0.0
"""
    with open(ENV_FILE_PATH, "w", encoding="utf-8") as f:
        f.write(env_content)
    print(f"[+] Configuration saved to: {ENV_FILE_PATH}")


def check_status(session, stack_name):
    if not session:
        print("[-] AWS Credentials not found. Cannot check AWS stack status.")
        return
    cf_client = session.client("cloudformation")
    try:
        res = cf_client.describe_stacks(StackName=stack_name)
        stack = res["Stacks"][0]
        print(f"\n=======================================================")
        print(f"Stack Name:   {stack['StackName']}")
        print(f"Status:       {stack['StackStatus']}")
        print(f"Created:      {stack.get('CreationTime')}")
        print(f"Last Updated: {stack.get('LastUpdatedTime', 'N/A')}")
        print("Outputs:")
        for out in stack.get("Outputs", []):
            print(f"  • {out['OutputKey']}: {out['OutputValue']}")
        print(f"=======================================================\n")
    except Exception as e:
        print(f"[-] Could not describe stack '{stack_name}': {e}")


def main():
    parser = argparse.ArgumentParser(description="DocuShield AWS Automated IaC Deployer")
    parser.add_argument("--deploy", action="store_true", help="Deploy or update AWS CloudFormation stack")
    parser.add_argument("--status", action="store_true", help="Describe current CloudFormation stack")
    parser.add_argument("--local", action="store_true", help="Set up local environment mode without AWS charges")
    parser.add_argument("--region", default=REGION, help=f"AWS Region (default: {REGION})")
    args = parser.parse_args()

    print("\n=======================================================")
    print("   DocuShield - AWS Infrastructure as Code Deployer    ")
    print("=======================================================")

    if args.local:
        print("[*] Generating Local Simulation environment config...")
        write_env_file({}, local_mode=True)
        print("[+] System configured for Local Simulation Mode.")
        return

    session, identity_or_err = get_boto3_session()

    if session is None:
        print(f"\n[!] Notice: AWS credentials not currently active in environment:")
        print(f"    {identity_or_err}")
        print("[*] To deploy to live AWS, set AWS_ACCESS_KEY_ID & AWS_SECRET_ACCESS_KEY,")
        print("    or run 'aws configure'.")
        print("[*] Setting up Local Resilience Simulator configuration as fallback...\n")
        write_env_file({}, local_mode=True)
        return

    print(f"[+] Authenticated to AWS as:")
    print(f"    Account: {identity_or_err.get('Account')}")
    print(f"    User/Role: {identity_or_err.get('Arn')}")
    print(f"    Region: {args.region}")

    if args.status:
        check_status(session, STACK_NAME)
        return

    if args.deploy or not sys.argv[1:]:
        with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
            template_body = f.read()

        success, outputs = deploy_cloudformation(session, STACK_NAME, template_body)
        if success:
            write_env_file(outputs, local_mode=False)
            print("\n[+] SUCCESS: Infrastructure provisioning complete!")
            print("[+] You may now start the backend with:")
            print("    python backend/main.py\n")
        else:
            print("\n[-] ERROR: Infrastructure deployment failed. Check CloudFormation logs.")
            sys.exit(1)


if __name__ == "__main__":
    main()

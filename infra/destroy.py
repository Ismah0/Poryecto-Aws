#!/usr/bin/env python3
"""
DocuShield AWS Infrastructure Teardown Script
=============================================
Safely empties S3 buckets and destroys CloudFormation stack to prevent any ongoing costs.

Usage:
    python infra/destroy.py --force
"""

import sys
import os
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

STACK_NAME = os.getenv("DOCUSHIELD_STACK_NAME", "docushield-resilience-stack")
REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")


def empty_bucket(s3_client, bucket_name):
    print(f"[*] Empting S3 bucket: {bucket_name}...")
    try:
        # Delete object versions
        paginator = s3_client.get_paginator("list_object_versions")
        for page in paginator.paginate(Bucket=bucket_name):
            delete_items = []
            for version in page.get("Versions", []):
                delete_items.append({"Key": version["Key"], "VersionId": version["VersionId"]})
            for marker in page.get("DeleteMarkers", []):
                delete_items.append({"Key": marker["Key"], "VersionId": marker["VersionId"]})
            if delete_items:
                s3_client.delete_objects(Bucket=bucket_name, Delete={"Objects": delete_items})
        print(f"[+] Bucket '{bucket_name}' emptied.")
    except Exception as e:
        print(f"[-] Note on bucket '{bucket_name}': {e}")


def main():
    parser = argparse.ArgumentParser(description="Teardown DocuShield AWS Infrastructure")
    parser.add_argument("--force", action="store_true", help="Confirm teardown without prompting")
    args = parser.parse_args()

    print("\n=======================================================")
    print("   DocuShield - AWS Infrastructure Teardown Utility    ")
    print("=======================================================")

    if not args.force:
        confirm = input(f"[?] Are you sure you want to delete stack '{STACK_NAME}' and all data? (y/N): ")
        if confirm.lower() != "y":
            print("[-] Teardown cancelled.")
            return

    try:
        import boto3
        session = boto3.Session(region_name=REGION)
        cf = session.client("cloudformation")
        s3 = session.client("s3")
    except Exception as e:
        print(f"[-] Could not connect to AWS: {e}")
        return

    # Look up bucket names from stack outputs
    try:
        res = cf.describe_stacks(StackName=STACK_NAME)
        for out in res["Stacks"][0].get("Outputs", []):
            if "Bucket" in out["OutputKey"]:
                empty_bucket(s3, out["OutputValue"])
    except Exception as e:
        print(f"[*] Could not inspect stack outputs (stack might not exist): {e}")

    print(f"[*] Deleting CloudFormation stack: {STACK_NAME}...")
    try:
        cf.delete_stack(StackName=STACK_NAME)
        print("[*] Waiting for stack deletion to complete...")
        waiter = cf.get_waiter("stack_delete_complete")
        waiter.wait(StackName=STACK_NAME, WaiterConfig={"Delay": 5, "MaxAttempts": 40})
        print(f"[+] Stack '{STACK_NAME}' successfully deleted!")
    except Exception as e:
        print(f"[-] Stack deletion error: {e}")


if __name__ == "__main__":
    main()

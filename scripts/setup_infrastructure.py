"""
AWS Infrastructure Setup Script for VaniVerse

This script creates the necessary AWS resources:
- S3 buckets for audio storage
- IAM roles and policies for Lambda execution
"""

import boto3
import json
import sys
from botocore.exceptions import ClientError

# Add parent directory to path for imports
sys.path.insert(0, '..')
from src.config import Config


def create_s3_buckets():
    """Create S3 buckets for audio input and output"""
    s3_client = boto3.client('s3', region_name=Config.AWS_REGION)
    
    buckets = [
        Config.AUDIO_INPUT_BUCKET,
        Config.AUDIO_OUTPUT_BUCKET
    ]
    
    for bucket_name in buckets:
        try:
            # Check if bucket exists
            s3_client.head_bucket(Bucket=bucket_name)
            print(f"✓ Bucket {bucket_name} already exists")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                # Create bucket
                try:
                    if Config.AWS_REGION == 'us-east-1':
                        s3_client.create_bucket(Bucket=bucket_name)
                    else:
                        s3_client.create_bucket(
                            Bucket=bucket_name,
                            CreateBucketConfiguration={'LocationConstraint': Config.AWS_REGION}
                        )
                    print(f"✓ Created bucket: {bucket_name}")
                    
                    # Enable versioning
                    s3_client.put_bucket_versioning(
                        Bucket=bucket_name,
                        VersioningConfiguration={'Status': 'Enabled'}
                    )
                    print(f"  - Enabled versioning for {bucket_name}")
                    
                    # Enable encryption
                    s3_client.put_bucket_encryption(
                        Bucket=bucket_name,
                        ServerSideEncryptionConfiguration={
                            'Rules': [
                                {
                                    'ApplyServerSideEncryptionByDefault': {
                                        'SSEAlgorithm': 'AES256'
                                    }
                                }
                            ]
                        }
                    )
                    print(f"  - Enabled encryption for {bucket_name}")
                    
                except ClientError as create_error:
                    print(f"✗ Error creating bucket {bucket_name}: {create_error}")
                    return False
            else:
                print(f"✗ Error checking bucket {bucket_name}: {e}")
                return False
    
    return True


def create_iam_role():
    """Create IAM role for Lambda execution"""
    iam_client = boto3.client('iam', region_name=Config.AWS_REGION)
    
    role_name = 'vaniverse-lambda-execution-role'
    
    # Trust policy for Lambda
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": "lambda.amazonaws.com"
                },
                "Action": "sts:AssumeRole"
            }
        ]
    }
    
    try:
        # Check if role exists
        iam_client.get_role(RoleName=role_name)
        print(f"✓ IAM role {role_name} already exists")
        role_arn = iam_client.get_role(RoleName=role_name)['Role']['Arn']
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchEntity':
            # Create role
            try:
                response = iam_client.create_role(
                    RoleName=role_name,
                    AssumeRolePolicyDocument=json.dumps(trust_policy),
                    Description='Execution role for VaniVerse Lambda orchestrator'
                )
                role_arn = response['Role']['Arn']
                print(f"✓ Created IAM role: {role_name}")
            except ClientError as create_error:
                print(f"✗ Error creating IAM role: {create_error}")
                return None
        else:
            print(f"✗ Error checking IAM role: {e}")
            return None
    
    # Attach policies
    policies = [
        'arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole',  # CloudWatch Logs
    ]
    
    for policy_arn in policies:
        try:
            iam_client.attach_role_policy(
                RoleName=role_name,
                PolicyArn=policy_arn
            )
            print(f"  - Attached policy: {policy_arn.split('/')[-1]}")
        except ClientError as e:
            if e.response['Error']['Code'] != 'EntityAlreadyExists':
                print(f"  - Warning: Could not attach policy {policy_arn}: {e}")
    
    # Create custom policy for VaniVerse services
    custom_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject"
                ],
                "Resource": [
                    f"arn:aws:s3:::{Config.AUDIO_INPUT_BUCKET}/*",
                    f"arn:aws:s3:::{Config.AUDIO_OUTPUT_BUCKET}/*"
                ]
            },
            {
                "Effect": "Allow",
                "Action": [
                    "s3:ListBucket"
                ],
                "Resource": [
                    f"arn:aws:s3:::{Config.AUDIO_INPUT_BUCKET}",
                    f"arn:aws:s3:::{Config.AUDIO_OUTPUT_BUCKET}"
                ]
            },
            {
                "Effect": "Allow",
                "Action": [
                    "transcribe:StartTranscriptionJob",
                    "transcribe:GetTranscriptionJob"
                ],
                "Resource": "*"
            },
            {
                "Effect": "Allow",
                "Action": [
                    "polly:SynthesizeSpeech"
                ],
                "Resource": "*"
            },
            {
                "Effect": "Allow",
                "Action": [
                    "bedrock:InvokeModel",
                    "bedrock:InvokeAgent"
                ],
                "Resource": "*"
            },
            {
                "Effect": "Allow",
                "Action": [
                    "bedrock-agent-runtime:Retrieve",
                    "bedrock-agent-runtime:RetrieveAndGenerate",
                    "bedrock-agent-runtime:InvokeAgent"
                ],
                "Resource": "*"
            }
        ]
    }
    
    custom_policy_name = 'vaniverse-lambda-policy'
    
    try:
        # Check if policy exists
        account_id = boto3.client('sts').get_caller_identity()['Account']
        custom_policy_arn = f"arn:aws:iam::{account_id}:policy/{custom_policy_name}"
        
        try:
            iam_client.get_policy(PolicyArn=custom_policy_arn)
            print(f"✓ Custom policy {custom_policy_name} already exists")
        except ClientError:
            # Create custom policy
            response = iam_client.create_policy(
                PolicyName=custom_policy_name,
                PolicyDocument=json.dumps(custom_policy),
                Description='Custom policy for VaniVerse Lambda function'
            )
            custom_policy_arn = response['Policy']['Arn']
            print(f"✓ Created custom policy: {custom_policy_name}")
        
        # Attach custom policy to role
        iam_client.attach_role_policy(
            RoleName=role_name,
            PolicyArn=custom_policy_arn
        )
        print(f"  - Attached custom policy to role")
        
    except ClientError as e:
        print(f"  - Warning: Could not create/attach custom policy: {e}")
    
    return role_arn


def configure_s3_event_notification():
    """Configure S3 event notification to trigger Lambda (placeholder)"""
    print("\n⚠ S3 Event Notification Configuration:")
    print("  This will be configured after Lambda function deployment.")
    print("  After deploying Lambda, run: python scripts/configure_s3_trigger.py")
    return True


def main():
    """Main setup function"""
    print("=" * 60)
    print("VaniVerse AWS Infrastructure Setup")
    print("=" * 60)
    print()
    
    print(f"Region: {Config.AWS_REGION}")
    print()
    
    # Step 1: Create S3 buckets
    print("Step 1: Creating S3 Buckets")
    print("-" * 60)
    if not create_s3_buckets():
        print("\n✗ Failed to create S3 buckets")
        return False
    print()
    
    # Step 2: Create IAM role
    print("Step 2: Creating IAM Role and Policies")
    print("-" * 60)
    role_arn = create_iam_role()
    if not role_arn:
        print("\n✗ Failed to create IAM role")
        return False
    print(f"\nRole ARN: {role_arn}")
    print()
    
    # Step 3: S3 event notification (placeholder)
    print("Step 3: S3 Event Notification")
    print("-" * 60)
    configure_s3_event_notification()
    print()
    
    print("=" * 60)
    print("✓ Infrastructure setup complete!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Update your .env file with the Role ARN:")
    print(f"   LAMBDA_ROLE_ARN={role_arn}")
    print("2. Deploy the Lambda function")
    print("3. Configure S3 event notification:")
    print("   python scripts/configure_s3_trigger.py")
    print()
    
    return True


if __name__ == '__main__':
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Setup failed with error: {e}")
        sys.exit(1)

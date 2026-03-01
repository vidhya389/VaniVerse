"""
Deploy VaniVerse to AWS staging environment

This script deploys the Lambda function, configures CloudWatch logging,
and sets up necessary AWS resources for staging.
"""

import boto3
import json
import os
import sys
import zipfile
import subprocess
from pathlib import Path
from datetime import datetime


class StagingDeployer:
    """Handles deployment to AWS staging environment"""
    
    def __init__(self, region='ap-south-1'):
        self.region = region
        self.lambda_client = boto3.client('lambda', region_name=region)
        self.s3_client = boto3.client('s3', region_name=region)
        self.iam_client = boto3.client('iam', region_name=region)
        self.logs_client = boto3.client('logs', region_name=region)
        self.cloudwatch_client = boto3.client('cloudwatch', region_name=region)
        
        # Configuration
        self.function_name = 'vaniverse-orchestrator-staging'
        self.deployment_bucket = 'vaniverse-deployments-staging'
        self.role_name = 'vaniverse-lambda-role-staging'
        
    def create_deployment_package(self):
        """Create Lambda deployment package"""
        print("Creating deployment package...")
        
        # Create temporary directory for package
        package_dir = Path('lambda_package')
        package_dir.mkdir(exist_ok=True)
        
        # Copy source code
        print("  Copying source code...")
        subprocess.run(['cp', '-r', 'src', str(package_dir)], check=True)
        
        # Install dependencies
        print("  Installing dependencies...")
        subprocess.run([
            'pip', 'install',
            '-r', 'requirements.txt',
            '-t', str(package_dir),
            '--upgrade'
        ], check=True)
        
        # Create zip file
        print("  Creating zip archive...")
        zip_path = 'lambda_deployment.zip'
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(package_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, package_dir)
                    zipf.write(file_path, arcname)
        
        # Cleanup
        subprocess.run(['rm', '-rf', str(package_dir)], check=True)
        
        print(f"  ✓ Deployment package created: {zip_path}")
        return zip_path
    
    def upload_to_s3(self, zip_path):
        """Upload deployment package to S3"""
        print(f"Uploading to S3 bucket: {self.deployment_bucket}...")
        
        # Create bucket if it doesn't exist
        try:
            self.s3_client.head_bucket(Bucket=self.deployment_bucket)
        except:
            print(f"  Creating bucket {self.deployment_bucket}...")
            self.s3_client.create_bucket(
                Bucket=self.deployment_bucket,
                CreateBucketConfiguration={'LocationConstraint': self.region}
            )
        
        # Upload zip file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        s3_key = f'deployments/vaniverse-{timestamp}.zip'
        
        self.s3_client.upload_file(zip_path, self.deployment_bucket, s3_key)
        
        print(f"  ✓ Uploaded to s3://{self.deployment_bucket}/{s3_key}")
        return s3_key
    
    def create_or_update_iam_role(self):
        """Create or update IAM role for Lambda"""
        print(f"Setting up IAM role: {self.role_name}...")
        
        # Trust policy for Lambda
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }]
        }
        
        try:
            # Try to create role
            response = self.iam_client.create_role(
                RoleName=self.role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Description='IAM role for VaniVerse Lambda function (staging)'
            )
            role_arn = response['Role']['Arn']
            print(f"  ✓ Created role: {role_arn}")
        except self.iam_client.exceptions.EntityAlreadyExistsException:
            # Role already exists
            response = self.iam_client.get_role(RoleName=self.role_name)
            role_arn = response['Role']['Arn']
            print(f"  ✓ Using existing role: {role_arn}")
        
        # Attach policies
        policies = [
            'arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole',
            'arn:aws:iam::aws:policy/AmazonS3FullAccess',
            'arn:aws:iam::aws:policy/AmazonTranscribeFullAccess',
            'arn:aws:iam::aws:policy/AmazonPollyFullAccess',
            'arn:aws:iam::aws:policy/AmazonBedrockFullAccess'
        ]
        
        for policy_arn in policies:
            try:
                self.iam_client.attach_role_policy(
                    RoleName=self.role_name,
                    PolicyArn=policy_arn
                )
                print(f"  ✓ Attached policy: {policy_arn.split('/')[-1]}")
            except:
                pass  # Already attached
        
        return role_arn
    
    def create_or_update_lambda_function(self, s3_key, role_arn):
        """Create or update Lambda function"""
        print(f"Deploying Lambda function: {self.function_name}...")
        
        # Environment variables
        environment = {
            'Variables': {
                'ENVIRONMENT': 'staging',
                'AWS_REGION': self.region,
                'AUDIO_INPUT_BUCKET': 'vaniverse-audio-input-staging',
                'AUDIO_OUTPUT_BUCKET': 'vaniverse-audio-output-staging',
                'USE_MOCK_UFSI': 'true',
                'LOG_LEVEL': 'DEBUG'
            }
        }
        
        # Lambda configuration
        config = {
            'FunctionName': self.function_name,
            'Runtime': 'python3.11',
            'Role': role_arn,
            'Handler': 'src.lambda_handler.lambda_handler',
            'Timeout': 300,  # 5 minutes
            'MemorySize': 1024,  # 1GB
            'Environment': environment,
            'Description': 'VaniVerse Orchestrator - Staging Environment'
        }
        
        try:
            # Try to create function
            response = self.lambda_client.create_function(
                **config,
                Code={
                    'S3Bucket': self.deployment_bucket,
                    'S3Key': s3_key
                }
            )
            print(f"  ✓ Created function: {response['FunctionArn']}")
        except self.lambda_client.exceptions.ResourceConflictException:
            # Function exists, update it
            response = self.lambda_client.update_function_code(
                FunctionName=self.function_name,
                S3Bucket=self.deployment_bucket,
                S3Key=s3_key
            )
            print(f"  ✓ Updated function code")
            
            # Update configuration
            self.lambda_client.update_function_configuration(**config)
            print(f"  ✓ Updated function configuration")
        
        return response['FunctionArn']
    
    def setup_cloudwatch_logging(self):
        """Configure CloudWatch logging and monitoring"""
        print("Setting up CloudWatch logging...")
        
        log_group_name = f'/aws/lambda/{self.function_name}'
        
        # Create log group if it doesn't exist
        try:
            self.logs_client.create_log_group(logGroupName=log_group_name)
            print(f"  ✓ Created log group: {log_group_name}")
        except self.logs_client.exceptions.ResourceAlreadyExistsException:
            print(f"  ✓ Using existing log group: {log_group_name}")
        
        # Set retention policy (30 days for staging)
        self.logs_client.put_retention_policy(
            logGroupName=log_group_name,
            retentionInDays=30
        )
        print(f"  ✓ Set log retention: 30 days")
        
        # Create CloudWatch alarms
        self.create_cloudwatch_alarms()
    
    def create_cloudwatch_alarms(self):
        """Create CloudWatch alarms for monitoring"""
        print("Creating CloudWatch alarms...")
        
        alarms = [
            {
                'AlarmName': f'{self.function_name}-errors',
                'MetricName': 'Errors',
                'Threshold': 5.0,
                'ComparisonOperator': 'GreaterThanThreshold',
                'EvaluationPeriods': 1,
                'Period': 300,
                'Statistic': 'Sum',
                'AlarmDescription': 'Alert when Lambda function has errors'
            },
            {
                'AlarmName': f'{self.function_name}-duration',
                'MetricName': 'Duration',
                'Threshold': 6000.0,  # 6 seconds in milliseconds
                'ComparisonOperator': 'GreaterThanThreshold',
                'EvaluationPeriods': 2,
                'Period': 60,
                'Statistic': 'Average',
                'AlarmDescription': 'Alert when Lambda duration exceeds 6 seconds'
            },
            {
                'AlarmName': f'{self.function_name}-throttles',
                'MetricName': 'Throttles',
                'Threshold': 1.0,
                'ComparisonOperator': 'GreaterThanThreshold',
                'EvaluationPeriods': 1,
                'Period': 300,
                'Statistic': 'Sum',
                'AlarmDescription': 'Alert when Lambda function is throttled'
            }
        ]
        
        for alarm in alarms:
            try:
                self.cloudwatch_client.put_metric_alarm(
                    **alarm,
                    Namespace='AWS/Lambda',
                    Dimensions=[
                        {'Name': 'FunctionName', 'Value': self.function_name}
                    ]
                )
                print(f"  ✓ Created alarm: {alarm['AlarmName']}")
            except Exception as e:
                print(f"  ⚠ Warning: Could not create alarm {alarm['AlarmName']}: {e}")
    
    def configure_s3_trigger(self):
        """Configure S3 trigger for Lambda function"""
        print("Configuring S3 trigger...")
        
        input_bucket = 'vaniverse-audio-input-staging'
        
        # Create input bucket if it doesn't exist
        try:
            self.s3_client.head_bucket(Bucket=input_bucket)
        except:
            print(f"  Creating bucket {input_bucket}...")
            self.s3_client.create_bucket(
                Bucket=input_bucket,
                CreateBucketConfiguration={'LocationConstraint': self.region}
            )
        
        # Add Lambda permission for S3
        try:
            self.lambda_client.add_permission(
                FunctionName=self.function_name,
                StatementId='s3-trigger-permission',
                Action='lambda:InvokeFunction',
                Principal='s3.amazonaws.com',
                SourceArn=f'arn:aws:s3:::{input_bucket}'
            )
            print(f"  ✓ Added S3 invoke permission")
        except self.lambda_client.exceptions.ResourceConflictException:
            print(f"  ✓ S3 invoke permission already exists")
        
        # Configure S3 notification
        notification_config = {
            'LambdaFunctionConfigurations': [{
                'LambdaFunctionArn': f'arn:aws:lambda:{self.region}:{boto3.client("sts").get_caller_identity()["Account"]}:function:{self.function_name}',
                'Events': ['s3:ObjectCreated:*'],
                'Filter': {
                    'Key': {
                        'FilterRules': [
                            {'Name': 'prefix', 'Value': 'audio-input/'},
                            {'Name': 'suffix', 'Value': '.wav'}
                        ]
                    }
                }
            }]
        }
        
        self.s3_client.put_bucket_notification_configuration(
            Bucket=input_bucket,
            NotificationConfiguration=notification_config
        )
        print(f"  ✓ Configured S3 trigger on {input_bucket}")
    
    def deploy(self):
        """Execute full deployment"""
        print("=" * 80)
        print("VaniVerse Staging Deployment")
        print("=" * 80)
        print(f"Region: {self.region}")
        print(f"Timestamp: {datetime.now().isoformat()}")
        print("=" * 80)
        print()
        
        try:
            # Step 1: Create deployment package
            zip_path = self.create_deployment_package()
            
            # Step 2: Upload to S3
            s3_key = self.upload_to_s3(zip_path)
            
            # Step 3: Create/update IAM role
            role_arn = self.create_or_update_iam_role()
            
            # Wait for role to propagate
            print("  Waiting for IAM role to propagate...")
            import time
            time.sleep(10)
            
            # Step 4: Create/update Lambda function
            function_arn = self.create_or_update_lambda_function(s3_key, role_arn)
            
            # Step 5: Setup CloudWatch logging
            self.setup_cloudwatch_logging()
            
            # Step 6: Configure S3 trigger
            self.configure_s3_trigger()
            
            # Cleanup
            os.remove(zip_path)
            
            print()
            print("=" * 80)
            print("✓ Deployment completed successfully!")
            print("=" * 80)
            print(f"Function ARN: {function_arn}")
            print(f"Log Group: /aws/lambda/{self.function_name}")
            print(f"Input Bucket: vaniverse-audio-input-staging")
            print("=" * 80)
            
            return True
            
        except Exception as e:
            print()
            print("=" * 80)
            print(f"✗ Deployment failed: {e}")
            print("=" * 80)
            import traceback
            traceback.print_exc()
            return False


def main():
    """Main deployment function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Deploy VaniVerse to AWS staging")
    parser.add_argument(
        '--region',
        default='ap-south-1',
        help='AWS region (default: ap-south-1 - Mumbai)'
    )
    
    args = parser.parse_args()
    
    # Check AWS credentials
    try:
        boto3.client('sts').get_caller_identity()
    except Exception as e:
        print(f"✗ AWS credentials not configured: {e}")
        sys.exit(1)
    
    # Deploy
    deployer = StagingDeployer(region=args.region)
    success = deployer.deploy()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Setup script for farmer registration system.

Creates DynamoDB table, deploys Lambda function, and sets up API Gateway.
"""

import boto3
import json
import zipfile
import os
import sys
from pathlib import Path

# Configuration
REGION = 'ap-south-1'
TABLE_NAME = 'vaniverse-farmers'
LAMBDA_FUNCTION_NAME = 'vaniverse-registration'
LAMBDA_ROLE_NAME = 'vaniverse-registration-role'
API_NAME = 'vaniverse-registration-api'


def create_dynamodb_table():
    """Create DynamoDB table for farmers."""
    print("Creating DynamoDB table...")
    
    dynamodb = boto3.client('dynamodb', region_name=REGION)
    
    try:
        response = dynamodb.create_table(
            TableName=TABLE_NAME,
            AttributeDefinitions=[
                {'AttributeName': 'farmer_id', 'AttributeType': 'S'},
                {'AttributeName': 'phone_number', 'AttributeType': 'S'},
            ],
            KeySchema=[
                {'AttributeName': 'farmer_id', 'KeyType': 'HASH'},
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'phone-index',
                    'KeySchema': [
                        {'AttributeName': 'phone_number', 'KeyType': 'HASH'},
                    ],
                    'Projection': {'ProjectionType': 'ALL'}
                }
            ],
            BillingMode='PAY_PER_REQUEST',
            Tags=[
                {'Key': 'Project', 'Value': 'VaniVerse'},
                {'Key': 'Component', 'Value': 'Registration'}
            ]
        )
        
        print(f"✓ DynamoDB table '{TABLE_NAME}' created successfully")
        print(f"  Waiting for table to be active...")
        
        waiter = dynamodb.get_waiter('table_exists')
        waiter.wait(TableName=TABLE_NAME)
        
        print(f"✓ Table is now active")
        
    except dynamodb.exceptions.ResourceInUseException:
        print(f"✓ DynamoDB table '{TABLE_NAME}' already exists")
    except Exception as e:
        print(f"✗ Error creating DynamoDB table: {e}")
        return False
    
    return True


def create_lambda_role():
    """Create IAM role for Lambda function."""
    print("\nCreating IAM role for Lambda...")
    
    iam = boto3.client('iam')
    
    # Trust policy
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }
        ]
    }
    
    # Permissions policy
    permissions_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "dynamodb:PutItem",
                    "dynamodb:GetItem",
                    "dynamodb:Query",
                    "dynamodb:UpdateItem"
                ],
                "Resource": [
                    f"arn:aws:dynamodb:{REGION}:*:table/{TABLE_NAME}",
                    f"arn:aws:dynamodb:{REGION}:*:table/{TABLE_NAME}/index/phone-index"
                ]
            },
            {
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                "Resource": "arn:aws:logs:*:*:*"
            }
        ]
    }
    
    try:
        # Create role
        role_response = iam.create_role(
            RoleName=LAMBDA_ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description='Role for VaniVerse registration Lambda function',
            Tags=[
                {'Key': 'Project', 'Value': 'VaniVerse'},
                {'Key': 'Component', 'Value': 'Registration'}
            ]
        )
        
        role_arn = role_response['Role']['Arn']
        print(f"✓ IAM role '{LAMBDA_ROLE_NAME}' created")
        
        # Attach inline policy
        iam.put_role_policy(
            RoleName=LAMBDA_ROLE_NAME,
            PolicyName='RegistrationLambdaPolicy',
            PolicyDocument=json.dumps(permissions_policy)
        )
        
        print(f"✓ Permissions policy attached")
        
        # Wait for role to be available
        import time
        print("  Waiting for role to propagate...")
        time.sleep(10)
        
        return role_arn
        
    except iam.exceptions.EntityAlreadyExistsException:
        print(f"✓ IAM role '{LAMBDA_ROLE_NAME}' already exists")
        role = iam.get_role(RoleName=LAMBDA_ROLE_NAME)
        return role['Role']['Arn']
    except Exception as e:
        print(f"✗ Error creating IAM role: {e}")
        return None


def create_lambda_package():
    """Create Lambda deployment package."""
    print("\nCreating Lambda deployment package...")
    
    package_path = Path('lambda_registration_package.zip')
    
    try:
        with zipfile.ZipFile(package_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add Lambda handler
            handler_path = Path('src/registration/lambda_handler.py')
            if handler_path.exists():
                zipf.write(handler_path, 'lambda_handler.py')
                print(f"✓ Added lambda_handler.py")
            else:
                print(f"✗ Handler not found: {handler_path}")
                return None
        
        print(f"✓ Lambda package created: {package_path}")
        return package_path
        
    except Exception as e:
        print(f"✗ Error creating Lambda package: {e}")
        return None


def deploy_lambda_function(role_arn, package_path):
    """Deploy Lambda function."""
    print("\nDeploying Lambda function...")
    
    lambda_client = boto3.client('lambda', region_name=REGION)
    
    try:
        with open(package_path, 'rb') as f:
            zip_content = f.read()
        
        try:
            # Try to create new function
            response = lambda_client.create_function(
                FunctionName=LAMBDA_FUNCTION_NAME,
                Runtime='python3.9',
                Role=role_arn,
                Handler='lambda_handler.lambda_handler',
                Code={'ZipFile': zip_content},
                Description='VaniVerse farmer registration handler',
                Timeout=10,
                MemorySize=256,
                Environment={
                    'Variables': {
                        'DYNAMODB_TABLE_NAME': TABLE_NAME,
                        'DYNAMODB_REGION': REGION
                    }
                },
                Tags={
                    'Project': 'VaniVerse',
                    'Component': 'Registration'
                }
            )
            print(f"✓ Lambda function '{LAMBDA_FUNCTION_NAME}' created")
            
        except lambda_client.exceptions.ResourceConflictException:
            # Update existing function
            response = lambda_client.update_function_code(
                FunctionName=LAMBDA_FUNCTION_NAME,
                ZipFile=zip_content
            )
            print(f"✓ Lambda function '{LAMBDA_FUNCTION_NAME}' updated")
        
        function_arn = response['FunctionArn']
        print(f"  Function ARN: {function_arn}")
        
        return function_arn
        
    except Exception as e:
        print(f"✗ Error deploying Lambda function: {e}")
        return None


def main():
    """Main setup function."""
    print("=" * 60)
    print("VaniVerse Registration System Setup")
    print("=" * 60)
    
    # Step 1: Create DynamoDB table
    if not create_dynamodb_table():
        print("\n✗ Setup failed at DynamoDB creation")
        return 1
    
    # Step 2: Create IAM role
    role_arn = create_lambda_role()
    if not role_arn:
        print("\n✗ Setup failed at IAM role creation")
        return 1
    
    # Step 3: Create Lambda package
    package_path = create_lambda_package()
    if not package_path:
        print("\n✗ Setup failed at Lambda package creation")
        return 1
    
    # Step 4: Deploy Lambda function
    function_arn = deploy_lambda_function(role_arn, package_path)
    if not function_arn:
        print("\n✗ Setup failed at Lambda deployment")
        return 1
    
    # Cleanup
    if package_path.exists():
        package_path.unlink()
        print(f"\n✓ Cleaned up temporary package")
    
    print("\n" + "=" * 60)
    print("✓ Setup completed successfully!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Create API Gateway REST API")
    print("2. Create /register resource and POST method")
    print("3. Integrate with Lambda function:")
    print(f"   {function_arn}")
    print("4. Enable CORS on API Gateway")
    print("5. Deploy API to stage (e.g., 'prod')")
    print("6. Update Flutter app with API endpoint URL")
    print("\nSee docs/FARMER_REGISTRATION_SETUP.md for detailed instructions")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

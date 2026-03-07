"""
Setup OTP Infrastructure

Creates DynamoDB table, Lambda functions, and API Gateway endpoints for OTP verification.
"""

import boto3
import json
import os
from botocore.exceptions import ClientError

# AWS clients
dynamodb = boto3.client('dynamodb')
lambda_client = boto3.client('lambda')
apigateway = boto3.client('apigateway')
iam = boto3.client('iam')

# Configuration
REGION = os.getenv('AWS_REGION', 'ap-south-1')
OTP_TABLE_NAME = 'OTPVerification'
SEND_OTP_FUNCTION_NAME = 'vaniverse-send-otp'
VERIFY_OTP_FUNCTION_NAME = 'vaniverse-verify-otp'


def create_otp_table():
    """Create DynamoDB table for OTP storage"""
    print(f"Creating DynamoDB table: {OTP_TABLE_NAME}")
    
    try:
        response = dynamodb.create_table(
            TableName=OTP_TABLE_NAME,
            KeySchema=[
                {
                    'AttributeName': 'phone_number',
                    'KeyType': 'HASH'  # Partition key
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'phone_number',
                    'AttributeType': 'S'
                }
            ],
            BillingMode='PAY_PER_REQUEST'  # On-demand pricing
        )
        
        table_arn = response['TableDescription']['TableArn']
        print(f"✅ Table created: {OTP_TABLE_NAME}")
        print(f"   ARN: {table_arn}")
        
        # Wait for table to be active
        print("   Waiting for table to be active...")
        waiter = dynamodb.get_waiter('table_exists')
        waiter.wait(TableName=OTP_TABLE_NAME)
        
        # Enable TTL
        print("   Enabling TTL on expiry_time attribute...")
        dynamodb.update_time_to_live(
            TableName=OTP_TABLE_NAME,
            TimeToLiveSpecification={
                'Enabled': True,
                'AttributeName': 'expiry_time'
            }
        )
        print("✅ TTL enabled successfully")
        
        return table_arn
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceInUseException':
            print(f"⚠️  Table {OTP_TABLE_NAME} already exists")
            # Get table ARN
            response = dynamodb.describe_table(TableName=OTP_TABLE_NAME)
            table_arn = response['Table']['TableArn']
            
            # Check and enable TTL if not already enabled
            try:
                ttl_response = dynamodb.describe_time_to_live(TableName=OTP_TABLE_NAME)
                ttl_status = ttl_response['TimeToLiveDescription']['TimeToLiveStatus']
                
                if ttl_status != 'ENABLED':
                    print("   Enabling TTL...")
                    dynamodb.update_time_to_live(
                        TableName=OTP_TABLE_NAME,
                        TimeToLiveSpecification={
                            'Enabled': True,
                            'AttributeName': 'expiry_time'
                        }
                    )
                    print("✅ TTL enabled successfully")
                else:
                    print("✅ TTL already enabled")
            except ClientError as ttl_error:
                print(f"⚠️  Could not configure TTL: {ttl_error}")
            
            return table_arn
        else:
            print(f"❌ Error creating table: {e}")
            raise


def create_lambda_execution_role():
    """Create IAM role for Lambda functions"""
    print("Creating Lambda execution role...")
    
    role_name = 'VaniVerseOTPLambdaRole'
    
    # Trust policy
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
        response = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description='Execution role for VaniVerse OTP Lambda functions'
        )
        role_arn = response['Role']['Arn']
        print(f"✅ Role created: {role_arn}")
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'EntityAlreadyExists':
            print(f"⚠️  Role {role_name} already exists")
            response = iam.get_role(RoleName=role_name)
            role_arn = response['Role']['Arn']
        else:
            print(f"❌ Error creating role: {e}")
            raise
    
    # Attach policies
    policies = [
        'arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole',
        'arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess',
        'arn:aws:iam::aws:policy/AmazonSNSFullAccess'
    ]
    
    for policy_arn in policies:
        try:
            iam.attach_role_policy(
                RoleName=role_name,
                PolicyArn=policy_arn
            )
            print(f"✅ Attached policy: {policy_arn}")
        except ClientError as e:
            print(f"⚠️  Policy already attached or error: {e}")
    
    return role_arn


def print_next_steps():
    """Print next steps for manual setup"""
    print("\n" + "="*60)
    print("OTP INFRASTRUCTURE SETUP COMPLETE")
    print("="*60)
    
    print("\n📋 NEXT STEPS:")
    print("\n1. Configure AWS SNS for SMS:")
    print("   - Go to AWS SNS Console")
    print("   - Navigate to Text messaging (SMS)")
    print("   - Set up SMS sandbox (for testing)")
    print("   - Or request production access")
    print("   - Add verified phone numbers for testing")
    
    print("\n2. Deploy Lambda Functions:")
    print(f"   - Package and deploy: {SEND_OTP_FUNCTION_NAME}")
    print(f"   - Package and deploy: {VERIFY_OTP_FUNCTION_NAME}")
    print("   - Set environment variables:")
    print(f"     * OTP_TABLE_NAME={OTP_TABLE_NAME}")
    print("     * MOCK_OTP=true (for development)")
    print("     * OTP_EXPIRY_MINUTES=10")
    print("     * OTP_MAX_ATTEMPTS=3")
    
    print("\n3. Create API Gateway Endpoints:")
    print("   - POST /send-otp → Send OTP Lambda")
    print("   - POST /verify-otp → Verify OTP Lambda")
    print("   - Enable CORS")
    print("   - Deploy to 'prod' stage")
    
    print("\n4. Update Mobile App:")
    print("   - Add OTP verification screen")
    print("   - Update registration service")
    print("   - Add API endpoints to config")
    
    print("\n5. Testing:")
    print("   - Test with MOCK_OTP=true first")
    print("   - Then test with real SMS")
    print("   - Verify rate limiting")
    print("   - Test expiry handling")
    
    print("\n" + "="*60)


def main():
    """Main setup function"""
    print("🚀 Setting up OTP Infrastructure for VaniVerse")
    print("="*60)
    
    try:
        # Step 1: Create DynamoDB table
        table_arn = create_otp_table()
        
        # Step 2: Create IAM role
        role_arn = create_lambda_execution_role()
        
        # Step 3: Print next steps
        print_next_steps()
        
        print("\n✅ Setup completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        raise


if __name__ == '__main__':
    main()

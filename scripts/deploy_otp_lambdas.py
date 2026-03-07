"""
Deploy OTP Lambda Functions

Packages and deploys Send OTP and Verify OTP Lambda functions.
"""

import boto3
import zipfile
import os
import time
from pathlib import Path
from botocore.exceptions import ClientError

# AWS clients
lambda_client = boto3.client('lambda')
iam = boto3.client('iam')

# Configuration
REGION = os.getenv('AWS_REGION', 'ap-south-1')
ROLE_NAME = 'VaniVerseOTPLambdaRole'
OTP_TABLE_NAME = 'OTPVerification'

# Lambda functions configuration
LAMBDA_FUNCTIONS = [
    {
        'name': 'vaniverse-send-otp',
        'handler': 'send_otp_handler.lambda_handler',
        'files': ['src/otp/send_otp_handler.py', 'src/otp/otp_service.py'],
        'zip_name': 'send_otp.zip'
    },
    {
        'name': 'vaniverse-verify-otp',
        'handler': 'verify_otp_handler.lambda_handler',
        'files': ['src/otp/verify_otp_handler.py', 'src/otp/otp_service.py'],
        'zip_name': 'verify_otp.zip'
    }
]


def get_role_arn():
    """Get IAM role ARN"""
    try:
        response = iam.get_role(RoleName=ROLE_NAME)
        return response['Role']['Arn']
    except ClientError as e:
        print(f"❌ Error getting role: {e}")
        print(f"   Make sure to run setup_otp_infrastructure.py first")
        raise


def create_deployment_package(files, zip_name):
    """Create deployment package for Lambda"""
    print(f"   Creating deployment package: {zip_name}")
    
    # Create zip file
    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in files:
            if os.path.exists(file_path):
                # Add file with correct path structure
                arcname = os.path.basename(file_path)
                zipf.write(file_path, arcname)
                print(f"     Added: {file_path} as {arcname}")
            else:
                print(f"     ⚠️  File not found: {file_path}")
    
    print(f"   ✅ Package created: {zip_name}")
    return zip_name


def deploy_lambda(config, role_arn):
    """Deploy or update Lambda function"""
    function_name = config['name']
    print(f"\n📦 Deploying Lambda: {function_name}")
    
    # Create deployment package
    zip_file = create_deployment_package(config['files'], config['zip_name'])
    
    # Read zip file
    with open(zip_file, 'rb') as f:
        zip_content = f.read()
    
    # Environment variables
    environment = {
        'Variables': {
            'OTP_TABLE_NAME': OTP_TABLE_NAME,
            'MOCK_OTP': 'true',  # Set to false for production
            'OTP_EXPIRY_MINUTES': '10',
            'OTP_MAX_ATTEMPTS': '3',
            'OTP_MAX_PER_HOUR': '3'
        }
    }
    
    try:
        # Try to get existing function
        lambda_client.get_function(FunctionName=function_name)
        
        # Function exists - update it
        print(f"   Updating existing function...")
        response = lambda_client.update_function_code(
            FunctionName=function_name,
            ZipFile=zip_content
        )
        
        # Wait for update to complete
        print(f"   Waiting for update to complete...")
        time.sleep(2)
        
        # Update configuration
        lambda_client.update_function_configuration(
            FunctionName=function_name,
            Runtime='python3.9',
            Handler=config['handler'],
            Role=role_arn,
            Timeout=30,
            MemorySize=256,
            Environment=environment
        )
        
        print(f"   ✅ Function updated: {function_name}")
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            # Function doesn't exist - create it
            print(f"   Creating new function...")
            response = lambda_client.create_function(
                FunctionName=function_name,
                Runtime='python3.9',
                Role=role_arn,
                Handler=config['handler'],
                Code={'ZipFile': zip_content},
                Timeout=30,
                MemorySize=256,
                Environment=environment,
                Description=f'VaniVerse OTP verification - {function_name}'
            )
            print(f"   ✅ Function created: {function_name}")
        else:
            print(f"   ❌ Error deploying function: {e}")
            raise
    
    # Clean up zip file
    os.remove(zip_file)
    print(f"   Cleaned up: {zip_file}")
    
    return response['FunctionArn']


def print_next_steps(function_arns):
    """Print next steps"""
    print("\n" + "="*60)
    print("LAMBDA FUNCTIONS DEPLOYED")
    print("="*60)
    
    print("\n✅ Deployed Functions:")
    for name, arn in function_arns.items():
        print(f"   - {name}")
        print(f"     ARN: {arn}")
    
    print("\n📋 NEXT STEPS:")
    
    print("\n1. Configure AWS SNS:")
    print("   - Go to AWS SNS Console")
    print("   - Set up SMS sandbox for testing")
    print("   - Add verified phone numbers")
    
    print("\n2. Create API Gateway Endpoints:")
    print("   - Go to API Gateway Console")
    print("   - Create or select your API")
    print("   - Create resources:")
    print("     * POST /send-otp → vaniverse-send-otp")
    print("     * POST /verify-otp → vaniverse-verify-otp")
    print("   - Enable CORS on both endpoints")
    print("   - Deploy to 'prod' stage")
    
    print("\n3. Test Lambda Functions:")
    print("   - Test with mock OTP (123456)")
    print("   - Check CloudWatch logs")
    print("   - Verify DynamoDB records")
    
    print("\n4. Update Mobile App:")
    print("   - Update API endpoints in otp_service.dart")
    print("   - Test OTP flow end-to-end")
    
    print("\n5. Production Setup:")
    print("   - Set MOCK_OTP=false in Lambda environment")
    print("   - Request SNS production access")
    print("   - Test with real SMS")
    
    print("\n" + "="*60)


def main():
    """Main deployment function"""
    print("🚀 Deploying OTP Lambda Functions")
    print("="*60)
    
    try:
        # Get IAM role ARN
        role_arn = get_role_arn()
        print(f"✅ Using IAM role: {role_arn}")
        
        # Deploy each Lambda function
        function_arns = {}
        for config in LAMBDA_FUNCTIONS:
            arn = deploy_lambda(config, role_arn)
            function_arns[config['name']] = arn
        
        # Print next steps
        print_next_steps(function_arns)
        
        print("\n✅ Deployment completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Deployment failed: {e}")
        raise


if __name__ == '__main__':
    main()

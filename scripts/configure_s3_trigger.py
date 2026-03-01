"""
Configure S3 Event Trigger for VaniVerse Lambda Function

This script sets up S3 bucket notifications to trigger the Lambda orchestrator
when audio files are uploaded.

Implements Requirement 11.1: S3 event triggers Lambda orchestrator
"""

import boto3
import json
import sys
from botocore.exceptions import ClientError

# Add parent directory to path for imports
sys.path.insert(0, '..')
from src.config import Config


def get_lambda_arn():
    """Get the ARN of the deployed Lambda function"""
    lambda_client = boto3.client('lambda', region_name=Config.AWS_REGION)
    
    try:
        response = lambda_client.get_function(
            FunctionName=Config.LAMBDA_FUNCTION_NAME
        )
        return response['Configuration']['FunctionArn']
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            print(f"✗ Lambda function '{Config.LAMBDA_FUNCTION_NAME}' not found")
            print("  Please deploy the Lambda function first")
            return None
        else:
            print(f"✗ Error getting Lambda function: {e}")
            return None


def add_lambda_permission(lambda_arn: str):
    """
    Add permission for S3 to invoke the Lambda function
    
    Args:
        lambda_arn: ARN of the Lambda function
        
    Returns:
        True if successful, False otherwise
    """
    lambda_client = boto3.client('lambda', region_name=Config.AWS_REGION)
    
    try:
        # Check if permission already exists
        try:
            response = lambda_client.get_policy(
                FunctionName=Config.LAMBDA_FUNCTION_NAME
            )
            policy = json.loads(response['Policy'])
            
            # Check if S3 permission already exists
            for statement in policy.get('Statement', []):
                if (statement.get('Sid') == 's3-trigger-permission' and
                    statement.get('Principal', {}).get('Service') == 's3.amazonaws.com'):
                    print(f"✓ Lambda permission for S3 already exists")
                    return True
        except ClientError:
            pass  # Permission doesn't exist, will create it
        
        # Add permission
        lambda_client.add_permission(
            FunctionName=Config.LAMBDA_FUNCTION_NAME,
            StatementId='s3-trigger-permission',
            Action='lambda:InvokeFunction',
            Principal='s3.amazonaws.com',
            SourceArn=f'arn:aws:s3:::{Config.AUDIO_INPUT_BUCKET}'
        )
        print(f"✓ Added Lambda permission for S3 to invoke function")
        return True
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceConflictException':
            print(f"✓ Lambda permission for S3 already exists")
            return True
        else:
            print(f"✗ Error adding Lambda permission: {e}")
            return False


def configure_s3_notification(lambda_arn: str):
    """
    Configure S3 bucket notification to trigger Lambda on audio uploads
    
    Args:
        lambda_arn: ARN of the Lambda function
        
    Returns:
        True if successful, False otherwise
        
    Validates:
        Requirement 11.1: S3 event triggers Lambda orchestrator
    """
    s3_client = boto3.client('s3', region_name=Config.AWS_REGION)
    
    try:
        # Check if bucket exists
        try:
            s3_client.head_bucket(Bucket=Config.AUDIO_INPUT_BUCKET)
        except ClientError as e:
            print(f"✗ Bucket '{Config.AUDIO_INPUT_BUCKET}' not found")
            print("  Please run setup_infrastructure.py first")
            return False
        
        # Get existing notification configuration
        try:
            existing_config = s3_client.get_bucket_notification_configuration(
                Bucket=Config.AUDIO_INPUT_BUCKET
            )
            # Remove ResponseMetadata
            existing_config.pop('ResponseMetadata', None)
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchConfiguration':
                existing_config = {}
            else:
                raise
        
        # Create notification configuration for audio file uploads
        # Filter for .wav, .mp3, .m4a, and .webm files
        notification_config = {
            'LambdaFunctionConfigurations': [
                {
                    'Id': 'vaniverse-audio-upload-trigger',
                    'LambdaFunctionArn': lambda_arn,
                    'Events': ['s3:ObjectCreated:*'],
                    'Filter': {
                        'Key': {
                            'FilterRules': [
                                {
                                    'Name': 'suffix',
                                    'Value': '.wav'
                                }
                            ]
                        }
                    }
                },
                {
                    'Id': 'vaniverse-audio-upload-trigger-mp3',
                    'LambdaFunctionArn': lambda_arn,
                    'Events': ['s3:ObjectCreated:*'],
                    'Filter': {
                        'Key': {
                            'FilterRules': [
                                {
                                    'Name': 'suffix',
                                    'Value': '.mp3'
                                }
                            ]
                        }
                    }
                },
                {
                    'Id': 'vaniverse-audio-upload-trigger-m4a',
                    'LambdaFunctionArn': lambda_arn,
                    'Events': ['s3:ObjectCreated:*'],
                    'Filter': {
                        'Key': {
                            'FilterRules': [
                                {
                                    'Name': 'suffix',
                                    'Value': '.m4a'
                                }
                            ]
                        }
                    }
                },
                {
                    'Id': 'vaniverse-audio-upload-trigger-webm',
                    'LambdaFunctionArn': lambda_arn,
                    'Events': ['s3:ObjectCreated:*'],
                    'Filter': {
                        'Key': {
                            'FilterRules': [
                                {
                                    'Name': 'suffix',
                                    'Value': '.webm'
                                }
                            ]
                        }
                    }
                }
            ]
        }
        
        # Merge with existing configuration if needed
        if 'TopicConfigurations' in existing_config:
            notification_config['TopicConfigurations'] = existing_config['TopicConfigurations']
        if 'QueueConfigurations' in existing_config:
            notification_config['QueueConfigurations'] = existing_config['QueueConfigurations']
        
        # Apply notification configuration
        s3_client.put_bucket_notification_configuration(
            Bucket=Config.AUDIO_INPUT_BUCKET,
            NotificationConfiguration=notification_config
        )
        
        print(f"✓ Configured S3 bucket notification for audio uploads")
        print(f"  - Bucket: {Config.AUDIO_INPUT_BUCKET}")
        print(f"  - Triggers on: .wav, .mp3, .m4a, .webm files")
        print(f"  - Lambda: {lambda_arn}")
        
        return True
        
    except ClientError as e:
        print(f"✗ Error configuring S3 notification: {e}")
        return False


def verify_configuration():
    """
    Verify that the S3 event trigger is configured correctly
    
    Returns:
        True if configuration is valid, False otherwise
    """
    s3_client = boto3.client('s3', region_name=Config.AWS_REGION)
    
    try:
        # Get notification configuration
        config = s3_client.get_bucket_notification_configuration(
            Bucket=Config.AUDIO_INPUT_BUCKET
        )
        
        # Check for Lambda configurations
        lambda_configs = config.get('LambdaFunctionConfigurations', [])
        
        if not lambda_configs:
            print("✗ No Lambda function configurations found")
            return False
        
        # Verify our configurations exist
        found_wav = False
        found_mp3 = False
        found_m4a = False
        found_webm = False
        
        for lc in lambda_configs:
            if lc.get('Id') == 'vaniverse-audio-upload-trigger':
                found_wav = True
            elif lc.get('Id') == 'vaniverse-audio-upload-trigger-mp3':
                found_mp3 = True
            elif lc.get('Id') == 'vaniverse-audio-upload-trigger-m4a':
                found_m4a = True
            elif lc.get('Id') == 'vaniverse-audio-upload-trigger-webm':
                found_webm = True
        
        if found_wav and found_mp3 and found_m4a and found_webm:
            print("✓ S3 event trigger configuration verified")
            print(f"  - Configured for .wav, .mp3, .m4a, and .webm files")
            return True
        else:
            print("⚠ Partial configuration found")
            print(f"  - .wav: {'✓' if found_wav else '✗'}")
            print(f"  - .mp3: {'✓' if found_mp3 else '✗'}")
            print(f"  - .m4a: {'✓' if found_m4a else '✗'}")
            print(f"  - .webm: {'✓' if found_webm else '✗'}")
            return False
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchConfiguration':
            print("✗ No S3 notification configuration found")
        else:
            print(f"✗ Error verifying configuration: {e}")
        return False


def main():
    """Main configuration function"""
    print("=" * 70)
    print("VaniVerse S3 Event Trigger Configuration")
    print("=" * 70)
    print()
    
    print(f"Region: {Config.AWS_REGION}")
    print(f"Input Bucket: {Config.AUDIO_INPUT_BUCKET}")
    print(f"Lambda Function: {Config.LAMBDA_FUNCTION_NAME}")
    print()
    
    # Step 1: Get Lambda ARN
    print("Step 1: Getting Lambda Function ARN")
    print("-" * 70)
    lambda_arn = get_lambda_arn()
    if not lambda_arn:
        print("\n✗ Failed to get Lambda ARN")
        print("\nPlease ensure:")
        print("1. Lambda function is deployed")
        print("2. Function name in .env matches deployed function")
        return False
    print(f"Lambda ARN: {lambda_arn}")
    print()
    
    # Step 2: Add Lambda permission
    print("Step 2: Adding Lambda Permission for S3")
    print("-" * 70)
    if not add_lambda_permission(lambda_arn):
        print("\n✗ Failed to add Lambda permission")
        return False
    print()
    
    # Step 3: Configure S3 notification
    print("Step 3: Configuring S3 Bucket Notification")
    print("-" * 70)
    if not configure_s3_notification(lambda_arn):
        print("\n✗ Failed to configure S3 notification")
        return False
    print()
    
    # Step 4: Verify configuration
    print("Step 4: Verifying Configuration")
    print("-" * 70)
    if not verify_configuration():
        print("\n⚠ Configuration verification failed")
        print("  The trigger may still work, but please check manually")
    print()
    
    print("=" * 70)
    print("✓ S3 Event Trigger Configuration Complete!")
    print("=" * 70)
    print()
    print("Next steps:")
    print("1. Test the trigger by uploading an audio file:")
    print(f"   aws s3 cp test_audio.wav s3://{Config.AUDIO_INPUT_BUCKET}/test/")
    print("2. Monitor Lambda logs:")
    print(f"   aws logs tail /aws/lambda/{Config.LAMBDA_FUNCTION_NAME} --follow")
    print()
    
    return True


if __name__ == '__main__':
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Configuration failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

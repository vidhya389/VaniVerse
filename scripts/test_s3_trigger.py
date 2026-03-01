"""
Test S3 Event Trigger for VaniVerse

This script tests the S3 event trigger by uploading a test audio file
and monitoring Lambda invocation.

Validates Requirement 11.1: S3 event triggers Lambda orchestrator
"""

import boto3
import json
import time
import sys
import os
from datetime import datetime, timedelta
from botocore.exceptions import ClientError

# Add parent directory to path for imports
sys.path.insert(0, '..')
from src.config import Config


def create_test_audio_file():
    """
    Create a minimal test audio file for upload
    
    Returns:
        Path to the test audio file
    """
    import wave
    import struct
    
    # Create a simple 1-second audio file
    filename = 'test_audio.wav'
    sample_rate = 16000
    duration = 1  # seconds
    frequency = 440  # Hz (A4 note)
    
    with wave.open(filename, 'w') as wav_file:
        # Set parameters: 1 channel, 2 bytes per sample, sample rate
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        
        # Generate sine wave
        for i in range(sample_rate * duration):
            value = int(32767 * 0.3 * (i % (sample_rate // frequency)) / (sample_rate // frequency))
            data = struct.pack('<h', value)
            wav_file.writeframes(data)
    
    print(f"✓ Created test audio file: {filename}")
    return filename


def upload_test_audio(test_file: str):
    """
    Upload test audio file to S3 input bucket
    
    Args:
        test_file: Path to test audio file
        
    Returns:
        S3 key of uploaded file
    """
    s3_client = boto3.client('s3', region_name=Config.AWS_REGION)
    
    # Create a unique key with farmer metadata
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    farmer_id = 'TEST_FARMER_001'
    session_id = f'test_session_{timestamp}'
    s3_key = f'{farmer_id}/{session_id}/{timestamp}.wav'
    
    try:
        # Upload with metadata
        with open(test_file, 'rb') as f:
            s3_client.put_object(
                Bucket=Config.AUDIO_INPUT_BUCKET,
                Key=s3_key,
                Body=f,
                Metadata={
                    'farmer_id': farmer_id,
                    'session_id': session_id,
                    'latitude': '28.6139',
                    'longitude': '77.2090',
                    'language': 'hi-IN',
                    'timestamp': timestamp
                }
            )
        
        print(f"✓ Uploaded test audio to S3")
        print(f"  Bucket: {Config.AUDIO_INPUT_BUCKET}")
        print(f"  Key: {s3_key}")
        
        return s3_key
        
    except ClientError as e:
        print(f"✗ Error uploading test audio: {e}")
        return None


def wait_for_lambda_invocation(timeout_seconds: int = 30):
    """
    Wait for Lambda function to be invoked and check logs
    
    Args:
        timeout_seconds: Maximum time to wait for invocation
        
    Returns:
        True if Lambda was invoked successfully, False otherwise
    """
    logs_client = boto3.client('logs', region_name=Config.AWS_REGION)
    log_group = f'/aws/lambda/{Config.LAMBDA_FUNCTION_NAME}'
    
    print(f"\nWaiting for Lambda invocation (timeout: {timeout_seconds}s)...")
    
    start_time = time.time()
    last_check_time = datetime.now() - timedelta(seconds=10)
    
    while time.time() - start_time < timeout_seconds:
        try:
            # Get recent log streams
            response = logs_client.describe_log_streams(
                logGroupName=log_group,
                orderBy='LastEventTime',
                descending=True,
                limit=5
            )
            
            # Check each log stream for recent events
            for stream in response.get('logStreams', []):
                stream_name = stream['logStreamName']
                last_event_time = datetime.fromtimestamp(
                    stream.get('lastEventTimestamp', 0) / 1000
                )
                
                # Only check streams with events after our upload
                if last_event_time > last_check_time:
                    # Get log events
                    events_response = logs_client.get_log_events(
                        logGroupName=log_group,
                        logStreamName=stream_name,
                        startTime=int(last_check_time.timestamp() * 1000),
                        limit=100
                    )
                    
                    # Check for our test invocation
                    for event in events_response.get('events', []):
                        message = event.get('message', '')
                        
                        # Look for S3 event processing
                        if 'TEST_FARMER_001' in message or 'test_session_' in message:
                            print(f"\n✓ Lambda invocation detected!")
                            print(f"  Log stream: {stream_name}")
                            print(f"  Timestamp: {last_event_time}")
                            print(f"\nRecent log messages:")
                            print("-" * 70)
                            
                            # Print recent log messages
                            for evt in events_response.get('events', [])[-10:]:
                                log_time = datetime.fromtimestamp(evt['timestamp'] / 1000)
                                print(f"[{log_time.strftime('%H:%M:%S')}] {evt['message']}")
                            
                            return True
            
            # Wait before next check
            time.sleep(2)
            print(".", end="", flush=True)
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                print(f"\n⚠ Log group not found: {log_group}")
                print("  Lambda may not have been invoked yet")
            else:
                print(f"\n✗ Error checking logs: {e}")
            time.sleep(2)
    
    print(f"\n✗ Timeout: Lambda was not invoked within {timeout_seconds} seconds")
    return False


def check_lambda_metrics():
    """
    Check CloudWatch metrics for Lambda invocations
    
    Returns:
        Dictionary with metric data
    """
    cloudwatch = boto3.client('cloudwatch', region_name=Config.AWS_REGION)
    
    try:
        # Get invocation count for last 5 minutes
        end_time = datetime.now()
        start_time = end_time - timedelta(minutes=5)
        
        response = cloudwatch.get_metric_statistics(
            Namespace='AWS/Lambda',
            MetricName='Invocations',
            Dimensions=[
                {
                    'Name': 'FunctionName',
                    'Value': Config.LAMBDA_FUNCTION_NAME
                }
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=60,
            Statistics=['Sum']
        )
        
        datapoints = response.get('Datapoints', [])
        
        if datapoints:
            total_invocations = sum(dp['Sum'] for dp in datapoints)
            print(f"\n✓ Lambda Metrics (last 5 minutes):")
            print(f"  Total invocations: {int(total_invocations)}")
            return {'invocations': total_invocations}
        else:
            print(f"\n⚠ No Lambda invocations in the last 5 minutes")
            return {'invocations': 0}
        
    except ClientError as e:
        print(f"\n✗ Error checking metrics: {e}")
        return None


def cleanup_test_file(test_file: str, s3_key: str = None):
    """
    Clean up test files
    
    Args:
        test_file: Local test file path
        s3_key: S3 key to delete (optional)
    """
    # Delete local file
    if os.path.exists(test_file):
        os.remove(test_file)
        print(f"\n✓ Cleaned up local test file")
    
    # Optionally delete S3 object
    if s3_key:
        try:
            s3_client = boto3.client('s3', region_name=Config.AWS_REGION)
            s3_client.delete_object(
                Bucket=Config.AUDIO_INPUT_BUCKET,
                Key=s3_key
            )
            print(f"✓ Cleaned up S3 test file")
        except ClientError as e:
            print(f"⚠ Could not delete S3 test file: {e}")


def main():
    """Main test function"""
    print("=" * 70)
    print("VaniVerse S3 Event Trigger Test")
    print("=" * 70)
    print()
    
    print(f"Region: {Config.AWS_REGION}")
    print(f"Input Bucket: {Config.AUDIO_INPUT_BUCKET}")
    print(f"Lambda Function: {Config.LAMBDA_FUNCTION_NAME}")
    print()
    
    test_file = None
    s3_key = None
    
    try:
        # Step 1: Create test audio file
        print("Step 1: Creating Test Audio File")
        print("-" * 70)
        test_file = create_test_audio_file()
        print()
        
        # Step 2: Upload to S3
        print("Step 2: Uploading Test Audio to S3")
        print("-" * 70)
        s3_key = upload_test_audio(test_file)
        if not s3_key:
            print("\n✗ Test failed: Could not upload test audio")
            return False
        print()
        
        # Step 3: Wait for Lambda invocation
        print("Step 3: Monitoring Lambda Invocation")
        print("-" * 70)
        invoked = wait_for_lambda_invocation(timeout_seconds=30)
        print()
        
        # Step 4: Check metrics
        print("Step 4: Checking CloudWatch Metrics")
        print("-" * 70)
        check_lambda_metrics()
        print()
        
        # Summary
        print("=" * 70)
        if invoked:
            print("✓ S3 Event Trigger Test PASSED!")
            print("=" * 70)
            print()
            print("The S3 event trigger is working correctly:")
            print("- Audio file uploaded successfully")
            print("- Lambda function was invoked")
            print("- Event processing started")
            print()
            return True
        else:
            print("✗ S3 Event Trigger Test FAILED")
            print("=" * 70)
            print()
            print("Possible issues:")
            print("1. S3 event notification not configured correctly")
            print("2. Lambda permission not granted to S3")
            print("3. Lambda function has errors")
            print()
            print("Troubleshooting steps:")
            print("1. Run: python scripts/configure_s3_trigger.py")
            print("2. Check Lambda logs manually:")
            print(f"   aws logs tail /aws/lambda/{Config.LAMBDA_FUNCTION_NAME} --follow")
            print("3. Verify S3 notification configuration:")
            print(f"   aws s3api get-bucket-notification-configuration --bucket {Config.AUDIO_INPUT_BUCKET}")
            print()
            return False
        
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Cleanup
        if test_file or s3_key:
            print("\nCleaning up test files...")
            print("-" * 70)
            cleanup_test_file(test_file, s3_key)


if __name__ == '__main__':
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n✗ Test interrupted by user")
        sys.exit(1)

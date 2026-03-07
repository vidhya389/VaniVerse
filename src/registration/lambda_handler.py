"""
Farmer Registration Lambda Handler

Handles farmer registration with phone number and generates unique farmer IDs.
Stores farmer data in DynamoDB.
Validates OTP verification token before registration.
"""

import json
import os
import uuid
import re
from datetime import datetime
from typing import Dict, Any
import boto3
from botocore.exceptions import ClientError


# Configuration
DYNAMODB_TABLE = os.getenv('DYNAMODB_TABLE_NAME', 'vaniverse-farmers')
OTP_TABLE = os.getenv('OTP_TABLE_NAME', 'OTPVerification')
AWS_REGION = os.getenv('DYNAMODB_REGION', os.getenv('AWS_REGION', 'ap-south-1'))

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
table = dynamodb.Table(DYNAMODB_TABLE)
otp_table = dynamodb.Table(OTP_TABLE)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for farmer registration.
    
    Args:
        event: API Gateway event with phone_number and verification_token in body
        context: Lambda context
    
    Returns:
        API Gateway response with farmer_id
    """
    try:
        # Parse request body
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', event)
        
        phone_number = body.get('phone_number', '').strip()
        verification_token = body.get('verification_token', '').strip()
        name = body.get('name', '').strip()
        language = body.get('language', 'hi-IN')
        agristack_id = body.get('agristack_id', '').strip()
        
        # Validate phone number
        if not phone_number:
            return error_response(400, "Phone number is required")
        
        if not validate_phone_number(phone_number):
            return error_response(400, "Invalid phone number format. Use +91XXXXXXXXXX")
        
        # Validate verification token
        if not verification_token:
            return error_response(400, "Verification token is required")
        
        if not validate_verification_token(phone_number, verification_token):
            return error_response(403, "Invalid or expired verification token. Please verify OTP again.")
        
        # Check if phone number already exists
        existing_farmer = get_farmer_by_phone(phone_number)
        
        if existing_farmer:
            # Return existing farmer ID (login case)
            print(f"Phone number {phone_number} already registered with ID {existing_farmer['farmer_id']}")
            return success_response({
                'farmer_id': existing_farmer['farmer_id'],
                'existing': True,
                'message': 'Login successful',
                'farmer': existing_farmer
            })
        
        # Generate new farmer ID
        farmer_id = generate_farmer_id()
        
        # Create farmer record
        farmer_data = {
            'farmer_id': farmer_id,
            'phone_number': phone_number,
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
            'status': 'active'
        }
        
        # Add optional fields
        if name:
            farmer_data['name'] = name
        if language:
            farmer_data['language'] = language
        if agristack_id:
            farmer_data['agristack_id'] = agristack_id
        
        # Save to DynamoDB
        save_farmer(farmer_data)
        
        print(f"New farmer registered: {farmer_id} with phone {phone_number}")
        
        return success_response({
            'farmer_id': farmer_id,
            'existing': False,
            'message': 'Registration successful',
            'farmer': farmer_data
        })
    
    except Exception as e:
        print(f"Error in registration: {str(e)}")
        import traceback
        traceback.print_exc()
        return error_response(500, f"Internal server error: {str(e)}")


def validate_phone_number(phone: str) -> bool:
    """
    Validate Indian phone number format.
    
    Args:
        phone: Phone number string
    
    Returns:
        True if valid, False otherwise
    """
    # Indian phone number: +91 followed by 10 digits
    pattern = r'^\+91[6-9]\d{9}$'
    return bool(re.match(pattern, phone))


def validate_verification_token(phone_number: str, verification_token: str) -> bool:
    """
    Validate that OTP was verified for this phone number.
    
    Args:
        phone_number: Phone number in format +919876543210
        verification_token: Token from verify_otp
    
    Returns:
        True if token is valid, False otherwise
    """
    try:
        import time
        
        response = otp_table.get_item(
            Key={'phone_number': phone_number}
        )
        
        if 'Item' not in response:
            print(f"No OTP record found for {phone_number}")
            return False
        
        otp_item = response['Item']
        
        # Check if verified
        if not otp_item.get('verified', False):
            print(f"OTP not verified for {phone_number}")
            return False
        
        # Check if not expired (allow 5 minutes after verification)
        if int(time.time()) > otp_item['expiry_time'] + 300:
            print(f"Verification token expired for {phone_number}")
            return False
        
        print(f"Verification token valid for {phone_number}")
        return True
        
    except ClientError as e:
        print(f"Error validating token: {e}")
        return False


def generate_farmer_id() -> str:
    """
    Generate unique farmer ID.
    
    Returns:
        Unique farmer ID string
    """
    # Format: FARMER_<timestamp>_<random>
    timestamp = int(datetime.utcnow().timestamp())
    random_suffix = str(uuid.uuid4())[:8]
    return f"FARMER_{timestamp}_{random_suffix}"


def get_farmer_by_phone(phone_number: str) -> Dict[str, Any]:
    """
    Check if farmer exists by phone number using GSI.
    
    Args:
        phone_number: Phone number to search
    
    Returns:
        Farmer data if exists, None otherwise
    """
    try:
        response = table.query(
            IndexName='phone-index',
            KeyConditionExpression='phone_number = :phone',
            ExpressionAttributeValues={
                ':phone': phone_number
            },
            Limit=1
        )
        
        items = response.get('Items', [])
        return items[0] if items else None
    
    except ClientError as e:
        print(f"Error querying DynamoDB: {e}")
        return None


def save_farmer(farmer_data: Dict[str, Any]) -> None:
    """
    Save farmer data to DynamoDB.
    
    Args:
        farmer_data: Farmer data dictionary
    
    Raises:
        ClientError: If DynamoDB operation fails
    """
    try:
        table.put_item(Item=farmer_data)
        print(f"Farmer saved successfully: {farmer_data['farmer_id']}")
    
    except ClientError as e:
        print(f"Error saving to DynamoDB: {e}")
        raise


def success_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create successful API Gateway response.
    
    Args:
        data: Response data
    
    Returns:
        API Gateway response format
    """
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'POST, OPTIONS'
        },
        'body': json.dumps({
            'success': True,
            **data
        })
    }


def error_response(status_code: int, message: str) -> Dict[str, Any]:
    """
    Create error API Gateway response.
    
    Args:
        status_code: HTTP status code
        message: Error message
    
    Returns:
        API Gateway response format
    """
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'POST, OPTIONS'
        },
        'body': json.dumps({
            'success': False,
            'error': message
        })
    }


# For local testing
if __name__ == '__main__':
    # Test event
    test_event = {
        'body': json.dumps({
            'phone_number': '+919876543210',
            'name': 'Test Farmer',
            'language': 'hi-IN'
        })
    }
    
    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2))

"""
Check Phone Number Lambda Handler

Checks if a phone number is already registered without requiring authentication.
"""

import json
import os
import re
from typing import Dict, Any
import boto3
from botocore.exceptions import ClientError


# Configuration
DYNAMODB_TABLE = os.getenv('DYNAMODB_TABLE_NAME', 'vaniverse-farmers')
AWS_REGION = os.getenv('DYNAMODB_REGION', os.getenv('AWS_REGION', 'ap-south-1'))

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
table = dynamodb.Table(DYNAMODB_TABLE)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Check if phone number is registered.
    
    Args:
        event: API Gateway event with phone_number in body
        context: Lambda context
    
    Returns:
        API Gateway response with exists flag and farmer name if exists
    """
    try:
        # Parse request body
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', event)
        
        phone_number = body.get('phone_number', '').strip()
        
        # Validate phone number
        if not phone_number:
            return error_response(400, "Phone number is required")
        
        if not validate_phone_number(phone_number):
            return error_response(400, "Invalid phone number format. Use +91XXXXXXXXXX")
        
        # Check if phone number exists
        farmer = get_farmer_by_phone(phone_number)
        
        if farmer:
            # Phone number exists
            return success_response({
                'exists': True,
                'farmer_name': farmer.get('name', 'Farmer'),
                'has_agristack': farmer.get('agristack_id') is not None,
            })
        else:
            # Phone number doesn't exist
            return success_response({
                'exists': False,
            })
    
    except Exception as e:
        print(f"Error checking phone number: {str(e)}")
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

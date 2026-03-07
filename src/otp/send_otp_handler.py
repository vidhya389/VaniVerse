"""
Send OTP Lambda Handler

Generates and sends OTP to farmer's phone number via SMS.
"""

import json
import logging
from typing import Dict, Any
from otp_service import OTPService

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for sending OTP.
    
    Expected input:
    {
        "phone_number": "+919876543210"
    }
    
    Returns:
    {
        "statusCode": 200,
        "body": {
            "success": true,
            "message": "OTP sent successfully",
            "expiry_minutes": 10
        }
    }
    """
    logger.info(f"Received send OTP request: {json.dumps(event)}")
    
    try:
        # Parse request body
        if 'body' in event:
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        else:
            body = event
        
        # Validate required fields
        if 'phone_number' not in body:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'success': False,
                    'error': 'Missing required field: phone_number'
                })
            }
        
        phone_number = body['phone_number'].strip()
        
        # Initialize OTP service
        otp_service = OTPService()
        
        # Send OTP
        result = otp_service.send_otp(phone_number)
        
        logger.info(f"OTP sent successfully to {phone_number}")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(result)
        }
        
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'success': False,
                'error': str(e)
            })
        }
        
    except Exception as e:
        logger.error(f"Error sending OTP: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'success': False,
                'error': 'Failed to send OTP. Please try again.'
            })
        }

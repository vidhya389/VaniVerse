"""
Verify OTP Lambda Handler

Verifies OTP code entered by farmer.
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
    Lambda handler for verifying OTP.
    
    Expected input:
    {
        "phone_number": "+919876543210",
        "otp_code": "123456"
    }
    
    Returns:
    {
        "statusCode": 200,
        "body": {
            "success": true,
            "message": "OTP verified successfully",
            "verification_token": "token_string",
            "phone_number": "+919876543210"
        }
    }
    """
    logger.info(f"Received verify OTP request")
    
    try:
        # Parse request body
        if 'body' in event:
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        else:
            body = event
        
        # Validate required fields
        if 'phone_number' not in body or 'otp_code' not in body:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'success': False,
                    'error': 'Missing required fields: phone_number, otp_code'
                })
            }
        
        phone_number = body['phone_number'].strip()
        otp_code = body['otp_code'].strip()
        
        # Initialize OTP service
        otp_service = OTPService()
        
        # Verify OTP
        result = otp_service.verify_otp(phone_number, otp_code)
        
        logger.info(f"OTP verified successfully for {phone_number}")
        
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
        logger.error(f"Error verifying OTP: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'success': False,
                'error': 'Failed to verify OTP. Please try again.'
            })
        }

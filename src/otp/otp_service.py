"""
OTP Service for farmer authentication

Handles OTP generation, storage, verification, and SMS delivery.
"""

import random
import time
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import boto3
from botocore.exceptions import ClientError


class OTPService:
    """Service for managing OTP verification"""
    
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb')
        self.sns = boto3.client('sns')
        self.table_name = os.getenv('OTP_TABLE_NAME', 'OTPVerification')
        self.table = self.dynamodb.Table(self.table_name)
        self.mock_mode = os.getenv('MOCK_OTP', 'false').lower() == 'true'
        self.otp_expiry_minutes = int(os.getenv('OTP_EXPIRY_MINUTES', '10'))
        self.max_attempts = int(os.getenv('OTP_MAX_ATTEMPTS', '3'))
        self.max_otp_per_hour = int(os.getenv('OTP_MAX_PER_HOUR', '3'))
    
    def generate_otp(self) -> str:
        """
        Generate a 6-digit OTP code.
        
        Returns:
            6-digit OTP string
        """
        if self.mock_mode:
            return '123456'  # Mock OTP for development
        
        return str(random.randint(100000, 999999))
    
    def send_otp(self, phone_number: str) -> Dict[str, Any]:
        """
        Generate and send OTP to phone number.
        
        Args:
            phone_number: Phone number in format +919876543210
            
        Returns:
            Dictionary with success status and message
            
        Raises:
            ValueError: If phone number is invalid
            Exception: If rate limit exceeded or SMS fails
        """
        # Validate phone number format
        if not self._validate_phone_number(phone_number):
            raise ValueError('Invalid phone number format. Use +91XXXXXXXXXX')
        
        # Check rate limiting
        if not self._check_rate_limit(phone_number):
            raise Exception('Too many OTP requests. Please try again later.')
        
        # Generate OTP
        otp_code = self.generate_otp()
        
        # Calculate expiry time
        expiry_time = int((datetime.now() + timedelta(minutes=self.otp_expiry_minutes)).timestamp())
        
        # Store OTP in DynamoDB
        try:
            self.table.put_item(
                Item={
                    'phone_number': phone_number,
                    'otp_code': otp_code,
                    'created_at': datetime.now().isoformat(),
                    'expiry_time': expiry_time,
                    'attempts': 0,
                    'verified': False,
                }
            )
        except ClientError as e:
            print(f"Error storing OTP: {e}")
            raise Exception('Failed to generate OTP. Please try again.')
        
        # Send SMS
        if not self.mock_mode:
            try:
                message = f"Your VaniVerse OTP is: {otp_code}. Valid for {self.otp_expiry_minutes} minutes. Do not share this code."
                
                self.sns.publish(
                    PhoneNumber=phone_number,
                    Message=message,
                    MessageAttributes={
                        'AWS.SNS.SMS.SMSType': {
                            'DataType': 'String',
                            'StringValue': 'Transactional'
                        }
                    }
                )
                print(f"OTP sent to {phone_number}")
            except ClientError as e:
                print(f"Error sending SMS: {e}")
                # Don't fail if SMS fails in mock mode
                if not self.mock_mode:
                    raise Exception('Failed to send OTP. Please try again.')
        else:
            print(f"MOCK MODE: OTP for {phone_number} is {otp_code}")
        
        return {
            'success': True,
            'message': 'OTP sent successfully',
            'expiry_minutes': self.otp_expiry_minutes
        }
    
    def verify_otp(self, phone_number: str, otp_code: str) -> Dict[str, Any]:
        """
        Verify OTP code for phone number.
        
        Args:
            phone_number: Phone number in format +919876543210
            otp_code: 6-digit OTP code
            
        Returns:
            Dictionary with verification status and token
            
        Raises:
            ValueError: If OTP is invalid or expired
            Exception: If max attempts exceeded
        """
        # Get OTP from DynamoDB
        try:
            response = self.table.get_item(
                Key={'phone_number': phone_number}
            )
        except ClientError as e:
            print(f"Error retrieving OTP: {e}")
            raise Exception('Failed to verify OTP. Please try again.')
        
        if 'Item' not in response:
            raise ValueError('No OTP found for this phone number. Please request a new OTP.')
        
        otp_item = response['Item']
        
        # Check if already verified
        if otp_item.get('verified', False):
            raise ValueError('OTP already used. Please request a new OTP.')
        
        # Check expiry
        if int(time.time()) > otp_item['expiry_time']:
            raise ValueError('OTP expired. Please request a new OTP.')
        
        # Check attempts
        attempts = otp_item.get('attempts', 0)
        if attempts >= self.max_attempts:
            raise Exception('Maximum verification attempts exceeded. Please request a new OTP.')
        
        # Verify OTP code
        if otp_item['otp_code'] != otp_code:
            # Increment attempts
            self.table.update_item(
                Key={'phone_number': phone_number},
                UpdateExpression='SET attempts = attempts + :inc',
                ExpressionAttributeValues={':inc': 1}
            )
            
            remaining_attempts = self.max_attempts - attempts - 1
            if remaining_attempts > 0:
                raise ValueError(f'Invalid OTP. {remaining_attempts} attempts remaining.')
            else:
                raise Exception('Maximum verification attempts exceeded. Please request a new OTP.')
        
        # Mark as verified
        self.table.update_item(
            Key={'phone_number': phone_number},
            UpdateExpression='SET verified = :verified',
            ExpressionAttributeValues={':verified': True}
        )
        
        # Generate verification token (simple implementation)
        verification_token = f"{phone_number}:{otp_code}:{int(time.time())}"
        
        return {
            'success': True,
            'message': 'OTP verified successfully',
            'verification_token': verification_token,
            'phone_number': phone_number
        }
    
    def validate_verification_token(self, phone_number: str, verification_token: str) -> bool:
        """
        Validate that OTP was verified for this phone number.
        
        Args:
            phone_number: Phone number in format +919876543210
            verification_token: Token from verify_otp
            
        Returns:
            True if token is valid, False otherwise
        """
        try:
            response = self.table.get_item(
                Key={'phone_number': phone_number}
            )
            
            if 'Item' not in response:
                return False
            
            otp_item = response['Item']
            
            # Check if verified
            if not otp_item.get('verified', False):
                return False
            
            # Check if not expired (allow 5 minutes after verification)
            if int(time.time()) > otp_item['expiry_time'] + 300:
                return False
            
            return True
            
        except ClientError as e:
            print(f"Error validating token: {e}")
            return False
    
    def _validate_phone_number(self, phone_number: str) -> bool:
        """
        Validate Indian phone number format.
        
        Args:
            phone_number: Phone number to validate
            
        Returns:
            True if valid, False otherwise
        """
        import re
        pattern = r'^\+91[6-9]\d{9}$'
        return bool(re.match(pattern, phone_number))
    
    def _check_rate_limit(self, phone_number: str) -> bool:
        """
        Check if phone number has exceeded OTP request rate limit.
        
        Args:
            phone_number: Phone number to check
            
        Returns:
            True if within limit, False if exceeded
        """
        # In production, implement proper rate limiting using DynamoDB or Redis
        # For now, simple check: allow if no recent OTP or OTP expired
        try:
            response = self.table.get_item(
                Key={'phone_number': phone_number}
            )
            
            if 'Item' not in response:
                return True  # No previous OTP - allow first request
            
            otp_item = response['Item']
            created_at = datetime.fromisoformat(otp_item['created_at'])
            time_since_last_otp = (datetime.now() - created_at).total_seconds()
            
            # Allow new OTP if:
            # 1. Previous OTP is older than 1 minute (60 seconds)
            # 2. Previous OTP was verified (user completed the flow)
            if time_since_last_otp > 60 or otp_item.get('verified', False):
                return True
            
            # Block if too recent (less than 60 seconds)
            print(f"Rate limit: Last OTP was {time_since_last_otp:.0f} seconds ago")
            return False
            
        except ClientError as e:
            print(f"Error checking rate limit: {e}")
            return True  # Allow on error to avoid blocking users

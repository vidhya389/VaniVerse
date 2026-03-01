"""
Cross-platform Lambda packaging script for VaniVerse
"""
import os
import shutil
import subprocess
import zipfile
from pathlib import Path

def package_lambda():
    """Package Lambda function with dependencies"""
    
    # Clean previous builds
    print("Cleaning previous builds...")
    if os.path.exists('lambda_package'):
        shutil.rmtree('lambda_package')
    if os.path.exists('vaniverse-lambda.zip'):
        os.remove('vaniverse-lambda.zip')
    
    # Create package directory
    print("Creating package directory...")
    os.makedirs('lambda_package', exist_ok=True)
    
    # Install dependencies
    print("Installing dependencies...")
    subprocess.run([
        'pip', 'install', '-r', 'requirements.txt',
        '-t', 'lambda_package'
    ], check=True)
    
    # Copy src folder
    print("Copying src folder...")
    shutil.copytree('src', 'lambda_package/src')
    
    # Create zip file
    print("Creating zip file...")
    with zipfile.ZipFile('vaniverse-lambda.zip', 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk('lambda_package'):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, 'lambda_package')
                zipf.write(file_path, arcname)
    
    print(f"Package created: vaniverse-lambda.zip ({os.path.getsize('vaniverse-lambda.zip') / 1024 / 1024:.2f} MB)")
    print("\nNext steps:")
    print("1. Upload vaniverse-lambda.zip to AWS Lambda")
    print("2. Set handler to: src.lambda_handler.lambda_handler")
    print("\nOr use AWS CLI:")
    print("aws lambda update-function-code --function-name YOUR_FUNCTION_NAME --zip-file fileb://vaniverse-lambda.zip --region ap-south-1")
    print("aws lambda update-function-configuration --function-name YOUR_FUNCTION_NAME --handler src.lambda_handler.lambda_handler --region ap-south-1")

if __name__ == '__main__':
    package_lambda()

"""
Validation script to verify VaniVerse setup

This script checks that all required files and configurations are in place.
"""

import os
import sys

def check_file_exists(filepath, description):
    """Check if a file exists"""
    if os.path.exists(filepath):
        print(f"✓ {description}: {filepath}")
        return True
    else:
        print(f"✗ {description} missing: {filepath}")
        return False

def check_directory_exists(dirpath, description):
    """Check if a directory exists"""
    if os.path.isdir(dirpath):
        print(f"✓ {description}: {dirpath}")
        return True
    else:
        print(f"✗ {description} missing: {dirpath}")
        return False

def main():
    """Main validation function"""
    print("=" * 60)
    print("VaniVerse Setup Validation")
    print("=" * 60)
    print()
    
    all_checks_passed = True
    
    # Check core files
    print("Checking core files...")
    print("-" * 60)
    all_checks_passed &= check_file_exists("requirements.txt", "Requirements file")
    all_checks_passed &= check_file_exists(".env.example", "Environment template")
    all_checks_passed &= check_file_exists(".gitignore", "Git ignore file")
    all_checks_passed &= check_file_exists("README.md", "README file")
    all_checks_passed &= check_file_exists("DEPLOYMENT.md", "Deployment guide")
    all_checks_passed &= check_file_exists("pytest.ini", "Pytest configuration")
    print()
    
    # Check source directories
    print("Checking source directories...")
    print("-" * 60)
    all_checks_passed &= check_directory_exists("src", "Source directory")
    all_checks_passed &= check_directory_exists("src/models", "Models directory")
    all_checks_passed &= check_directory_exists("src/speech", "Speech directory")
    all_checks_passed &= check_directory_exists("src/context", "Context directory")
    all_checks_passed &= check_directory_exists("src/agents", "Agents directory")
    all_checks_passed &= check_directory_exists("src/prompting", "Prompting directory")
    all_checks_passed &= check_directory_exists("src/safety", "Safety directory")
    all_checks_passed &= check_directory_exists("src/utils", "Utils directory")
    all_checks_passed &= check_directory_exists("tests", "Tests directory")
    print()
    
    # Check source files
    print("Checking source files...")
    print("-" * 60)
    all_checks_passed &= check_file_exists("src/__init__.py", "Source init")
    all_checks_passed &= check_file_exists("src/config.py", "Configuration module")
    all_checks_passed &= check_file_exists("src/lambda_handler.py", "Lambda handler")
    print()
    
    # Check scripts
    print("Checking scripts...")
    print("-" * 60)
    all_checks_passed &= check_directory_exists("scripts", "Scripts directory")
    all_checks_passed &= check_file_exists("scripts/setup_infrastructure.py", "Infrastructure setup script")
    all_checks_passed &= check_file_exists("scripts/setup_venv.bat", "Windows setup script")
    all_checks_passed &= check_file_exists("scripts/setup_venv.sh", "Linux/Mac setup script")
    print()
    
    # Check test files
    print("Checking test files...")
    print("-" * 60)
    all_checks_passed &= check_file_exists("tests/__init__.py", "Tests init")
    all_checks_passed &= check_file_exists("tests/test_config.py", "Config tests")
    print()
    
    # Check environment configuration
    print("Checking environment configuration...")
    print("-" * 60)
    if os.path.exists(".env"):
        print("✓ .env file exists (credentials configured)")
    else:
        print("⚠ .env file not found (copy from .env.example and configure)")
        print("  Run: copy .env.example .env")
    print()
    
    # Try to import config
    print("Checking Python imports...")
    print("-" * 60)
    try:
        sys.path.insert(0, '.')
        from src.config import Config
        print("✓ Config module imports successfully")
        print(f"  - AWS Region: {Config.AWS_REGION}")
        print(f"  - Input Bucket: {Config.AUDIO_INPUT_BUCKET}")
        print(f"  - Output Bucket: {Config.AUDIO_OUTPUT_BUCKET}")
        print(f"  - Use Mock UFSI: {Config.USE_MOCK_UFSI}")
    except Exception as e:
        print(f"✗ Failed to import config: {e}")
        all_checks_passed = False
    print()
    
    # Summary
    print("=" * 60)
    if all_checks_passed:
        print("✓ All validation checks passed!")
        print()
        print("Next steps:")
        print("1. Create virtual environment: python -m venv venv")
        print("2. Activate virtual environment:")
        print("   - Windows: venv\\Scripts\\activate")
        print("   - Linux/Mac: source venv/bin/activate")
        print("3. Install dependencies: pip install -r requirements.txt")
        print("4. Copy .env.example to .env and configure credentials")
        print("5. Run infrastructure setup: python scripts/setup_infrastructure.py")
    else:
        print("✗ Some validation checks failed")
        print("Please review the errors above and fix any missing files")
    print("=" * 60)
    
    return all_checks_passed

if __name__ == '__main__':
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Validation failed with error: {e}")
        sys.exit(1)

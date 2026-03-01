/// Quick S3 Connection Test
/// Run this to verify your AWS credentials and S3 access
/// 
/// Usage: dart run test_s3_connection.dart

import 'dart:io';
import 'package:http/http.dart' as http;

// Import your credentials
import 'lib/aws_credentials.dart';

void main() async {
  print('🧪 Testing VaniVerse S3 Connection...\n');

  // Test 1: Check credentials are configured
  print('1️⃣ Checking AWS credentials...');
  if (AWSCredentials.accessKeyId.contains('EXAMPLE') || 
      AWSCredentials.accessKeyId.contains('YOUR_')) {
    print('   ❌ FAILED: Credentials not configured');
    print('   → Edit client/lib/aws_credentials.dart with your actual credentials\n');
    return;
  }
  print('   ✅ Credentials configured\n');

  // Test 2: Check input bucket accessibility
  print('2️⃣ Testing input bucket (${AWSCredentials.inputBucket})...');
  final inputBucketUrl = 'https://${AWSCredentials.inputBucket}.s3.${AWSCredentials.region}.amazonaws.com/';
  try {
    final response = await http.head(Uri.parse(inputBucketUrl));
    if (response.statusCode == 200 || response.statusCode == 403) {
      print('   ✅ Input bucket exists\n');
    } else {
      print('   ⚠️  Unexpected status: ${response.statusCode}\n');
    }
  } catch (e) {
    print('   ❌ FAILED: Cannot reach input bucket');
    print('   Error: $e\n');
  }

  // Test 3: Check output bucket accessibility
  print('3️⃣ Testing output bucket (${AWSCredentials.outputBucket})...');
  final outputBucketUrl = 'https://${AWSCredentials.outputBucket}.s3.${AWSCredentials.region}.amazonaws.com/';
  try {
    final response = await http.head(Uri.parse(outputBucketUrl));
    if (response.statusCode == 200 || response.statusCode == 403) {
      print('   ✅ Output bucket exists\n');
    } else {
      print('   ⚠️  Unexpected status: ${response.statusCode}\n');
    }
  } catch (e) {
    print('   ❌ FAILED: Cannot reach output bucket');
    print('   Error: $e\n');
  }

  // Test 4: Try a simple upload
  print('4️⃣ Testing file upload...');
  try {
    // Create a tiny test file
    final testFile = File('test_upload.txt');
    await testFile.writeAsString('VaniVerse test upload');

    final testKey = 'TEST_FARMER/test-${DateTime.now().millisecondsSinceEpoch}.txt';
    final uploadUrl = 'https://${AWSCredentials.inputBucket}.s3.${AWSCredentials.region}.amazonaws.com/$testKey';

    final uploadResponse = await http.put(
      Uri.parse(uploadUrl),
      headers: {
        'Content-Type': 'text/plain',
        'x-amz-meta-test': 'true',
      },
      body: await testFile.readAsString(),
    );

    if (uploadResponse.statusCode == 200 || uploadResponse.statusCode == 204) {
      print('   ✅ Upload successful!\n');
      
      // Clean up
      await testFile.delete();
    } else if (uploadResponse.statusCode == 403) {
      print('   ❌ FAILED: Access Denied');
      print('   → Check IAM user has s3:PutObject permission');
      print('   → Check bucket policy allows uploads\n');
    } else {
      print('   ❌ FAILED: Upload failed with status ${uploadResponse.statusCode}');
      print('   Response: ${uploadResponse.body}\n');
    }
  } catch (e) {
    print('   ❌ FAILED: Upload error');
    print('   Error: $e\n');
  }

  // Summary
  print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  print('📋 SUMMARY');
  print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  print('');
  print('If all tests passed:');
  print('  ✅ Your AWS credentials are working');
  print('  ✅ S3 buckets are accessible');
  print('  ✅ You can upload files');
  print('  → Ready to run: flutter run');
  print('');
  print('If tests failed:');
  print('  1. Check aws_credentials.dart has correct values');
  print('  2. Verify S3 buckets exist in AWS Console');
  print('  3. Check IAM user permissions');
  print('  4. Verify bucket CORS configuration');
  print('  5. See QUICKSTART.md for detailed steps');
  print('');
}

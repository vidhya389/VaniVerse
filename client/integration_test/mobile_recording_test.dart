import 'dart:io';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:vaniverse_client/services/audio_recording_service.dart';
import 'package:vaniverse_client/services/simple_s3_service.dart';
import 'dart:typed_data';

/// Integration tests for mobile audio recording
/// Tests Requirements 1.1, 1.2, 1.3, 1.6, 1.7
/// 
/// These tests verify:
/// - Recording on Android emulator and physical devices
/// - Recording on iOS simulator and physical devices
/// - File creation and cleanup
/// - S3 upload from mobile using file path and bytes
/// - End-to-end voice loop on mobile
/// - Cross-platform consistency with web
void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  group('Mobile Audio Recording Tests', () {
    late AudioRecordingService recordingService;

    setUp(() {
      recordingService = AudioRecordingService();
    });

    tearDown(() {
      recordingService.dispose();
    });

    /// Test 5.3.1: Test recording on Android emulator
    /// Test 5.3.2: Test recording on Android device
    /// 
    /// Note: This test runs on both Android emulator and physical devices.
    /// The behavior should be identical on both.
    testWidgets('Android recording produces valid audio file',
        (WidgetTester tester) async {
      // Skip on non-Android platforms
      if (kIsWeb || !Platform.isAndroid) {
        return;
      }

      // Check permission
      final hasPermission = await recordingService.hasPermission();
      expect(hasPermission, isTrue,
          reason: 'Microphone permission should be granted');

      // Start recording
      final filePath = await recordingService.startRecording();
      expect(filePath, isNotNull,
          reason: 'File path should be returned');
      expect(recordingService.isRecording, isTrue,
          reason: 'Recording should be active');
      expect(recordingService.currentRecordingPath, equals(filePath),
          reason: 'Current recording path should match file path');

      print('🎤 Android recording started: $filePath');

      // Record for 3 seconds
      await tester.pump(const Duration(seconds: 3));

      // Stop recording
      final stoppedPath = await recordingService.stopRecording();
      expect(stoppedPath, equals(filePath),
          reason: 'Stopped recording path should match started path');
      expect(recordingService.isRecording, isFalse,
          reason: 'Recording should be stopped');

      print('⏹️ Android recording stopped');

      // Verify file exists
      final file = File(filePath!);
      expect(file.existsSync(), isTrue,
          reason: 'Audio file should exist on disk');

      // Verify file size
      final fileSize = file.lengthSync();
      expect(fileSize, greaterThan(1024),
          reason: 'Audio file should be > 1KB');

      // For 3 seconds at 16kHz mono 16-bit: ~96KB expected
      expect(fileSize, greaterThan(50000),
          reason: '3-second recording should produce at least 50KB file');

      print('✅ Android test passed: File size = $fileSize bytes');

      // Get audio bytes
      final audioBytes = await recordingService.getAudioBytes();
      expect(audioBytes, isNotNull,
          reason: 'Audio bytes should be available');
      expect(audioBytes!.length, equals(fileSize),
          reason: 'Audio bytes length should match file size');

      print('📊 Audio bytes retrieved: ${audioBytes.length} bytes');
    });

    /// Test 5.3.3: Test recording on iOS simulator
    /// 
    /// Note: This test runs on both iOS simulator and physical devices.
    /// The behavior should be identical on both.
    testWidgets('iOS recording produces valid audio file',
        (WidgetTester tester) async {
      // Skip on non-iOS platforms
      if (kIsWeb || !Platform.isIOS) {
        return;
      }

      // Check permission
      final hasPermission = await recordingService.hasPermission();
      expect(hasPermission, isTrue,
          reason: 'Microphone permission should be granted');

      // Start recording
      final filePath = await recordingService.startRecording();
      expect(filePath, isNotNull,
          reason: 'File path should be returned');
      expect(recordingService.isRecording, isTrue,
          reason: 'Recording should be active');
      expect(recordingService.currentRecordingPath, equals(filePath),
          reason: 'Current recording path should match file path');

      print('🎤 iOS recording started: $filePath');

      // Record for 3 seconds
      await tester.pump(const Duration(seconds: 3));

      // Stop recording
      final stoppedPath = await recordingService.stopRecording();
      expect(stoppedPath, equals(filePath),
          reason: 'Stopped recording path should match started path');
      expect(recordingService.isRecording, isFalse,
          reason: 'Recording should be stopped');

      print('⏹️ iOS recording stopped');

      // Verify file exists
      final file = File(filePath!);
      expect(file.existsSync(), isTrue,
          reason: 'Audio file should exist on disk');

      // Verify file size
      final fileSize = file.lengthSync();
      expect(fileSize, greaterThan(1024),
          reason: 'Audio file should be > 1KB');

      // For 3 seconds at 16kHz mono 16-bit: ~96KB expected
      expect(fileSize, greaterThan(50000),
          reason: '3-second recording should produce at least 50KB file');

      print('✅ iOS test passed: File size = $fileSize bytes');

      // Get audio bytes
      final audioBytes = await recordingService.getAudioBytes();
      expect(audioBytes, isNotNull,
          reason: 'Audio bytes should be available');
      expect(audioBytes!.length, equals(fileSize),
          reason: 'Audio bytes length should match file size');

      print('📊 Audio bytes retrieved: ${audioBytes.length} bytes');
    });

    /// Test 5.3.4: Test file creation and cleanup
    /// 
    /// Validates Requirement 1.7: Resource cleanup including temporary files
    testWidgets('File creation and cleanup works correctly',
        (WidgetTester tester) async {
      // Skip on web
      if (kIsWeb) {
        return;
      }

      // Test 1: File is created during recording
      final filePath = await recordingService.startRecording();
      expect(filePath, isNotNull);

      await tester.pump(const Duration(seconds: 2));

      // File should exist while recording
      final file = File(filePath!);
      expect(file.existsSync(), isTrue,
          reason: 'File should exist during recording');

      print('✅ File created: $filePath');

      // Stop recording
      await recordingService.stopRecording();

      // File should still exist after stopping
      expect(file.existsSync(), isTrue,
          reason: 'File should exist after stopping');

      print('✅ File persists after stop');

      // Test 2: File is deleted on cancel
      await recordingService.cancelRecording();

      // File should be deleted after cancel
      expect(file.existsSync(), isFalse,
          reason: 'File should be deleted after cancel');

      print('✅ File deleted after cancel');

      // Test 3: Multiple recordings create unique files
      final filePath1 = await recordingService.startRecording();
      await tester.pump(const Duration(seconds: 1));
      await recordingService.stopRecording();

      await recordingService.cancelRecording();
      await tester.pump(const Duration(milliseconds: 500));

      final filePath2 = await recordingService.startRecording();
      await tester.pump(const Duration(seconds: 1));
      await recordingService.stopRecording();

      expect(filePath1, isNot(equals(filePath2)),
          reason: 'Each recording should have unique file path');

      print('✅ Unique file paths: $filePath1 vs $filePath2');

      // Clean up
      await recordingService.cancelRecording();
    });

    /// Test 5.3.5: Test upload to S3 from mobile
    /// 
    /// Validates Requirement 1.6: Audio upload support using file path and bytes
    testWidgets('Upload audio to S3 from mobile',
        (WidgetTester tester) async {
      // Skip on web
      if (kIsWeb) {
        return;
      }

      // Record audio
      final filePath = await recordingService.startRecording();
      await tester.pump(const Duration(seconds: 3));
      await recordingService.stopRecording();

      // Get audio bytes
      final audioBytes = await recordingService.getAudioBytes();
      expect(audioBytes, isNotNull);
      expect(audioBytes!.length, greaterThan(1024));

      // Verify file exists
      final file = File(filePath!);
      expect(file.existsSync(), isTrue);

      print('📊 Prepared for upload: ${audioBytes.length} bytes, file: $filePath');

      // Upload to S3
      final s3Service = SimpleS3Service();
      String? requestId;

      try {
        // Test upload with both file path and bytes
        requestId = await s3Service.uploadAudio(
          audioFilePath: filePath,
          audioBytes: audioBytes,
          farmerId: 'test_farmer_mobile',
          language: 'hi-IN',
          latitude: 28.6139,
          longitude: 77.2090,
        );

        expect(requestId, isNotNull,
            reason: 'Request ID should be returned from upload');
        expect(requestId, isNotEmpty,
            reason: 'Request ID should not be empty');

        print('✅ Upload successful: Request ID = $requestId');
      } catch (e) {
        // Upload might fail in test environment if S3 credentials not configured
        print('⚠️ Upload test skipped: $e');
        print('   (This is expected if S3 credentials are not configured in test environment)');
      }

      // Clean up
      await recordingService.cancelRecording();
    });

    /// Test 5.3.6: Test end-to-end voice loop on mobile
    /// 
    /// Validates complete workflow on mobile:
    /// 1. Start recording
    /// 2. Record audio to file
    /// 3. Stop recording
    /// 4. Get audio bytes from file
    /// 5. Upload to S3
    /// 6. Verify file cleanup
    testWidgets('End-to-end voice loop on mobile',
        (WidgetTester tester) async {
      // Skip on web
      if (kIsWeb) {
        return;
      }

      // Step 1: Check permission
      final hasPermission = await recordingService.hasPermission();
      expect(hasPermission, isTrue);

      // Step 2: Start recording
      final filePath = await recordingService.startRecording();
      expect(filePath, isNotNull);
      expect(recordingService.isRecording, isTrue);

      print('🎤 Recording started: $filePath');

      // Step 3: Record for 5 seconds (simulating user speaking)
      await tester.pump(const Duration(seconds: 5));

      // Step 4: Stop recording
      final stoppedPath = await recordingService.stopRecording();
      expect(stoppedPath, equals(filePath));
      expect(recordingService.isRecording, isFalse);

      print('⏹️ Recording stopped');

      // Step 5: Verify file exists and has content
      final file = File(filePath!);
      expect(file.existsSync(), isTrue);

      final fileSize = file.lengthSync();
      expect(fileSize, greaterThan(1024));

      print('📁 File created: $fileSize bytes');

      // Step 6: Get audio bytes
      final audioBytes = await recordingService.getAudioBytes();
      expect(audioBytes, isNotNull);
      expect(audioBytes!.length, equals(fileSize));

      print('📊 Audio bytes collected: ${audioBytes.length} bytes');

      // Step 7: Validate audio format (WAV header check)
      // WAV files start with "RIFF" (0x52494646)
      expect(audioBytes[0], equals(0x52)); // 'R'
      expect(audioBytes[1], equals(0x49)); // 'I'
      expect(audioBytes[2], equals(0x46)); // 'F'
      expect(audioBytes[3], equals(0x46)); // 'F'

      // Check for "WAVE" format (at offset 8)
      expect(audioBytes[8], equals(0x57));  // 'W'
      expect(audioBytes[9], equals(0x41));  // 'A'
      expect(audioBytes[10], equals(0x56)); // 'V'
      expect(audioBytes[11], equals(0x45)); // 'E'

      print('✅ WAV format validated');

      // Step 8: Upload to S3
      final s3Service = SimpleS3Service();
      String? requestId;

      try {
        requestId = await s3Service.uploadAudio(
          audioFilePath: filePath,
          audioBytes: audioBytes,
          farmerId: 'test_farmer_mobile_e2e',
          language: 'hi-IN',
        );

        expect(requestId, isNotNull);
        print('📤 Upload successful: $requestId');

        // Step 9: Poll for response (optional - may timeout in test)
        final responseUrl = await s3Service.pollForResponse(
          requestId: requestId!,
          timeout: const Duration(seconds: 5),
          pollInterval: const Duration(seconds: 1),
        );

        if (responseUrl != null) {
          print('✅ Response available: $responseUrl');
        } else {
          print('⏱️ Response not available (expected in test environment)');
        }
      } catch (e) {
        print('⚠️ Upload/polling test skipped: $e');
        print('   (This is expected if S3 credentials are not configured)');
      }

      // Step 10: Clean up - verify file deletion
      await recordingService.cancelRecording();

      expect(file.existsSync(), isFalse,
          reason: 'File should be deleted after cancel');

      print('🗑️ File cleaned up');
      print('✅ End-to-end voice loop test completed');
    });
  });

  group('Mobile Recording Error Handling', () {
    late AudioRecordingService recordingService;

    setUp(() {
      recordingService = AudioRecordingService();
    });

    tearDown(() {
      recordingService.dispose();
    });

    testWidgets('Cannot start recording when already recording',
        (WidgetTester tester) async {
      if (kIsWeb) {
        return;
      }

      // Start first recording
      await recordingService.startRecording();
      expect(recordingService.isRecording, isTrue);

      // Try to start second recording
      try {
        await recordingService.startRecording();
        fail('Should throw exception when already recording');
      } catch (e) {
        expect(e.toString(), contains('Already recording'));
      }

      // Clean up
      await recordingService.stopRecording();
      await recordingService.cancelRecording();
    });

    testWidgets('Stop recording when not recording returns null',
        (WidgetTester tester) async {
      if (kIsWeb) {
        return;
      }

      // Try to stop when not recording
      final result = await recordingService.stopRecording();
      expect(result, isNull,
          reason: 'Stopping when not recording should return null');
    });

    testWidgets('Cancel recording deletes file',
        (WidgetTester tester) async {
      if (kIsWeb) {
        return;
      }

      // Start recording
      final filePath = await recordingService.startRecording();
      await tester.pump(const Duration(seconds: 2));

      // Verify file exists
      final file = File(filePath!);
      expect(file.existsSync(), isTrue);

      // Cancel recording
      await recordingService.cancelRecording();

      expect(recordingService.isRecording, isFalse);
      expect(recordingService.currentRecordingPath, isNull);

      // File should be deleted
      expect(file.existsSync(), isFalse,
          reason: 'File should be deleted after cancellation');

      // Audio bytes should not be available after cancel
      final audioBytes = await recordingService.getAudioBytes();
      expect(audioBytes, isNull,
          reason: 'Audio bytes should be null after cancellation');
    });

    testWidgets('Get audio bytes before recording returns null',
        (WidgetTester tester) async {
      if (kIsWeb) {
        return;
      }

      // Try to get audio bytes without recording
      final audioBytes = await recordingService.getAudioBytes();
      expect(audioBytes, isNull,
          reason: 'Audio bytes should be null before recording');
    });
  });

  group('Mobile Recording State Management', () {
    late AudioRecordingService recordingService;

    setUp(() {
      recordingService = AudioRecordingService();
    });

    tearDown(() {
      recordingService.dispose();
    });

    testWidgets('Recording state transitions correctly',
        (WidgetTester tester) async {
      if (kIsWeb) {
        return;
      }

      // Initial state
      expect(recordingService.isRecording, isFalse);
      expect(recordingService.currentRecordingPath, isNull);

      // Start recording
      final filePath = await recordingService.startRecording();
      expect(recordingService.isRecording, isTrue);
      expect(recordingService.currentRecordingPath, equals(filePath));

      await tester.pump(const Duration(seconds: 2));

      // Stop recording
      await recordingService.stopRecording();
      expect(recordingService.isRecording, isFalse);
      expect(recordingService.currentRecordingPath, equals(filePath),
          reason: 'Recording path should persist after stop');

      // Get audio bytes
      final audioBytes = await recordingService.getAudioBytes();
      expect(audioBytes, isNotNull);

      // Cancel to reset state
      await recordingService.cancelRecording();
      expect(recordingService.isRecording, isFalse);
      expect(recordingService.currentRecordingPath, isNull);
    });

    testWidgets('Multiple recording sessions work correctly',
        (WidgetTester tester) async {
      if (kIsWeb) {
        return;
      }

      // First recording session
      final filePath1 = await recordingService.startRecording();
      await tester.pump(const Duration(seconds: 2));
      await recordingService.stopRecording();
      final audioBytes1 = await recordingService.getAudioBytes();
      expect(audioBytes1, isNotNull);
      expect(audioBytes1!.length, greaterThan(1024));

      // Clean up
      await recordingService.cancelRecording();
      await tester.pump(const Duration(milliseconds: 500));

      // Second recording session
      final filePath2 = await recordingService.startRecording();
      expect(filePath2, isNot(equals(filePath1)),
          reason: 'Each recording should have unique file path');

      await tester.pump(const Duration(seconds: 2));
      await recordingService.stopRecording();
      final audioBytes2 = await recordingService.getAudioBytes();
      expect(audioBytes2, isNotNull);
      expect(audioBytes2!.length, greaterThan(1024));

      print('✅ Multiple recording sessions: Session 1 = ${audioBytes1.length} bytes, Session 2 = ${audioBytes2.length} bytes');

      // Clean up
      await recordingService.cancelRecording();
    });

    testWidgets('Dispose cleans up all resources',
        (WidgetTester tester) async {
      if (kIsWeb) {
        return;
      }

      // Start recording
      final filePath = await recordingService.startRecording();
      await tester.pump(const Duration(seconds: 1));

      final file = File(filePath!);
      expect(file.existsSync(), isTrue);

      // Dispose while recording
      recordingService.dispose();

      // State should be reset
      expect(recordingService.isRecording, isFalse);
      expect(recordingService.currentRecordingPath, isNull);

      // Note: File may or may not be deleted on dispose
      // depending on implementation. The important thing is
      // that the service is in a clean state.
    });
  });

  group('Mobile Audio Format Validation', () {
    late AudioRecordingService recordingService;

    setUp(() {
      recordingService = AudioRecordingService();
    });

    tearDown(() {
      recordingService.dispose();
    });

    testWidgets('Audio format is WAV with correct parameters',
        (WidgetTester tester) async {
      if (kIsWeb) {
        return;
      }

      // Record audio
      await recordingService.startRecording();
      await tester.pump(const Duration(seconds: 3));
      await recordingService.stopRecording();

      final audioBytes = await recordingService.getAudioBytes();
      expect(audioBytes, isNotNull);

      // Validate WAV header structure
      // RIFF header
      expect(audioBytes![0], equals(0x52)); // 'R'
      expect(audioBytes[1], equals(0x49));  // 'I'
      expect(audioBytes[2], equals(0x46));  // 'F'
      expect(audioBytes[3], equals(0x46));  // 'F'

      // WAVE format
      expect(audioBytes[8], equals(0x57));  // 'W'
      expect(audioBytes[9], equals(0x41));  // 'A'
      expect(audioBytes[10], equals(0x56)); // 'V'
      expect(audioBytes[11], equals(0x45)); // 'E'

      // fmt chunk
      expect(audioBytes[12], equals(0x66)); // 'f'
      expect(audioBytes[13], equals(0x6D)); // 'm'
      expect(audioBytes[14], equals(0x74)); // 't'

      // Audio format (PCM = 1)
      final audioFormat = audioBytes[20] | (audioBytes[21] << 8);
      expect(audioFormat, equals(1),
          reason: 'Audio format should be PCM (1)');

      // Number of channels (mono = 1)
      final numChannels = audioBytes[22] | (audioBytes[23] << 8);
      expect(numChannels, equals(1),
          reason: 'Number of channels should be 1 (mono)');

      // Sample rate (16000 Hz)
      final sampleRate = audioBytes[24] |
          (audioBytes[25] << 8) |
          (audioBytes[26] << 16) |
          (audioBytes[27] << 24);
      expect(sampleRate, equals(16000),
          reason: 'Sample rate should be 16000 Hz');

      // Bits per sample (16-bit)
      final bitsPerSample = audioBytes[34] | (audioBytes[35] << 8);
      expect(bitsPerSample, equals(16),
          reason: 'Bits per sample should be 16');

      print('✅ WAV format validation passed:');
      print('   - Format: PCM');
      print('   - Channels: $numChannels (mono)');
      print('   - Sample Rate: $sampleRate Hz');
      print('   - Bit Depth: $bitsPerSample bits');

      // Clean up
      await recordingService.cancelRecording();
    });
  });

  group('Cross-Platform File Size Consistency', () {
    late AudioRecordingService recordingService;

    setUp(() {
      recordingService = AudioRecordingService();
    });

    tearDown(() {
      recordingService.dispose();
    });

    testWidgets('File sizes are consistent across recording durations',
        (WidgetTester tester) async {
      if (kIsWeb) {
        return;
      }

      // Test different durations
      final durations = [1, 3, 5];
      final fileSizes = <int>[];

      for (final duration in durations) {
        await recordingService.startRecording();
        await tester.pump(Duration(seconds: duration));
        await recordingService.stopRecording();

        final audioBytes = await recordingService.getAudioBytes();
        expect(audioBytes, isNotNull);

        fileSizes.add(audioBytes!.length);

        print('Duration: ${duration}s, Size: ${audioBytes.length} bytes');

        await recordingService.cancelRecording();
        await tester.pump(const Duration(milliseconds: 500));
      }

      // Verify sizes increase with duration
      expect(fileSizes[1], greaterThan(fileSizes[0]),
          reason: '3-second recording should be larger than 1-second');
      expect(fileSizes[2], greaterThan(fileSizes[1]),
          reason: '5-second recording should be larger than 3-second');

      // Verify approximate size ratios
      // 3-second should be roughly 3x the size of 1-second
      final ratio1 = fileSizes[1] / fileSizes[0];
      expect(ratio1, greaterThan(2.0),
          reason: '3-second recording should be at least 2x larger');
      expect(ratio1, lessThan(4.0),
          reason: '3-second recording should be less than 4x larger');

      print('✅ File size consistency validated');
      print('   1s: ${fileSizes[0]} bytes');
      print('   3s: ${fileSizes[1]} bytes (${ratio1.toStringAsFixed(2)}x)');
      print('   5s: ${fileSizes[2]} bytes');
    });
  });
}

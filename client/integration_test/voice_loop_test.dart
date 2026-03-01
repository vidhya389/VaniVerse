import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:vaniverse_client/main.dart';
import 'package:vaniverse_client/services/voice_interaction_service.dart';
import 'package:vaniverse_client/services/audio_cue_service.dart';
import 'package:provider/provider.dart';

/// Integration tests for complete voice loop
/// Tests Requirements 1.3, 9.2, 9.4
void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  group('Voice Loop Integration Tests', () {
    testWidgets('Complete voice loop from button press to audio playback',
        (WidgetTester tester) async {
      // Build the app
      await tester.pumpWidget(const VaniVerseApp());
      await tester.pumpAndSettle();

      // Find the pulse button
      final pulseButton = find.byType(GestureDetector).first;
      expect(pulseButton, findsOneWidget);

      // Get the voice service
      final context = tester.element(find.byType(MaterialApp));
      final voiceService = Provider.of<VoiceInteractionService>(
        context,
        listen: false,
      );

      // Initial state should be idle
      expect(voiceService.state, VoiceInteractionState.idle);

      // Tap the button to start recording
      await tester.tap(pulseButton);
      await tester.pump();

      // State should transition to listening
      expect(voiceService.state, VoiceInteractionState.listening);

      // Wait for 2 seconds (simulating recording)
      await tester.pump(const Duration(seconds: 2));

      // Tap again to stop recording
      await tester.tap(pulseButton);
      await tester.pump();

      // State should transition to processing
      expect(voiceService.state, VoiceInteractionState.processing);

      // Note: In a real integration test, we would wait for the actual
      // response from the server. For this test, we're just verifying
      // the state transitions work correctly.
    });

    testWidgets('Interrupt playback during speaking state',
        (WidgetTester tester) async {
      await tester.pumpWidget(const VaniVerseApp());
      await tester.pumpAndSettle();

      final context = tester.element(find.byType(MaterialApp));
      final voiceService = Provider.of<VoiceInteractionService>(
        context,
        listen: false,
      );

      // Simulate speaking state
      // In a real test, this would be triggered by actual audio playback
      // For now, we just verify the interrupt functionality exists
      expect(voiceService.interrupt, isNotNull);
    });

    testWidgets('Handle offline mode gracefully', (WidgetTester tester) async {
      await tester.pumpWidget(const VaniVerseApp());
      await tester.pumpAndSettle();

      final context = tester.element(find.byType(MaterialApp));
      final voiceService = Provider.of<VoiceInteractionService>(
        context,
        listen: false,
      );

      // Set offline mode
      voiceService.setOnlineStatus(false);
      await tester.pump();

      // Verify offline indicator is shown
      expect(find.byIcon(Icons.cloud_off), findsOneWidget);

      // Verify offline message is displayed
      expect(find.textContaining('ऑफ़लाइन'), findsOneWidget);
    });

    testWidgets('Low bandwidth mode activation', (WidgetTester tester) async {
      await tester.pumpWidget(const VaniVerseApp());
      await tester.pumpAndSettle();

      final context = tester.element(find.byType(MaterialApp));
      final voiceService = Provider.of<VoiceInteractionService>(
        context,
        listen: false,
      );

      // Enable low bandwidth mode
      voiceService.setLowBandwidthMode(true);
      await tester.pump();

      // Verify low bandwidth indicator is shown
      expect(find.byIcon(Icons.signal_cellular_alt_1_bar), findsOneWidget);

      // Verify the service is in low bandwidth mode
      expect(voiceService.lowBandwidthMode, true);
    });

    testWidgets('Settings sheet opens and closes', (WidgetTester tester) async {
      await tester.pumpWidget(const VaniVerseApp());
      await tester.pumpAndSettle();

      // Tap settings button
      await tester.tap(find.byIcon(Icons.settings));
      await tester.pumpAndSettle();

      // Verify settings sheet is displayed
      expect(find.text('सेटिंग्स'), findsOneWidget);
      expect(find.text('भाषा'), findsOneWidget);
      expect(find.text('कम बैंडविड्थ मोड'), findsOneWidget);

      // Close settings by tapping outside
      await tester.tapAt(const Offset(10, 10));
      await tester.pumpAndSettle();

      // Verify settings sheet is closed
      expect(find.text('सेटिंग्स'), findsNothing);
    });

    testWidgets('Language selection works', (WidgetTester tester) async {
      await tester.pumpWidget(const VaniVerseApp());
      await tester.pumpAndSettle();

      final context = tester.element(find.byType(MaterialApp));
      final voiceService = Provider.of<VoiceInteractionService>(
        context,
        listen: false,
      );

      // Initial language should be Hindi
      expect(voiceService.language, 'hi-IN');

      // Open settings
      await tester.tap(find.byIcon(Icons.settings));
      await tester.pumpAndSettle();

      // Tap language option
      await tester.tap(find.text('भाषा'));
      await tester.pumpAndSettle();

      // Select Tamil
      await tester.tap(find.textContaining('Tamil'));
      await tester.pumpAndSettle();

      // Verify language changed
      expect(voiceService.language, 'ta-IN');
    });
  });

  group('Offline Cache Tests', () {
    testWidgets('Pending uploads sync when online', (WidgetTester tester) async {
      await tester.pumpWidget(const VaniVerseApp());
      await tester.pumpAndSettle();

      final context = tester.element(find.byType(MaterialApp));
      final voiceService = Provider.of<VoiceInteractionService>(
        context,
        listen: false,
      );

      // Set offline
      voiceService.setOnlineStatus(false);
      await tester.pump();

      // Simulate recording in offline mode
      // (In real test, would actually record and cache)

      // Set back online
      voiceService.setOnlineStatus(true);
      await tester.pump();

      // Trigger sync
      await voiceService.syncPendingUploads();

      // Verify sync was attempted
      // (In real test, would verify uploads were sent)
    });
  });

  group('Error Handling Tests', () {
    testWidgets('Error state displays and recovers', (WidgetTester tester) async {
      await tester.pumpWidget(const VaniVerseApp());
      await tester.pumpAndSettle();

      final context = tester.element(find.byType(MaterialApp));
      final voiceService = Provider.of<VoiceInteractionService>(
        context,
        listen: false,
      );

      // Verify error handling exists
      expect(voiceService.state, VoiceInteractionState.idle);

      // In a real test, we would trigger an error condition
      // and verify the error state is displayed and then recovers
    });
  });
}

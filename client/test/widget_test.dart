import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:vaniverse_client/main.dart';

void main() {
  testWidgets('App smoke test', (WidgetTester tester) async {
    // Build our app and trigger a frame.
    await tester.pumpWidget(const VaniVerseApp());

    // Verify that the app title is displayed
    expect(find.text('VaniVerse'), findsOneWidget);
    
    // Verify that the pulse button is present
    expect(find.byType(GestureDetector), findsWidgets);
  });
}

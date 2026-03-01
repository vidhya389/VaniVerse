import 'package:flutter_test/flutter_test.dart';
import 'package:vaniverse_client/services/offline_cache_service.dart';

void main() {
  group('OfflineCacheService', () {
    late OfflineCacheService service;

    setUp(() {
      service = OfflineCacheService();
    });

    test('QAPair serialization works', () {
      final pair = QAPair(
        question: 'Test question',
        answer: 'Test answer',
        timestamp: DateTime(2024, 1, 1),
        audioFileName: 'test.mp3',
        isOfflineResponse: true,
      );

      final json = pair.toJson();
      final restored = QAPair.fromJson(json);

      expect(restored.question, pair.question);
      expect(restored.answer, pair.answer);
      expect(restored.audioFileName, pair.audioFileName);
      expect(restored.isOfflineResponse, pair.isOfflineResponse);
    });

    test('PendingUpload serialization works', () {
      final upload = PendingUpload(
        id: 'test-id',
        audioFilePath: '/path/to/audio.mp3',
        farmerId: 'farmer-123',
        language: 'hi-IN',
        metadata: {'key': 'value'},
        timestamp: DateTime(2024, 1, 1),
      );

      final json = upload.toJson();
      final restored = PendingUpload.fromJson(json);

      expect(restored.id, upload.id);
      expect(restored.audioFilePath, upload.audioFilePath);
      expect(restored.farmerId, upload.farmerId);
      expect(restored.language, upload.language);
      expect(restored.metadata['key'], 'value');
    });

    // Note: Actual cache tests require SharedPreferences mock
    // which is better suited for integration tests
  });
}

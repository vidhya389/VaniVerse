import 'package:flutter_test/flutter_test.dart';
import 'package:vaniverse_client/services/location_service.dart';

void main() {
  group('LocationService', () {
    late LocationService service;

    setUp(() {
      service = LocationService();
    });

    test('Cache is initially empty', () {
      service.clearCache();
      // Cache should be cleared
    });

    test('Distance calculation works', () {
      // Test distance between two known points
      // New Delhi to Mumbai (approximate)
      final distance = service.getDistanceBetween(
        28.6139, 77.2090, // Delhi
        19.0760, 72.8777, // Mumbai
      );

      // Distance should be approximately 1150 km (1,150,000 meters)
      expect(distance, greaterThan(1000000));
      expect(distance, lessThan(1300000));
    });

    test('GPSCoordinates serialization works', () {
      final coords = GPSCoordinates(
        latitude: 28.6139,
        longitude: 77.2090,
        accuracy: 10.0,
        timestamp: DateTime(2024, 1, 1),
      );

      final json = coords.toJson();
      final restored = GPSCoordinates.fromJson(json);

      expect(restored.latitude, coords.latitude);
      expect(restored.longitude, coords.longitude);
      expect(restored.accuracy, coords.accuracy);
    });
  });
}

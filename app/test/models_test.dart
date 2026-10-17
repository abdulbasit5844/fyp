import 'package:dms_app/models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('SafetyEvent parses the backend event JSON', () {
    final e = SafetyEvent.fromJson({
      'id': 'e1',
      'eventType': 'drowsiness',
      'severity': 'critical',
      'status': 'escalated',
      'description': 'Eyes closed (EAR 0.18)',
      'detectedAt': '2026-10-15T12:00:00.000Z',
      'escalatedAt': '2026-10-15T12:00:15.000Z',
      'actionTaken': 'Emergency contacts notified',
      'location': {'type': 'Point', 'coordinates': [73.0479, 33.6844]},
      'signals': {'ear': 0.18, 'sustainedMs': 2400},
      'videoClip': {'id': 'c1', 'status': 'available', 'durationSec': 30},
      'notifications': [
        {'channel': 'sms', 'alertType': 'escalation', 'deliveryStatus': 'sent', 'recipientContact': {'name': 'Dad'}},
      ],
    });
    expect(e.title, 'Drowsiness detected');
    expect(e.isCritical, isTrue);
    expect(e.lat, closeTo(33.6844, 1e-6));
    expect(e.lng, closeTo(73.0479, 1e-6));
    expect(e.clip!.available, isTrue);
    expect(e.notifications.single.contactName, 'Dad');
  });

  test('MonitorSettings round-trips and rounds slider values', () {
    final s = MonitorSettings.fromJson({
      'earThreshold': 0.25, 'earSustainSec': 2, 'headPoseThresholdDeg': 30, 'headPoseSustainSec': 2,
      'emotionSustainSec': 3, 'ackWindowSec': 15, 'alertSensitivity': 3, 'videoRecordingEnabled': true,
      'notifications': {'push': true, 'sound': false, 'smsFallback': true},
    });
    s.earThreshold = 0.23000000001;
    s.alertSensitivity = 4.2;
    final j = s.toJson();
    expect(j['earThreshold'], 0.23);
    expect(j['alertSensitivity'], 4);
    // WhatsApp alerts default to on when the server has not stored the flag yet.
    expect(j['notifications'], {'push': true, 'sound': false, 'smsFallback': true, 'whatsapp': true});
  });

  test('Device state defaults to safe for unknown values', () {
    expect(driverStateFrom('critical'), DriverState.critical);
    expect(driverStateFrom(null), DriverState.safe);
  });
}

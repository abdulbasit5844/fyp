// Plain data classes matching the backend's JSON (see backend/src/models).

DateTime? _date(dynamic v) => v == null ? null : DateTime.parse(v as String).toLocal();
double? _num(dynamic v) => (v as num?)?.toDouble();

class User {
  User(this.id, this.name, this.email, this.role);
  factory User.fromJson(Map<String, dynamic> j) =>
      User(j['id'], j['name'], j['email'], j['role']);

  final String id, name, email, role;
  bool get isOwner => role == 'owner';
}

enum DriverState { safe, warning, critical }

DriverState driverStateFrom(String? s) =>
    DriverState.values.firstWhere((e) => e.name == s, orElse: () => DriverState.safe);

class Device {
  Device.fromJson(Map<String, dynamic> j)
      : id = j['id'],
        deviceId = j['deviceId'],
        name = j['name'] ?? 'My Vehicle',
        online = j['online'] ?? false,
        monitoring = j['monitoring'] ?? false,
        detectionEnabled = j['detectionEnabled'] ?? false,
        state = driverStateFrom(j['currentState']),
        lastSeenAt = _date(j['lastSeenAt']),
        stateUpdatedAt = _date(j['stateUpdatedAt']),
        activeDriverName = (j['activeDriver'] is Map) ? j['activeDriver']['displayName'] : null,
        identity = j['identity'] ?? 'verifying',
        driverPresent = j['driverPresent'] ?? true;

  final String id, deviceId, name;
  final bool online, monitoring;
  final bool detectionEnabled; // Start/Stop detecting from the home screen
  final DriverState state;
  final DateTime? lastSeenAt, stateUpdatedAt;
  final String? activeDriverName;
  /// verifying | verified | unknown | none (nobody enrolled: whoever drives is monitored)
  final String identity;
  bool get unknownDriver => identity == 'unknown';
  /// false: nobody in the camera (no face for 2 s)
  final bool driverPresent;
}

class SafetyEvent {
  SafetyEvent.fromJson(Map<String, dynamic> j)
      : id = j['id'],
        type = j['eventType'],
        severity = j['severity'],
        status = j['status'],
        description = j['description'],
        detectedAt = _date(j['detectedAt'])!,
        acknowledgedAt = _date(j['acknowledgedAt']),
        acknowledgedVia = j['acknowledgedVia'],
        escalatedAt = _date(j['escalatedAt']),
        actionTaken = j['actionTaken'] ?? '',
        lat = (j['location']?['coordinates'] as List?)?.elementAt(1)?.toDouble(),
        lng = (j['location']?['coordinates'] as List?)?.elementAt(0)?.toDouble(),
        signals = (j['signals'] as Map?)?.cast<String, dynamic>() ?? const {},
        clip = j['videoClip'] is Map ? VideoClip.fromJson(j['videoClip']) : null,
        driverName = j['driver'] is Map ? j['driver']['displayName'] : null,
        photo = j['photo'],
        notifications = ((j['notifications'] as List?) ?? const [])
            .map((n) => AlertDelivery.fromJson(n as Map<String, dynamic>))
            .toList();

  final String id, type, severity, status, actionTaken;
  final String? description, acknowledgedVia, driverName;
  final String? photo; // unverified_driver: base64 JPEG of the person in the seat
  final DateTime detectedAt;
  final DateTime? acknowledgedAt, escalatedAt;
  final double? lat, lng;
  final Map<String, dynamic> signals;
  final VideoClip? clip;
  final List<AlertDelivery> notifications;

  bool get isCritical => severity == 'critical';
  bool get isActive => status == 'active';
  String get title => eventTitles[type] ?? type;
}

const eventTitles = {
  'drowsiness': 'Drowsiness detected',
  'yawning': 'Yawning',
  'fatigue': 'Signs of fatigue',
  'inattention': 'Eyes off the road',
  'looking_down': 'Looking down (phone?)',
  'emotional_distress': 'Driver distressed',
  'unverified_driver': 'Unknown person detected',
  'unauthorized_occupant': 'Unknown occupant',
  'key_left_inside': 'Key left inside',
};

class VideoClip {
  VideoClip.fromJson(Map<String, dynamic> j)
      : id = j['id'],
        status = j['status'] ?? 'recording',
        durationSec = _num(j['durationSec']) ?? 30;

  final String id, status;
  final double durationSec;
  bool get available => status == 'available';
}

class AlertDelivery {
  AlertDelivery.fromJson(Map<String, dynamic> j)
      : channel = j['channel'],
        alertType = j['alertType'],
        status = j['deliveryStatus'],
        error = j['error'],
        contactName = j['recipientContact'] is Map ? j['recipientContact']['name'] : null;

  final String channel, alertType, status;
  final String? error, contactName;
}

class EmergencyContact {
  EmergencyContact.fromJson(Map<String, dynamic> j)
      : id = j['id'],
        name = j['name'],
        phone = j['phone'],
        email = j['email'],
        relationship = j['relationship'],
        priority = j['priority'] ?? 1,
        notifyBySms = j['notifyBySms'] ?? true;

  final String id, name, phone;
  final String? email, relationship;
  final int priority;
  final bool notifyBySms;
}

class DriverProfile {
  DriverProfile.fromJson(Map<String, dynamic> j)
      : id = j['id'],
        displayName = j['displayName'],
        isPrimary = j['isPrimary'] ?? false,
        isAuthorized = j['isAuthorized'] ?? true,
        enrolled = j['enrolled'] ?? false,
        photo = j['photo'];

  final String id, displayName;
  final bool isPrimary, isAuthorized, enrolled;
  final String? photo; // base64 JPEG taken at enrollment
}

/// A face-enrollment message from the vehicle unit: the live camera view
/// (and capture progress), then a final result (`done` true).
class EnrollmentUpdate {
  EnrollmentUpdate.progress(Map<String, dynamic> j)
      : driverId = j['driverId'],
        done = false,
        ok = false,
        error = null,
        photo = null,
        capturing = j['mode'] == 'capture',
        samples = (j['samples'] as num?)?.toInt() ?? 0,
        needed = (j['needed'] as num?)?.toInt() ?? 5,
        faceVisible = j['faceVisible'] ?? false,
        secondsLeft = (j['secondsLeft'] as num?)?.toInt(),
        preview = j['preview'];

  EnrollmentUpdate.result(Map<String, dynamic> j)
      : driverId = j['driverId'],
        done = true,
        ok = j['ok'] ?? false,
        error = j['error'],
        photo = j['photo'],
        capturing = false,
        samples = 0,
        needed = 0,
        faceVisible = false,
        secondsLeft = null,
        preview = null;

  final String driverId;
  final bool done, ok, faceVisible, capturing;
  final String? error, preview, photo;
  final int samples, needed;
  final int? secondsLeft;
}

/// Mutable copy of SystemConfig for the settings screen.
class MonitorSettings {
  MonitorSettings.fromJson(Map<String, dynamic> j)
      : earThreshold = _num(j['earThreshold'])!,
        earSustainSec = _num(j['earSustainSec'])!,
        headPoseThresholdDeg = _num(j['headPoseThresholdDeg'])!,
        headPitchThresholdDeg = _num(j['headPitchThresholdDeg']) ?? 20,
        headPoseSustainSec = _num(j['headPoseSustainSec'])!,
        emotionSustainSec = _num(j['emotionSustainSec'])!,
        ackWindowSec = _num(j['ackWindowSec'])!,
        alertSensitivity = _num(j['alertSensitivity'])!,
        videoRecordingEnabled = j['videoRecordingEnabled'] ?? true,
        push = j['notifications']?['push'] ?? true,
        sound = j['notifications']?['sound'] ?? true,
        smsFallback = j['notifications']?['smsFallback'] ?? false,
        whatsapp = j['notifications']?['whatsapp'] ?? true;

  double earThreshold, earSustainSec, headPoseThresholdDeg, headPitchThresholdDeg, headPoseSustainSec;
  double emotionSustainSec, ackWindowSec, alertSensitivity;
  bool videoRecordingEnabled, push, sound, smsFallback, whatsapp;

  Map<String, dynamic> toJson() => {
        'earThreshold': double.parse(earThreshold.toStringAsFixed(2)),
        'earSustainSec': earSustainSec,
        'headPoseThresholdDeg': headPoseThresholdDeg.roundToDouble(),
        'headPitchThresholdDeg': headPitchThresholdDeg.roundToDouble(),
        'headPoseSustainSec': headPoseSustainSec,
        'emotionSustainSec': emotionSustainSec,
        'ackWindowSec': ackWindowSec.roundToDouble(),
        'alertSensitivity': alertSensitivity.round(),
        'videoRecordingEnabled': videoRecordingEnabled,
        'notifications': {'push': push, 'sound': sound, 'smsFallback': smsFallback, 'whatsapp': whatsapp},
      };
}

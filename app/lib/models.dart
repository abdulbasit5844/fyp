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
        state = driverStateFrom(j['currentState']),
        lastSeenAt = _date(j['lastSeenAt']),
        stateUpdatedAt = _date(j['stateUpdatedAt']),
        activeDriverName = (j['activeDriver'] is Map) ? j['activeDriver']['displayName'] : null;

  final String id, deviceId, name;
  final bool online, monitoring;
  final DriverState state;
  final DateTime? lastSeenAt, stateUpdatedAt;
  final String? activeDriverName;
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
        notifications = ((j['notifications'] as List?) ?? const [])
            .map((n) => AlertDelivery.fromJson(n as Map<String, dynamic>))
            .toList();

  final String id, type, severity, status, actionTaken;
  final String? description, acknowledgedVia, driverName;
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
  'inattention': 'Eyes off the road',
  'emotional_distress': 'Driver distressed',
  'unverified_driver': 'Unrecognized driver',
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
        enrolled = j['enrolled'] ?? false;

  final String id, displayName;
  final bool isPrimary, isAuthorized, enrolled;
}

/// Mutable copy of SystemConfig for the settings screen.
class MonitorSettings {
  MonitorSettings.fromJson(Map<String, dynamic> j)
      : earThreshold = _num(j['earThreshold'])!,
        earSustainSec = _num(j['earSustainSec'])!,
        headPoseThresholdDeg = _num(j['headPoseThresholdDeg'])!,
        headPoseSustainSec = _num(j['headPoseSustainSec'])!,
        emotionSustainSec = _num(j['emotionSustainSec'])!,
        ackWindowSec = _num(j['ackWindowSec'])!,
        alertSensitivity = _num(j['alertSensitivity'])!,
        videoRecordingEnabled = j['videoRecordingEnabled'] ?? true,
        push = j['notifications']?['push'] ?? true,
        sound = j['notifications']?['sound'] ?? true,
        smsFallback = j['notifications']?['smsFallback'] ?? false;

  double earThreshold, earSustainSec, headPoseThresholdDeg, headPoseSustainSec;
  double emotionSustainSec, ackWindowSec, alertSensitivity;
  bool videoRecordingEnabled, push, sound, smsFallback;

  Map<String, dynamic> toJson() => {
        'earThreshold': double.parse(earThreshold.toStringAsFixed(2)),
        'earSustainSec': earSustainSec,
        'headPoseThresholdDeg': headPoseThresholdDeg.roundToDouble(),
        'headPoseSustainSec': headPoseSustainSec,
        'emotionSustainSec': emotionSustainSec,
        'ackWindowSec': ackWindowSec.roundToDouble(),
        'alertSensitivity': alertSensitivity.round(),
        'videoRecordingEnabled': videoRecordingEnabled,
        'notifications': {'push': push, 'sound': sound, 'smsFallback': smsFallback},
      };
}

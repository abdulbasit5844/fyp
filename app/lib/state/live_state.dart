import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../api/api_client.dart';
import '../models.dart';

/// Real-time view of the vehicle: device status and alerts awaiting
/// acknowledgment, fed by the backend WebSocket (/ws). On every (re)connect
/// it re-syncs from REST so nothing is missed while offline (REL-4).
class LiveState extends ChangeNotifier {
  LiveState(this.api);

  final ApiClient api;
  final _alertController = StreamController<SafetyEvent>.broadcast();
  final _enrollController = StreamController<EnrollmentUpdate>.broadcast();

  List<Device> devices = [];
  List<SafetyEvent> activeAlerts = [];
  SafetyEvent? lastEvent;
  final Set<String> escalatedIds = {};
  /// Delivery results of escalations, by event id (e.g. the owner's WhatsApp for an unknown driver).
  final Map<String, List<AlertDelivery>> deliveries = {};
  bool connected = false;
  int ackWindowSec = 15;

  WebSocketChannel? _channel;
  StreamSubscription? _sub;
  Timer? _retry;
  int _backoff = 1;
  bool _running = false;

  /// New alerts that should open the full-screen alert view.
  Stream<SafetyEvent> get newAlerts => _alertController.stream;

  /// Face enrollment progress and results from the vehicle unit.
  Stream<EnrollmentUpdate> get enrollment => _enrollController.stream;

  Device? get device => devices.isEmpty ? null : devices.first;

  /// Overall status shown on the home screen.
  DriverState get state {
    if (activeAlerts.any((e) => e.isCritical)) return DriverState.critical;
    if (activeAlerts.isNotEmpty) return DriverState.warning;
    final d = device;
    return d != null && d.online ? d.state : DriverState.safe;
  }

  void start() {
    if (_running) return;
    _running = true;
    _connect();
  }

  void stop() {
    _running = false;
    _retry?.cancel();
    _sub?.cancel();
    _channel?.sink.close();
    connected = false;
  }

  Future<void> refresh() async {
    try {
      final results = await Future.wait([
        api.get('/devices'),
        api.get('/events/active'),
        api.get('/events', query: {'limit': 1}),
        api.get('/config'),
      ]);
      devices = (results[0] as List).map((j) => Device.fromJson(j)).toList();
      activeAlerts = (results[1] as List).map((j) => SafetyEvent.fromJson(j)).toList();
      final items = (results[2] as Map)['items'] as List;
      lastEvent = items.isEmpty ? null : SafetyEvent.fromJson(items.first);
      ackWindowSec = ((results[3] as Map)['ackWindowSec'] as num).round();
      notifyListeners();
    } catch (e) {
      debugPrint('live refresh failed: $e');
    }
  }

  Future<void> _connect() async {
    if (!_running) return;
    // Make sure the access token is fresh before opening the socket.
    try {
      await api.get('/auth/me');
    } catch (_) {}
    final base = Uri.parse(api.tokens.serverUrl);
    final wsUri = base.replace(
      scheme: base.scheme == 'https' ? 'wss' : 'ws',
      path: '${base.path}/ws',
      queryParameters: {'token': api.tokens.accessToken ?? ''},
    );
    try {
      _channel = WebSocketChannel.connect(wsUri);
      await _channel!.ready;
      connected = true;
      _backoff = 1;
      notifyListeners();
      await refresh();
      _sub = _channel!.stream.listen(_onMessage, onDone: _onClosed, onError: (_) => _onClosed());
    } catch (_) {
      _onClosed();
    }
  }

  void _onClosed() {
    connected = false;
    notifyListeners();
    _sub?.cancel();
    if (!_running) return;
    _retry?.cancel();
    _retry = Timer(Duration(seconds: _backoff), _connect);
    _backoff = (_backoff * 2).clamp(1, 30);
  }

  void _onMessage(dynamic raw) {
    final msg = jsonDecode(raw as String) as Map<String, dynamic>;
    final data = msg['data'];
    switch (msg['type']) {
      case 'device':
        final d = Device.fromJson(data);
        devices = [for (final x in devices) x.id == d.id ? d : x];
        if (!devices.any((x) => x.id == d.id)) devices.add(d);
      case 'event':
        final e = SafetyEvent.fromJson(data);
        lastEvent = e;
        if (e.isActive) {
          activeAlerts = [e, ...activeAlerts.where((a) => a.id != e.id)];
          _alertController.add(e);
        }
      case 'event_update' || 'escalation':
        final e = SafetyEvent.fromJson(data);
        if (lastEvent?.id == e.id) lastEvent = e;
        activeAlerts = activeAlerts.where((a) => a.id != e.id).toList();
        if (msg['type'] == 'escalation') {
          escalatedIds.add(e.id);
          _alertController.add(e);
        }
      case 'escalation_delivery':
        deliveries[data['eventId'] as String] =
            [for (final n in (data['notifications'] as List)) AlertDelivery.fromJson(n as Map<String, dynamic>)];
      case 'config':
        ackWindowSec = (data['ackWindowSec'] as num).round();
      case 'enrollment_progress':
        _enrollController.add(EnrollmentUpdate.progress(data));
        return; // nothing on screen besides the enrollment dialog changes
      case 'enrollment':
        _enrollController.add(EnrollmentUpdate.result(data));
    }
    notifyListeners();
  }

  /// Start or stop detecting the driver on the paired unit.
  Future<void> setDetection(bool enabled) async {
    final d = device;
    if (d == null) return;
    final updated = Device.fromJson(await api.post('/devices/${d.id}/detection', {'enabled': enabled}));
    devices = [for (final x in devices) x.id == updated.id ? updated : x];
    if (!enabled) activeAlerts = [];
    notifyListeners();
  }

  Future<SafetyEvent> acknowledge(String eventId) async {
    final e = SafetyEvent.fromJson(await api.post('/events/$eventId/acknowledge'));
    activeAlerts = activeAlerts.where((a) => a.id != eventId).toList();
    notifyListeners();
    return e;
  }

  @override
  void dispose() {
    stop();
    _alertController.close();
    _enrollController.close();
    super.dispose();
  }
}

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:media_kit/media_kit.dart';
import 'package:media_kit_video/media_kit_video.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../api/api_client.dart';
import '../state/live_state.dart';
import '../theme.dart';

/// Live camera view from the vehicle unit (H.264 over RTSP from MediaMTX on the
/// Pi) at 480p 60 fps, 720p 46 fps or 1080p 30 fps — the camera's limits.
/// The unit only streams while this screen is open;
/// the app repeats the request as a keep-alive and the unit stops on its own
/// if the app goes away.
class LiveScreen extends StatefulWidget {
  const LiveScreen({super.key});

  @override
  State<LiveScreen> createState() => _LiveScreenState();
}

/// (name sent to the backend, label, resolution shown on the video)
const _qualities = [
  ('480p', '480p · 60 fps', '640×480'),
  ('720p', '720p · 46 fps', '1280×720'),
  ('1080p', '1080p · 30 fps', '1920×1080'),
];
const _qualityKey = 'liveQuality';

class _LiveScreenState extends State<LiveScreen> {
  String _quality = '480p';
  late final Player _player = Player();
  late final VideoController _controller = VideoController(_player);
  Timer? _keepAlive, _stats;
  String? _error, _url;
  String? _deviceId;
  double? _fps;
  bool _playing = false;

  ApiClient get _api => context.read<ApiClient>();

  @override
  void initState() {
    super.initState();
    _player.stream.error.listen((e) {
      if (mounted && !_playing) setState(() => _error = 'Could not play the stream: $e');
    });
    _player.stream.playing.listen((p) {
      if (mounted) setState(() => _playing = p);
    });
    _loadQualityThenStart();
  }

  Future<void> _loadQualityThenStart() async {
    try {
      final saved = (await SharedPreferences.getInstance()).getString(_qualityKey);
      if (_qualities.any((q) => q.$1 == saved)) _quality = saved!;
    } catch (_) {}
    if (mounted) _start();
  }

  Future<void> _setQuality(String q) async {
    if (q == _quality) return;
    setState(() => _quality = q);
    try {
      await (await SharedPreferences.getInstance()).setString(_qualityKey, q);
    } catch (_) {}
    await _player.stop(); // the unit restarts its camera in the new mode; reconnect
    _start();
  }

  Future<Map<String, dynamic>> _request(bool enabled) async =>
      await _api.post('/devices/$_deviceId/live', {'enabled': enabled, if (enabled) 'quality': _quality})
          as Map<String, dynamic>;

  Future<void> _start() async {
    setState(() {
      _error = null;
      _fps = null;
      _playing = false;
    });
    final device = context.read<LiveState>().device;
    if (device == null) {
      setState(() => _error = 'Pair a vehicle unit first.');
      return;
    }
    _deviceId = device.id;
    try {
      final res = await _request(true);
      _url = res['url'] as String;
      // Low latency: play frames as they arrive, no buffering.
      final native = _player.platform;
      if (native is NativePlayer) {
        for (final (k, v) in [
          ('profile', 'low-latency'),
          ('untimed', 'yes'),
          ('cache', 'no'),
          ('rtsp-transport', 'tcp'),
          ('demuxer-lavf-o', 'fflags=+nobuffer'),
        ]) {
          await native.setProperty(k, v);
        }
      }
      // The unit needs ~1 s to restart its camera in live mode; retry until the stream appears.
      for (var attempt = 0; attempt < 8 && mounted && !_playing; attempt++) {
        await Future.delayed(Duration(milliseconds: attempt == 0 ? 1500 : 1000));
        await _player.open(Media(_url!));
        await Future.delayed(const Duration(milliseconds: 1500));
      }
      if (mounted && !_playing && _error == null) {
        setState(() => _error = 'The vehicle unit did not start streaming. Check that it is online.');
      }
      _keepAlive?.cancel();
      _keepAlive = Timer.periodic(
          const Duration(seconds: 20), (_) => _request(true).catchError((_) => <String, dynamic>{}));
      _stats?.cancel();
      _stats = Timer.periodic(const Duration(seconds: 1), (_) => _readFps());
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    }
  }

  Future<void> _readFps() async {
    final native = _player.platform;
    if (native is! NativePlayer) return;
    try {
      // Measured rate when mpv reports it; in low-latency (untimed) mode it often
      // does not, so fall back to the stream's own frame rate.
      final v = double.tryParse(await native.getProperty('estimated-vf-fps')) ??
          double.tryParse(await native.getProperty('container-fps'));
      if (mounted) setState(() => _fps = v);
    } catch (_) {}
  }

  @override
  void dispose() {
    _keepAlive?.cancel();
    _stats?.cancel();
    if (_deviceId != null) _request(false).catchError((_) => <String, dynamic>{});
    _player.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        title: const Text('Live view'),
        actions: [
          IconButton(tooltip: 'Reconnect', icon: const Icon(Icons.refresh), onPressed: _start),
        ],
      ),
      body: Column(children: [
        Expanded(child: Center(child: _error != null ? _errorView() : _videoView())),
        _qualityPicker(),
      ]),
    );
  }

  Widget _errorView() => Padding(
        padding: const EdgeInsets.all(24),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          const Icon(Icons.videocam_off, color: Colors.white54, size: 64),
          const SizedBox(height: 12),
          Text('$_error\nLive view needs the same Wi-Fi as the vehicle unit.',
              textAlign: TextAlign.center, style: const TextStyle(color: Colors.white)),
          const SizedBox(height: 16),
          FilledButton.icon(onPressed: _start, icon: const Icon(Icons.refresh), label: const Text('Try again')),
        ]),
      );

  Widget _videoView() {
    final resolution = _qualities.firstWhere((q) => q.$1 == _quality).$3;
    return AspectRatio(
      aspectRatio: _quality == '480p' ? 4 / 3 : 16 / 9,
      child: Stack(children: [
        Positioned.fill(child: Video(controller: _controller, controls: NoVideoControls)),
        if (!_playing)
          const Center(
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              CircularProgressIndicator(),
              SizedBox(height: 12),
              Text('Starting the camera…', style: TextStyle(color: Colors.white70)),
            ]),
          ),
        if (_playing)
          Positioned(
            left: 8,
            top: 8,
            child: Row(children: [
              _chip(const Text('● LIVE', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                  criticalColor),
              const SizedBox(width: 6),
              _chip(
                Text(_fps == null ? resolution : '$resolution • ${_fps!.round()} fps',
                    style: const TextStyle(color: Colors.white)),
                Colors.black54,
              ),
            ]),
          ),
      ]),
    );
  }

  Widget _qualityPicker() => Container(
        width: double.infinity,
        color: const Color(0xFF111111),
        padding: const EdgeInsets.fromLTRB(12, 12, 12, 20),
        child: SafeArea(
          top: false,
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            const Text('Quality', style: TextStyle(color: Colors.white70)),
            const SizedBox(height: 8),
            SegmentedButton<String>(
              style: SegmentedButton.styleFrom(
                foregroundColor: Colors.white70,
                selectedForegroundColor: Colors.white,
                selectedBackgroundColor: Theme.of(context).colorScheme.primary.withValues(alpha: 0.5),
              ),
              segments: [for (final (name, label, _) in _qualities) ButtonSegment(value: name, label: Text(label))],
              selected: {_quality},
              onSelectionChanged: (v) => _setQuality(v.first),
            ),
            const SizedBox(height: 6),
            const Text("Higher quality needs a stronger Wi-Fi signal. These are the camera's limits.",
                textAlign: TextAlign.center, style: TextStyle(color: Colors.white38, fontSize: 12)),
          ]),
        ),
      );

  Widget _chip(Widget child, Color color) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(6)),
        child: child,
      );
}

import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';

import '../api/api_client.dart';
import '../models.dart';
import '../state/live_state.dart';
import '../theme.dart';

/// Shows the vehicle unit's camera, warns when nobody is in view, and lets the
/// owner capture the driver's photo and face samples. Returns true when the
/// face was enrolled.
Future<bool> showEnrollDialog(BuildContext context, ApiClient api, LiveState live, DriverProfile driver) async {
  final ok = await showDialog<bool>(
    context: context,
    barrierDismissible: false,
    builder: (_) => _EnrollDialog(api: api, live: live, driver: driver),
  );
  return ok ?? false;
}

class _EnrollDialog extends StatefulWidget {
  const _EnrollDialog({required this.api, required this.live, required this.driver});

  final ApiClient api;
  final LiveState live;
  final DriverProfile driver;

  @override
  State<_EnrollDialog> createState() => _EnrollDialogState();
}

enum _Phase { connecting, live, capturing, success, failed }

class _EnrollDialogState extends State<_EnrollDialog> {
  _Phase _phase = _Phase.connecting;
  String? _error;
  EnrollmentUpdate? _last;
  Uint8List? _view, _photo;
  StreamSubscription<EnrollmentUpdate>? _sub;
  Timer? _watchdog;

  bool get _faceVisible => _last?.faceVisible ?? false;

  @override
  void initState() {
    super.initState();
    _sub = widget.live.enrollment.where((u) => u.driverId == widget.driver.id).listen(_onUpdate);
    _send('preview');
  }

  Future<void> _send(String action) async {
    setState(() {
      _error = null;
      if (action == 'preview') {
        _phase = _Phase.connecting;
        _last = null;
      } else if (action == 'capture') {
        _phase = _Phase.capturing;
      }
    });
    try {
      await widget.api.post('/drivers/${widget.driver.id}/enroll', {'action': action});
      if (action != 'cancel') _armWatchdog();
    } catch (e) {
      if (action != 'cancel') _fail(e.toString());
    }
  }

  // The unit sends a frame every ~0.4 s; silence means it is offline or busy.
  void _armWatchdog() {
    _watchdog?.cancel();
    _watchdog = Timer(const Duration(seconds: 10), () {
      if (_phase == _Phase.connecting || _phase == _Phase.live || _phase == _Phase.capturing) {
        _fail(widget.live.connected
            ? 'No picture from the vehicle unit. Check that it is online and try again.'
            : 'Lost connection to the server. Check the network and try again.');
      }
    });
  }

  void _onUpdate(EnrollmentUpdate u) {
    if (!mounted || _phase == _Phase.success || _phase == _Phase.failed) return;
    if (!u.done) {
      _armWatchdog();
      setState(() {
        _last = u;
        if (u.preview != null && u.preview!.isNotEmpty) _view = base64Decode(u.preview!);
        if (_phase == _Phase.connecting) _phase = _Phase.live;
      });
      return;
    }
    _watchdog?.cancel();
    if (u.ok) {
      setState(() {
        _phase = _Phase.success;
        if (u.photo != null && u.photo!.isNotEmpty) _photo = base64Decode(u.photo!);
      });
    } else {
      _fail(u.error ?? 'Enrollment failed. Try again.');
    }
  }

  void _fail(String msg) {
    _watchdog?.cancel();
    if (!mounted) return;
    setState(() {
      _phase = _Phase.failed;
      _error = msg;
    });
  }

  void _close(bool enrolled) {
    if (_phase == _Phase.connecting || _phase == _Phase.live || _phase == _Phase.capturing) {
      _send('cancel'); // stop the unit streaming
    }
    Navigator.pop(context, enrolled);
  }

  @override
  void dispose() {
    _sub?.cancel();
    _watchdog?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text('Enroll ${widget.driver.displayName}'),
      content: SizedBox(
        width: 380,
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          _picture(),
          const SizedBox(height: 12),
          _status(context),
        ]),
      ),
      actions: [
        if (_phase == _Phase.success)
          FilledButton(onPressed: () => _close(true), child: const Text('Done'))
        else ...[
          TextButton(onPressed: () => _close(false), child: const Text('Cancel')),
          if (_phase == _Phase.failed)
            FilledButton(onPressed: () => _send('preview'), child: const Text('Try again'))
          else
            FilledButton.icon(
              onPressed: _phase == _Phase.live && _faceVisible ? () => _send('capture') : null,
              icon: const Icon(Icons.camera_alt),
              label: Text(_phase == _Phase.capturing ? 'Capturing…' : 'Capture'),
            ),
        ],
      ],
    );
  }

  Widget _picture() {
    final Widget child;
    if (_phase == _Phase.success && _photo != null) {
      child = Image.memory(_photo!, fit: BoxFit.contain);
    } else if (_view != null && _phase != _Phase.success) {
      child = Image.memory(_view!, fit: BoxFit.cover, gaplessPlayback: true);
    } else if (_phase == _Phase.failed) {
      child = const Icon(Icons.videocam_off, color: Colors.white54, size: 64);
    } else if (_phase == _Phase.success) {
      child = const Icon(Icons.check_circle, color: safeColor, size: 72);
    } else {
      child = const Column(mainAxisSize: MainAxisSize.min, children: [
        CircularProgressIndicator(),
        SizedBox(height: 12),
        Text('Connecting to the camera…', style: TextStyle(color: Colors.white70)),
      ]);
    }
    return AspectRatio(
      aspectRatio: 4 / 3,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(8),
        child: Container(color: Colors.black, alignment: Alignment.center, child: child),
      ),
    );
  }

  Widget _status(BuildContext context) {
    switch (_phase) {
      case _Phase.connecting:
        return const Text('Starting the vehicle unit\'s camera…');
      case _Phase.live:
        return _faceVisible
            ? _banner(Icons.face, safeColor, 'Person detected. Ask them to look at the camera, then press Capture.')
            : _banner(Icons.person_off, warningColor,
                'No person detected in the camera. Sit in the driver\'s seat facing the camera.');
      case _Phase.capturing:
        final u = _last;
        return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          LinearProgressIndicator(value: u == null || u.needed == 0 || !u.capturing ? null : u.samples / u.needed),
          const SizedBox(height: 8),
          _faceVisible || u == null
              ? _banner(Icons.camera_alt, null, 'Capturing… hold still and look at the camera.')
              : _banner(Icons.person_off, warningColor, 'No person detected in the camera. Stay in view.'),
        ]);
      case _Phase.success:
        return _banner(Icons.check_circle, safeColor,
            '${widget.driver.displayName}\'s photo and face are registered. The unit will now recognise them.');
      case _Phase.failed:
        return _banner(Icons.error_outline, criticalColor, _error ?? 'Enrollment failed.');
    }
  }

  Widget _banner(IconData icon, Color? color, String text) => Container(
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(
          color: (color ?? Colors.blueGrey).withValues(alpha: 0.12),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Row(children: [
          Icon(icon, color: color),
          const SizedBox(width: 10),
          Expanded(child: Text(text)),
        ]),
      );
}

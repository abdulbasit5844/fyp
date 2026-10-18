import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../models.dart';
import '../state/live_state.dart';
import '../theme.dart';
import 'live_screen.dart';

/// Shows an alert as a small popup (M5/M6): red for critical, amber for
/// warnings, a countdown to escalation and an Acknowledge button. When the
/// driver recovers, the popup turns green ("Back to safe") and closes itself.
Future<void> showAlertPopup(BuildContext context, SafetyEvent event) => showDialog<void>(
      context: context,
      barrierDismissible: true,
      builder: (_) => event.type == 'unverified_driver' ? UnknownPersonPopup(event: event) : AlertPopup(event: event),
    );

/// Someone the vehicle unit does not recognise is in the driver's seat: their
/// photo, whether the owner's WhatsApp alert went out, and the live camera.
class UnknownPersonPopup extends StatelessWidget {
  const UnknownPersonPopup({super.key, required this.event});
  final SafetyEvent event;

  @override
  Widget build(BuildContext context) {
    final live = context.watch<LiveState>();
    final whatsapp = live.deliveries[event.id]?.where((n) => n.channel == 'whatsapp').firstOrNull;
    final (IconData icon, Color color, String text) = switch (whatsapp?.status) {
      'sent' => (Icons.check_circle, safeColor, 'Owner alerted on WhatsApp with this photo'),
      'failed' => (Icons.error, criticalColor, 'WhatsApp not sent: ${whatsapp!.error ?? 'unknown error'}'),
      _ => (Icons.schedule, warningColor, 'Alerting the owner on WhatsApp…'),
    };
    final photo = event.photo;

    return Dialog(
      clipBehavior: Clip.antiAlias,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 380),
        child: SingleChildScrollView(
          child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            Container(
              color: criticalColor,
              padding: const EdgeInsets.fromLTRB(16, 12, 4, 12),
              child: Row(children: [
                const Icon(Icons.person_off, color: Colors.white, size: 32),
                const SizedBox(width: 12),
                Expanded(
                  child: Text('Unknown person detected',
                      style: Theme.of(context)
                          .textTheme
                          .titleLarge
                          ?.copyWith(color: Colors.white, fontWeight: FontWeight.bold)),
                ),
                IconButton(
                  icon: const Icon(Icons.close, color: Colors.white),
                  onPressed: () => Navigator.of(context).pop(),
                ),
              ]),
            ),
            if (photo != null)
              Image.memory(base64Decode(photo), height: 240, fit: BoxFit.cover, gaplessPlayback: true),
            Padding(
              padding: const EdgeInsets.all(16),
              child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                Text(event.description ?? "Someone who is not a registered driver is in the driver's seat.",
                    style: Theme.of(context).textTheme.bodyLarge),
                const SizedBox(height: 4),
                Text(DateFormat('HH:mm:ss, d MMM').format(event.detectedAt),
                    style: Theme.of(context).textTheme.bodySmall),
                const SizedBox(height: 12),
                Row(children: [
                  Icon(icon, color: color, size: 20),
                  const SizedBox(width: 8),
                  Expanded(child: Text(text)),
                ]),
                const SizedBox(height: 8),
                const Text('Driver monitoring is paused until a registered driver is recognised.',
                    style: TextStyle(fontSize: 12)),
                const SizedBox(height: 16),
                FilledButton.icon(
                  onPressed: () {
                    final nav = Navigator.of(context);
                    nav.pop();
                    nav.push(MaterialPageRoute(builder: (_) => const LiveScreen()));
                  },
                  style: FilledButton.styleFrom(backgroundColor: criticalColor, foregroundColor: Colors.white),
                  icon: const Icon(Icons.videocam),
                  label: const Text('Watch live camera'),
                ),
                const SizedBox(height: 8),
                OutlinedButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Close')),
              ]),
            ),
          ]),
        ),
      ),
    );
  }
}

class AlertPopup extends StatefulWidget {
  const AlertPopup({super.key, required this.event});
  final SafetyEvent event;

  @override
  State<AlertPopup> createState() => _AlertPopupState();
}

class _AlertPopupState extends State<AlertPopup> {
  late Timer _tick;
  Timer? _autoClose;
  bool _busy = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _tick = Timer.periodic(const Duration(milliseconds: 250), (_) => setState(() {}));
  }

  @override
  void dispose() {
    _tick.cancel();
    _autoClose?.cancel();
    super.dispose();
  }

  void _close() {
    if (mounted && Navigator.of(context).canPop()) Navigator.of(context).pop();
  }

  Future<void> _acknowledge() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final e = await context.read<LiveState>().acknowledge(widget.event.id);
      if (!mounted) return;
      if (e.status == 'escalated') {
        setState(() => _error = 'Too late: emergency contacts were already notified.');
      } else {
        _close();
      }
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final live = context.watch<LiveState>();
    final event = widget.event;
    final stillActive = live.activeAlerts.any((a) => a.id == event.id);
    final escalated = event.status == 'escalated' || live.escalatedIds.contains(event.id);
    final backToSafe = !stillActive && !escalated;

    if (backToSafe) _autoClose ??= Timer(const Duration(seconds: 3), _close);

    final color = backToSafe ? safeColor : (escalated ? criticalColor : severityColor(event.severity));
    final onColor = backToSafe || event.isCritical || escalated ? Colors.white : Colors.black;

    final deadline = event.detectedAt.add(Duration(seconds: live.ackWindowSec));
    final remaining = deadline.difference(DateTime.now());
    final secondsLeft = remaining.isNegative ? 0 : remaining.inMilliseconds / 1000;

    final title = backToSafe ? 'Back to safe' : (escalated ? 'Emergency contacts notified' : event.title);
    final detail = backToSafe
        ? 'The driver is back to normal.'
        : event.description ?? (event.isCritical ? 'Critical safety alert' : 'Safety warning');

    return Dialog(
      clipBehavior: Clip.antiAlias,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 380),
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          // Coloured header
          AnimatedContainer(
            duration: const Duration(milliseconds: 300),
            color: color,
            padding: const EdgeInsets.fromLTRB(16, 12, 4, 12),
            child: Row(children: [
              Icon(backToSafe ? Icons.check_circle : (escalated ? Icons.sos : eventIcon(event.type)),
                  color: onColor, size: 32),
              const SizedBox(width: 12),
              Expanded(
                child: Text(title,
                    style: Theme.of(context)
                        .textTheme
                        .titleLarge
                        ?.copyWith(color: onColor, fontWeight: FontWeight.bold)),
              ),
              IconButton(
                icon: Icon(Icons.close, color: onColor),
                tooltip: stillActive ? 'Hide (the alert stays active)' : 'Close',
                onPressed: _close,
              ),
            ]),
          ),
          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              Text(detail, style: Theme.of(context).textTheme.bodyLarge),
              const SizedBox(height: 4),
              Text(DateFormat('HH:mm:ss, d MMM').format(event.detectedAt),
                  style: Theme.of(context).textTheme.bodySmall),
              if (event.lat != null && !backToSafe)
                Align(
                  alignment: Alignment.centerLeft,
                  child: TextButton.icon(
                    onPressed: () => launchUrl(Uri.parse('https://maps.google.com/?q=${event.lat},${event.lng}')),
                    icon: const Icon(Icons.place, size: 18),
                    label: Text('${event.lat!.toStringAsFixed(5)}, ${event.lng!.toStringAsFixed(5)}'),
                  ),
                ),
              if (event.isCritical && stillActive) ...[
                const SizedBox(height: 12),
                Text(
                  secondsLeft > 0
                      ? 'Emergency contacts will be alerted in ${secondsLeft.ceil()} s'
                      : 'Alerting emergency contacts…',
                ),
                const SizedBox(height: 6),
                LinearProgressIndicator(
                  value: (secondsLeft / live.ackWindowSec).clamp(0, 1).toDouble(),
                  color: criticalColor,
                  minHeight: 6,
                ),
              ],
              if (_error != null) ...[
                const SizedBox(height: 8),
                Text(_error!, style: const TextStyle(color: criticalColor, fontWeight: FontWeight.bold)),
              ],
              const SizedBox(height: 16),
              if (stillActive)
                FilledButton.icon(
                  onPressed: _busy ? null : _acknowledge,
                  style: FilledButton.styleFrom(backgroundColor: color, foregroundColor: onColor),
                  icon: const Icon(Icons.check_circle),
                  label: Text(_busy ? 'Sending…' : "I'm OK — Acknowledge"),
                )
              else
                OutlinedButton(onPressed: _close, child: const Text('Close')),
            ]),
          ),
        ]),
      ),
    );
  }
}

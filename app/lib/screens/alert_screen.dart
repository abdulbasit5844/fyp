import 'dart:async';

import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../models.dart';
import '../state/live_state.dart';
import '../theme.dart';

/// Full-screen alert (M5/M6): red for critical, amber for warnings, a countdown
/// to escalation and a one-tap Acknowledge button.
class AlertScreen extends StatefulWidget {
  const AlertScreen({super.key, required this.event});
  final SafetyEvent event;

  @override
  State<AlertScreen> createState() => _AlertScreenState();
}

class _AlertScreenState extends State<AlertScreen> {
  late Timer _tick;
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
    super.dispose();
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
        Navigator.of(context).pop();
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
    final acknowledgedElsewhere = !stillActive && !escalated && event.isActive;

    final color = escalated ? criticalColor : severityColor(event.severity);
    final onColor = event.isCritical || escalated ? Colors.white : Colors.black;

    final deadline = event.detectedAt.add(Duration(seconds: live.ackWindowSec));
    final remaining = deadline.difference(DateTime.now());
    final secondsLeft = remaining.isNegative ? 0 : remaining.inMilliseconds / 1000;

    return Scaffold(
      backgroundColor: color,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Align(
                alignment: Alignment.topRight,
                child: IconButton(
                  icon: Icon(Icons.close, color: onColor),
                  tooltip: 'Hide (the alert stays active)',
                  onPressed: () => Navigator.of(context).pop(),
                ),
              ),
              const Spacer(),
              Icon(escalated ? Icons.sos : eventIcon(event.type), size: 120, color: onColor),
              const SizedBox(height: 16),
              Text(
                escalated ? 'Emergency contacts notified' : event.title,
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.headlineLarge?.copyWith(color: onColor, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 12),
              Text(
                event.description ?? (event.isCritical ? 'Critical safety alert' : 'Safety warning'),
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.titleMedium?.copyWith(color: onColor),
              ),
              const SizedBox(height: 8),
              Text(DateFormat('HH:mm:ss, d MMM').format(event.detectedAt),
                  textAlign: TextAlign.center, style: TextStyle(color: onColor)),
              if (event.lat != null) ...[
                const SizedBox(height: 8),
                TextButton.icon(
                  onPressed: () => launchUrl(Uri.parse('https://maps.google.com/?q=${event.lat},${event.lng}')),
                  icon: Icon(Icons.place, color: onColor),
                  label: Text('${event.lat!.toStringAsFixed(5)}, ${event.lng!.toStringAsFixed(5)}',
                      style: TextStyle(color: onColor)),
                ),
              ],
              const Spacer(),
              if (event.isCritical && stillActive) ...[
                Text(
                  secondsLeft > 0
                      ? 'Emergency contacts will be alerted in ${secondsLeft.ceil()} s'
                      : 'Alerting emergency contacts…',
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(color: onColor),
                ),
                const SizedBox(height: 8),
                LinearProgressIndicator(
                  value: (secondsLeft / live.ackWindowSec).clamp(0, 1).toDouble(),
                  color: onColor,
                  backgroundColor: onColor.withValues(alpha: 0.3),
                  minHeight: 8,
                ),
                const SizedBox(height: 24),
              ],
              if (_error != null)
                Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Text(_error!, textAlign: TextAlign.center,
                      style: TextStyle(color: onColor, fontWeight: FontWeight.bold)),
                ),
              if (stillActive)
                FilledButton.icon(
                  onPressed: _busy ? null : _acknowledge,
                  style: FilledButton.styleFrom(
                    backgroundColor: onColor,
                    foregroundColor: color,
                    minimumSize: const Size.fromHeight(72),
                    textStyle: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
                  ),
                  icon: const Icon(Icons.check_circle, size: 32),
                  label: Text(_busy ? 'Sending…' : "I'm OK — Acknowledge"),
                )
              else
                OutlinedButton(
                  onPressed: () => Navigator.of(context).pop(),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: onColor,
                    side: BorderSide(color: onColor),
                    minimumSize: const Size.fromHeight(56),
                  ),
                  child: Text(acknowledgedElsewhere ? 'Alert acknowledged — close' : 'Close'),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

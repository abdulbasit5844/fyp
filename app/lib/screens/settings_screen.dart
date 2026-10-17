import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api/api_client.dart';
import '../models.dart';
import '../state/auth_state.dart';
import 'contacts_screen.dart';

/// Monitoring settings (FR7.3). Saved values reach the vehicle unit over MQTT
/// within a second. Only the owner can change them (FR5.4).
class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  MonitorSettings? _s;
  bool _dirty = false, _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final json = await context.read<ApiClient>().get('/config');
      setState(() {
        _s = MonitorSettings.fromJson(json);
        _dirty = false;
      });
    } catch (e) {
      setState(() => _error = e.toString());
    }
  }

  Future<void> _save() async {
    setState(() => _saving = true);
    try {
      final json = await context.read<ApiClient>().patch('/config', _s!.toJson());
      setState(() {
        _s = MonitorSettings.fromJson(json);
        _dirty = false;
      });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Settings sent to the vehicle unit')));
      }
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  void _set(VoidCallback f) => setState(() {
        f();
        _dirty = true;
      });

  @override
  Widget build(BuildContext context) {
    final owner = context.read<AuthState>().user?.isOwner ?? false;
    final s = _s;

    return PopScope(
      canPop: !_dirty,
      onPopInvokedWithResult: (didPop, _) async {
        if (didPop) return;
        final leave = await showDialog<bool>(
          context: context,
          builder: (c) => AlertDialog(
            title: const Text('Discard changes?'),
            actions: [
              TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('Keep editing')),
              TextButton(onPressed: () => Navigator.pop(c, true), child: const Text('Discard')),
            ],
          ),
        );
        if (leave == true && context.mounted) {
          setState(() => _dirty = false);
          Navigator.of(context).pop();
        }
      },
      child: Scaffold(
        appBar: AppBar(title: const Text('Settings')),
        floatingActionButton: owner && _dirty
            ? FloatingActionButton.extended(
                onPressed: _saving ? null : _save,
                icon: const Icon(Icons.save),
                label: Text(_saving ? 'Saving…' : 'Save'),
              )
            : null,
        body: s == null
            ? Center(child: _error == null ? const CircularProgressIndicator() : Text(_error!))
            : AbsorbPointer(
                absorbing: !owner,
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(16, 8, 16, 96),
                  children: [
                    if (!owner)
                      const Card(
                        child: ListTile(
                          leading: Icon(Icons.lock),
                          title: Text('Only the vehicle owner can change these settings.'),
                        ),
                      ),
                    const _Header('Drowsiness'),
                    _SliderTile(
                      title: 'Eye closure threshold (EAR)',
                      help: 'Lower = eyes must be more closed before counting as drowsy.',
                      value: s.earThreshold, min: 0.20, max: 0.30, divisions: 10,
                      label: s.earThreshold.toStringAsFixed(2),
                      onChanged: (v) => _set(() => s.earThreshold = v),
                    ),
                    _SliderTile(
                      title: 'Eyes closed for',
                      value: s.earSustainSec, min: 1, max: 5, divisions: 8,
                      label: '${s.earSustainSec.toStringAsFixed(1)} s',
                      onChanged: (v) => _set(() => s.earSustainSec = v),
                    ),
                    const _Header('Attention'),
                    _SliderTile(
                      title: 'Head turn limit',
                      value: s.headPoseThresholdDeg, min: 15, max: 45, divisions: 6,
                      label: '${s.headPoseThresholdDeg.round()}°',
                      onChanged: (v) => _set(() => s.headPoseThresholdDeg = v),
                    ),
                    _SliderTile(
                      title: 'Looking away for',
                      value: s.headPoseSustainSec, min: 1, max: 5, divisions: 8,
                      label: '${s.headPoseSustainSec.toStringAsFixed(1)} s',
                      onChanged: (v) => _set(() => s.headPoseSustainSec = v),
                    ),
                    _SliderTile(
                      title: 'Distress (anger / fear) for',
                      value: s.emotionSustainSec, min: 1, max: 10, divisions: 9,
                      label: '${s.emotionSustainSec.round()} s',
                      onChanged: (v) => _set(() => s.emotionSustainSec = v),
                    ),
                    const _Header('Alerts and escalation'),
                    _SliderTile(
                      title: 'Acknowledgment window',
                      help: 'Time to respond before emergency contacts get your location.',
                      value: s.ackWindowSec, min: 5, max: 30, divisions: 25,
                      label: '${s.ackWindowSec.round()} s',
                      onChanged: (v) => _set(() => s.ackWindowSec = v),
                    ),
                    _SliderTile(
                      title: 'Alert sensitivity',
                      help: 'Higher reacts sooner but may give more false alarms.',
                      value: s.alertSensitivity, min: 1, max: 5, divisions: 4,
                      label: const ['Very low', 'Low', 'Normal', 'High', 'Very high'][s.alertSensitivity.round() - 1],
                      onChanged: (v) => _set(() => s.alertSensitivity = v),
                    ),
                    SwitchListTile(
                      title: const Text('Buzzer sound'),
                      value: s.sound,
                      onChanged: (v) => _set(() => s.sound = v),
                    ),
                    SwitchListTile(
                      title: const Text('Push notifications'),
                      value: s.push,
                      onChanged: (v) => _set(() => s.push = v),
                    ),
                    SwitchListTile(
                      title: const Text('SMS fallback'),
                      subtitle: const Text('Text contacts who do not have the app'),
                      value: s.smsFallback,
                      onChanged: (v) => _set(() => s.smsFallback = v),
                    ),
                    SwitchListTile(
                      title: const Text('Record event video'),
                      subtitle: const Text('30 s clip around each safety event'),
                      value: s.videoRecordingEnabled,
                      onChanged: (v) => _set(() => s.videoRecordingEnabled = v),
                    ),
                    const Divider(),
                    ListTile(
                      leading: const Icon(Icons.contact_emergency),
                      title: const Text('Emergency contacts'),
                      trailing: const Icon(Icons.chevron_right),
                      onTap: () =>
                          Navigator.of(context).push(MaterialPageRoute(builder: (_) => const ContactsScreen())),
                    ),
                  ],
                ),
              ),
      ),
    );
  }
}

class _Header extends StatelessWidget {
  const _Header(this.text);
  final String text;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(16, 20, 16, 4),
        child: Text(text,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(color: Theme.of(context).colorScheme.primary)),
      );
}

class _SliderTile extends StatelessWidget {
  const _SliderTile({
    required this.title,
    required this.value,
    required this.min,
    required this.max,
    required this.divisions,
    required this.label,
    required this.onChanged,
    this.help,
  });

  final String title, label;
  final String? help;
  final double value, min, max;
  final int divisions;
  final ValueChanged<double> onChanged;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      title: Row(children: [
        Expanded(child: Text(title)),
        Text(label, style: const TextStyle(fontWeight: FontWeight.bold)),
      ]),
      subtitle: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (help != null) Text(help!),
          Slider(
            value: value.clamp(min, max),
            min: min,
            max: max,
            divisions: divisions,
            label: label,
            onChanged: onChanged,
          ),
        ],
      ),
    );
  }
}

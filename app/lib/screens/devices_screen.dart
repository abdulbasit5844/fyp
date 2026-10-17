import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../api/api_client.dart';
import '../models.dart';
import '../state/auth_state.dart';
import '../state/live_state.dart';
import '../theme.dart';
import 'enroll_dialog.dart';

/// Pair the Raspberry Pi with this account and manage the drivers whose faces
/// it should recognise.
class DevicesScreen extends StatefulWidget {
  const DevicesScreen({super.key});

  @override
  State<DevicesScreen> createState() => _DevicesScreenState();
}

class _DevicesScreenState extends State<DevicesScreen> {
  List<DriverProfile> _drivers = [];
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadDrivers();
  }

  ApiClient get _api => context.read<ApiClient>();

  Future<void> _loadDrivers() async {
    try {
      final list = await _api.get('/drivers') as List;
      setState(() => _drivers = list.map((j) => DriverProfile.fromJson(j)).toList());
    } catch (e) {
      setState(() => _error = e.toString());
    }
  }

  void _snack(String msg) => ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));

  Future<void> _pair() async {
    List discovered = [];
    try {
      discovered = await _api.get('/devices/discover') as List;
    } catch (_) {}
    if (!mounted) return;
    final idCtl = TextEditingController(text: discovered.isNotEmpty ? discovered.first['deviceId'] : '');
    final nameCtl = TextEditingController(text: 'My Vehicle');
    final ok = await showDialog<bool>(
      context: context,
      builder: (d) => AlertDialog(
        title: const Text('Pair vehicle unit'),
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          Text(discovered.isEmpty
              ? 'No unpaired unit found yet. Make sure the monitoring service is running on the Pi, or type its device ID.'
              : 'Found: ${discovered.map((d) => d['deviceId']).join(', ')}'),
          TextField(controller: idCtl, decoration: const InputDecoration(labelText: 'Device ID')),
          TextField(controller: nameCtl, decoration: const InputDecoration(labelText: 'Vehicle name')),
        ]),
        actions: [
          TextButton(onPressed: () => Navigator.pop(d, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(d, true), child: const Text('Pair')),
        ],
      ),
    );
    if (ok != true) return;
    try {
      await _api.post('/devices', {'deviceId': idCtl.text.trim(), 'name': nameCtl.text.trim()});
      if (mounted) await context.read<LiveState>().refresh();
      _snack('Vehicle unit paired');
    } catch (e) {
      _snack(e.toString());
    }
  }

  Future<void> _addDriver() async {
    final ctl = TextEditingController();
    final name = await showDialog<String>(
      context: context,
      builder: (d) => AlertDialog(
        title: const Text('Add driver'),
        content: TextField(controller: ctl, autofocus: true, decoration: const InputDecoration(labelText: 'Name')),
        actions: [
          TextButton(onPressed: () => Navigator.pop(d), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(d, ctl.text.trim()), child: const Text('Add')),
        ],
      ),
    );
    if (name == null || name.isEmpty) return;
    try {
      await _api.post('/drivers', {'displayName': name, 'isPrimary': _drivers.isEmpty});
      _loadDrivers();
    } catch (e) {
      _snack(e.toString());
    }
  }

  Future<void> _enroll(DriverProfile d) async {
    final live = context.read<LiveState>();
    if (live.device == null) {
      _snack('Pair a vehicle unit first');
      return;
    }
    await showEnrollDialog(context, _api, live, d);
    if (mounted) _loadDrivers();
  }

  Future<void> _toggleAuthorized(DriverProfile d) async {
    try {
      await _api.patch('/drivers/${d.id}', {'isAuthorized': !d.isAuthorized});
      _loadDrivers();
    } catch (e) {
      _snack(e.toString());
    }
  }

  Future<void> _deleteDriver(DriverProfile d) async {
    try {
      await _api.delete('/drivers/${d.id}');
      _loadDrivers();
    } catch (e) {
      _snack(e.toString());
    }
  }

  @override
  Widget build(BuildContext context) {
    final live = context.watch<LiveState>();
    final owner = context.read<AuthState>().user?.isOwner ?? false;

    return Scaffold(
      appBar: AppBar(title: const Text('Devices & drivers')),
      body: RefreshIndicator(
        onRefresh: () async {
          await live.refresh();
          await _loadDrivers();
        },
        child: ListView(
          padding: const EdgeInsets.all(12),
          children: [
            Text('Vehicle units', style: Theme.of(context).textTheme.titleMedium),
            for (final d in live.devices)
              Card(
                child: ListTile(
                  leading: Icon(Icons.memory, color: d.online ? safeColor : Colors.grey),
                  title: Text(d.name),
                  subtitle: Text('${d.deviceId} • ${d.online ? 'online' : 'offline'}'
                      '${d.lastSeenAt != null ? ' • seen ${DateFormat('d MMM HH:mm').format(d.lastSeenAt!)}' : ''}'),
                ),
              ),
            if (live.devices.isEmpty) const ListTile(title: Text('No vehicle unit paired')),
            if (owner)
              Align(
                alignment: Alignment.centerLeft,
                child: TextButton.icon(onPressed: _pair, icon: const Icon(Icons.link), label: const Text('Pair a unit')),
              ),
            const Divider(height: 32),
            Text('Drivers', style: Theme.of(context).textTheme.titleMedium),
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 4),
              child: Text('The unit checks the driver\'s face before monitoring. Enroll each driver while they sit '
                  'in front of the camera.'),
            ),
            if (_error != null) Text(_error!),
            for (final d in _drivers)
              Card(
                child: ListTile(
                  leading: CircleAvatar(
                    radius: 24,
                    backgroundImage: d.photo != null ? MemoryImage(base64Decode(d.photo!)) : null,
                    child: d.photo == null ? const Icon(Icons.person) : null,
                  ),
                  title: Text('${d.displayName}${d.isPrimary ? ' (primary)' : ''}'),
                  subtitle: Row(children: [
                    Icon(d.isAuthorized ? Icons.verified_user : Icons.block,
                        size: 16, color: d.isAuthorized ? safeColor : criticalColor),
                    const SizedBox(width: 4),
                    Flexible(
                      child: Text('${d.isAuthorized ? 'Allowed' : 'Blocked'} • '
                          '${d.enrolled ? 'Face enrolled' : 'Face not enrolled yet'}'),
                    ),
                  ]),
                  onTap: owner && !d.enrolled ? () => _enroll(d) : null,
                  trailing: owner
                      ? PopupMenuButton<String>(
                          onSelected: (v) => switch (v) {
                            'enroll' => _enroll(d),
                            'auth' => _toggleAuthorized(d),
                            _ => _deleteDriver(d),
                          },
                          itemBuilder: (_) => [
                            PopupMenuItem(value: 'enroll', child: Text(d.enrolled ? 'Re-enroll face' : 'Enroll face')),
                            PopupMenuItem(value: 'auth', child: Text(d.isAuthorized ? 'Block this driver' : 'Allow this driver')),
                            const PopupMenuItem(value: 'delete', child: Text('Remove')),
                          ],
                        )
                      : null,
                ),
              ),
            if (owner)
              Align(
                alignment: Alignment.centerLeft,
                child: TextButton.icon(
                    onPressed: _addDriver, icon: const Icon(Icons.person_add), label: const Text('Add driver')),
              ),
          ],
        ),
      ),
    );
  }
}

import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../models.dart';
import '../state/auth_state.dart';
import '../state/live_state.dart';
import '../theme.dart';
import 'alert_screen.dart';
import 'contacts_screen.dart';
import 'devices_screen.dart';
import 'events_screen.dart';
import 'settings_screen.dart';

/// Home dashboard: live driver status, active alert banner, last event and
/// navigation to logs, contacts and settings.
class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final live = context.watch<LiveState>();
    final auth = context.read<AuthState>();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Driver Safety'),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 4),
            child: Tooltip(
              message: live.connected ? 'Live connection to the vehicle unit' : 'Reconnecting…',
              child: Icon(live.connected ? Icons.cloud_done : Icons.cloud_off,
                  color: live.connected ? safeColor : Theme.of(context).colorScheme.error),
            ),
          ),
          PopupMenuButton<String>(
            onSelected: (v) {
              if (v == 'logout') auth.logout();
            },
            itemBuilder: (_) => [
              PopupMenuItem(enabled: false, child: Text('${auth.user?.name} (${auth.user?.role})')),
              const PopupMenuItem(value: 'logout', child: Text('Sign out')),
            ],
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: live.refresh,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            for (final a in live.activeAlerts) _AlertBanner(event: a),
            _StatusCard(live: live),
            const SizedBox(height: 12),
            _LastEventCard(event: live.lastEvent),
            const SizedBox(height: 12),
            _NavGrid(isOwner: auth.user?.isOwner ?? false),
          ],
        ),
      ),
    );
  }
}

class _StatusCard extends StatelessWidget {
  const _StatusCard({required this.live});
  final LiveState live;

  @override
  Widget build(BuildContext context) {
    final device = live.device;
    final state = live.state;
    final color = stateColor(state);
    final label = switch (state) {
      DriverState.safe => 'SAFE',
      DriverState.warning => 'WARNING',
      DriverState.critical => 'CRITICAL',
    };
    final icon = switch (state) {
      DriverState.safe => Icons.verified_user,
      DriverState.warning => Icons.warning_amber_rounded,
      DriverState.critical => Icons.crisis_alert,
    };

    String subtitle;
    if (device == null) {
      subtitle = 'No vehicle unit paired yet. Open Devices to pair your Raspberry Pi.';
    } else if (!device.online) {
      final seen = device.lastSeenAt == null ? 'never' : DateFormat('d MMM, HH:mm').format(device.lastSeenAt!);
      subtitle = '${device.name} is offline (last seen $seen)';
    } else if (!device.monitoring) {
      subtitle = '${device.name} is online, waiting for the driver';
    } else {
      subtitle = '${device.name} • monitoring ${device.activeDriverName ?? 'unknown driver'}';
    }

    return Card(
      color: color.withValues(alpha: 0.12),
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          children: [
            Icon(icon, size: 72, color: color),
            const SizedBox(height: 8),
            Text(label,
                style: Theme.of(context).textTheme.displaySmall?.copyWith(color: color, fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            Text(subtitle, textAlign: TextAlign.center),
          ],
        ),
      ),
    );
  }
}

class _AlertBanner extends StatelessWidget {
  const _AlertBanner({required this.event});
  final SafetyEvent event;

  @override
  Widget build(BuildContext context) {
    final color = severityColor(event.severity);
    return Card(
      color: color,
      margin: const EdgeInsets.only(bottom: 12),
      child: ListTile(
        leading: Icon(eventIcon(event.type), color: Colors.white, size: 32),
        title: Text(event.title, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
        subtitle: Text('Tap to acknowledge • ${DateFormat.Hms().format(event.detectedAt)}',
            style: const TextStyle(color: Colors.white)),
        trailing: const Icon(Icons.chevron_right, color: Colors.white),
        onTap: () => Navigator.of(context).push(MaterialPageRoute(
          fullscreenDialog: true,
          builder: (_) => AlertScreen(event: event),
        )),
      ),
    );
  }
}

class _LastEventCard extends StatelessWidget {
  const _LastEventCard({this.event});
  final SafetyEvent? event;

  @override
  Widget build(BuildContext context) {
    final e = event;
    return Card(
      child: ListTile(
        leading: Icon(e == null ? Icons.event_available : eventIcon(e.type),
            color: e == null ? null : severityColor(e.severity)),
        title: Text(e == null ? 'No safety events yet' : 'Last event: ${e.title}'),
        subtitle: e == null
            ? null
            : Text('${DateFormat('d MMM, HH:mm:ss').format(e.detectedAt)} • ${e.actionTaken}'),
      ),
    );
  }
}

class _NavGrid extends StatelessWidget {
  const _NavGrid({required this.isOwner});
  final bool isOwner;

  @override
  Widget build(BuildContext context) {
    final items = <(IconData, String, Widget Function())>[
      (Icons.history, 'Event logs', () => const EventsScreen()),
      (Icons.contact_emergency, 'Emergency contacts', () => const ContactsScreen()),
      (Icons.tune, 'Settings', () => const SettingsScreen()),
      (Icons.memory, 'Devices & drivers', () => const DevicesScreen()),
    ];
    return GridView.count(
      crossAxisCount: MediaQuery.sizeOf(context).width > 700 ? 4 : 2,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      mainAxisSpacing: 12,
      crossAxisSpacing: 12,
      childAspectRatio: 1.5,
      children: [
        for (final (icon, label, page) in items)
          Card(
            clipBehavior: Clip.antiAlias,
            child: InkWell(
              onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => page())),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(icon, size: 36, color: Theme.of(context).colorScheme.primary),
                  const SizedBox(height: 8),
                  Text(label, textAlign: TextAlign.center),
                ],
              ),
            ),
          ),
      ],
    );
  }
}

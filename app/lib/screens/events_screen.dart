import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../api/api_client.dart';
import '../models.dart';
import '../theme.dart';
import 'video_screen.dart';

/// Paginated event log, newest first (FR7.1), with type/severity filters and
/// tap-to-expand details including the recorded clip.
class EventsScreen extends StatefulWidget {
  const EventsScreen({super.key});

  @override
  State<EventsScreen> createState() => _EventsScreenState();
}

class _EventsScreenState extends State<EventsScreen> {
  final _items = <SafetyEvent>[];
  final _scroll = ScrollController();
  int _page = 0, _pages = 1, _total = 0;
  bool _loading = false;
  String? _error, _type, _severity;

  @override
  void initState() {
    super.initState();
    _scroll.addListener(() {
      if (_scroll.position.extentAfter < 300) _loadMore();
    });
    _reload();
  }

  Future<void> _reload() async {
    _items.clear();
    _page = 0;
    _pages = 1;
    await _loadMore();
  }

  Future<void> _loadMore() async {
    if (_loading || _page >= _pages) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final res = await context.read<ApiClient>().get('/events', query: {
        'page': _page + 1,
        'limit': 20,
        if (_type != null) 'type': _type,
        if (_severity != null) 'severity': _severity,
      });
      setState(() {
        _items.addAll((res['items'] as List).map((j) => SafetyEvent.fromJson(j)));
        _page = res['page'];
        _pages = res['pages'];
        _total = res['total'];
      });
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Event logs${_total > 0 ? ' ($_total)' : ''}')),
      body: Column(
        children: [
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            child: Row(children: [
              for (final s in ['critical', 'warning'])
                Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: FilterChip(
                    label: Text(s[0].toUpperCase() + s.substring(1)),
                    selected: _severity == s,
                    onSelected: (v) {
                      _severity = v ? s : null;
                      _reload();
                    },
                  ),
                ),
              for (final t in eventTitles.keys.take(4))
                Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: FilterChip(
                    avatar: Icon(eventIcon(t), size: 18),
                    label: Text(eventTitles[t]!),
                    selected: _type == t,
                    onSelected: (v) {
                      _type = v ? t : null;
                      _reload();
                    },
                  ),
                ),
            ]),
          ),
          Expanded(
            child: RefreshIndicator(
              onRefresh: _reload,
              child: _items.isEmpty && !_loading
                  ? ListView(children: [
                      const SizedBox(height: 120),
                      Icon(_error == null ? Icons.event_available : Icons.error_outline, size: 56),
                      const SizedBox(height: 12),
                      Text(_error ?? 'No events recorded', textAlign: TextAlign.center),
                    ])
                  : ListView.builder(
                      controller: _scroll,
                      itemCount: _items.length + (_page < _pages ? 1 : 0),
                      itemBuilder: (context, i) => i == _items.length
                          ? const Padding(
                              padding: EdgeInsets.all(24),
                              child: Center(child: CircularProgressIndicator()),
                            )
                          : _EventTile(event: _items[i]),
                    ),
            ),
          ),
        ],
      ),
    );
  }

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }
}

class _EventTile extends StatelessWidget {
  const _EventTile({required this.event});
  final SafetyEvent event;

  @override
  Widget build(BuildContext context) {
    final color = severityColor(event.severity);
    final e = event;
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      clipBehavior: Clip.antiAlias,
      child: ExpansionTile(
        leading: CircleAvatar(backgroundColor: color, child: Icon(eventIcon(e.type), color: Colors.white)),
        title: Text(e.title),
        subtitle: Text('${DateFormat('d MMM yyyy, HH:mm:ss').format(e.detectedAt)}\n${e.actionTaken}'),
        trailing: Chip(
          label: Text(e.severity.toUpperCase(), style: const TextStyle(color: Colors.white)),
          backgroundColor: color,
          side: BorderSide.none,
        ),
        childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        expandedCrossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (e.description != null) Text(e.description!),
          const SizedBox(height: 8),
          Wrap(spacing: 16, runSpacing: 4, children: [
            Text('Status: ${e.status}'),
            if (e.driverName != null) Text('Driver: ${e.driverName}'),
            if (e.signals['ear'] != null) Text('EAR: ${e.signals['ear']}'),
            if (e.signals['yaw'] != null) Text('Yaw: ${(e.signals['yaw'] as num).round()}°'),
            if (e.signals['pitch'] != null) Text('Pitch: ${(e.signals['pitch'] as num).round()}° (+ = down)'),
            if (e.signals['perclos'] != null)
              Text('PERCLOS: ${((e.signals['perclos'] as num) * 100).round()}% of the last minute'),
            if (e.signals['blinkRate'] != null) Text('Blinks: ${e.signals['blinkRate']}/min'),
            if (e.signals['blinkMs'] != null) Text('Blink duration: ${e.signals['blinkMs']} ms'),
            if ((e.signals['yawns'] ?? 0) > 0) Text('Yawns (5 min): ${e.signals['yawns']}'),
            if (e.signals['emotion'] != null) Text('Emotion: ${e.signals['emotion']}'),
            if (e.signals['sustainedMs'] != null)
              Text('Held for ${((e.signals['sustainedMs'] as num) / 1000).toStringAsFixed(1)} s'),
            if (e.acknowledgedAt != null)
              Text('Acknowledged ${DateFormat.Hms().format(e.acknowledgedAt!)} via '
                  '${e.acknowledgedVia == 'edge_button' ? 'vehicle button' : 'app'}'),
            if (e.escalatedAt != null) Text('Escalated ${DateFormat.Hms().format(e.escalatedAt!)}'),
          ]),
          const SizedBox(height: 12),
          Wrap(spacing: 8, children: [
            if (e.clip?.available == true)
              FilledButton.icon(
                onPressed: () => Navigator.of(context).push(MaterialPageRoute(
                  builder: (_) => VideoScreen(clipId: e.clip!.id, title: e.title),
                )),
                icon: const Icon(Icons.play_circle),
                label: Text('Play clip (${e.clip!.durationSec.round()} s)'),
              )
            else if (e.clip != null)
              Chip(label: Text(e.clip!.status == 'deleted' ? 'Clip removed to free space' : 'Clip is being saved…')),
            if (e.type == 'unverified_driver')
              OutlinedButton.icon(
                onPressed: () => _showPhoto(context, e.id),
                icon: const Icon(Icons.photo),
                label: const Text('Photo'),
              ),
            if (e.lat != null)
              OutlinedButton.icon(
                onPressed: () => launchUrl(Uri.parse('https://maps.google.com/?q=${e.lat},${e.lng}')),
                icon: const Icon(Icons.map),
                label: const Text('Location'),
              ),
            if (e.escalatedAt != null)
              OutlinedButton.icon(
                onPressed: () => _showDeliveries(context, e.id),
                icon: const Icon(Icons.contact_phone),
                label: const Text('Who was notified'),
              ),
          ]),
        ],
      ),
    );
  }

  Future<void> _showPhoto(BuildContext context, String id) async {
    final detail = SafetyEvent.fromJson(await context.read<ApiClient>().get('/events/$id'));
    if (!context.mounted) return;
    showDialog<void>(
      context: context,
      builder: (d) => AlertDialog(
        title: const Text('Person in the driver\'s seat'),
        content: detail.photo == null
            ? const Text('No photo was taken for this event.')
            : Image.memory(base64Decode(detail.photo!), fit: BoxFit.contain),
        actions: [TextButton(onPressed: () => Navigator.pop(d), child: const Text('Close'))],
      ),
    );
  }

  Future<void> _showDeliveries(BuildContext context, String id) async {
    final api = context.read<ApiClient>();
    final detail = SafetyEvent.fromJson(await api.get('/events/$id'));
    if (!context.mounted) return;
    final rows = detail.notifications.where((n) => n.alertType == 'escalation').toList();
    showModalBottomSheet(
      context: context,
      builder: (_) => ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('Emergency notifications', style: Theme.of(context).textTheme.titleLarge),
          for (final n in rows)
            ListTile(
              leading: Icon(n.status == 'sent' ? Icons.check_circle : Icons.error,
                  color: n.status == 'sent' ? safeColor : criticalColor),
              title: Text(n.contactName ?? 'You'),
              subtitle: Text('${n.channel.toUpperCase()} • ${n.status}${n.error != null ? ' — ${n.error}' : ''}'),
            ),
        ],
      ),
    );
  }
}

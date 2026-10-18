import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api/api_client.dart';
import '../state/auth_state.dart';
import '../theme.dart';

/// Links the WhatsApp number that sends escalation alerts to emergency
/// contacts: the vehicle unit shows a QR code, which is scanned from that
/// phone under WhatsApp → Linked devices, like WhatsApp Web.
class WhatsAppScreen extends StatefulWidget {
  const WhatsAppScreen({super.key});

  @override
  State<WhatsAppScreen> createState() => _WhatsAppScreenState();
}

class _WhatsAppScreenState extends State<WhatsAppScreen> {
  Map<String, dynamic>? _status;
  String? _loadError;
  bool _busy = false;
  Timer? _poll;
  final _phone = TextEditingController(text: '+92');
  final _ownerPhone = TextEditingController();
  bool _ownerLoaded = false;

  ApiClient get _api => context.read<ApiClient>();
  String get _state => _status?['status'] ?? 'disconnected';

  @override
  void initState() {
    super.initState();
    _refresh();
    _loadOwnerNumber();
    // Poll while open: the QR code changes every ~20 s and we must notice the scan.
    _poll = Timer.periodic(const Duration(seconds: 2), (_) => _refresh());
  }

  @override
  void dispose() {
    _poll?.cancel();
    _phone.dispose();
    _ownerPhone.dispose();
    super.dispose();
  }

  Future<void> _refresh() async {
    try {
      final s = await _api.get('/whatsapp') as Map<String, dynamic>;
      if (mounted) {
        setState(() {
          _status = s;
          _loadError = null;
        });
      }
    } catch (e) {
      if (mounted) setState(() => _loadError = e.toString());
    }
  }

  Future<void> _loadOwnerNumber() async {
    try {
      final cfg = await _api.get('/config') as Map<String, dynamic>;
      if (mounted) {
        setState(() {
          _ownerPhone.text = cfg['ownerWhatsApp'] ?? '';
          _ownerLoaded = true;
        });
      }
    } catch (_) {}
  }

  Future<void> _saveOwnerNumber() => _run(() async {
        final v = _ownerPhone.text.trim();
        await _api.patch('/config', {'ownerWhatsApp': v.isEmpty ? null : v});
        _snack(v.isEmpty ? 'Unknown-driver alerts will go to the linked number' : 'Unknown-driver alerts will go to $v');
      });

  Future<void> _run(Future<void> Function() action) async {
    setState(() => _busy = true);
    try {
      await action();
    } catch (e) {
      _snack(e.toString());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _snack(String msg) {
    if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }

  Future<void> _link() => _run(() async {
        final s = await _api.post('/whatsapp/link') as Map<String, dynamic>;
        if (mounted) setState(() => _status = s);
      });

  Future<void> _unlink() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (d) => AlertDialog(
        title: const Text('Unlink WhatsApp?'),
        content: const Text('Emergency contacts will stop getting WhatsApp alerts until you link a number again.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(d, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(d, true), child: const Text('Unlink')),
        ],
      ),
    );
    if (ok != true) return;
    await _run(() async {
      final s = await _api.post('/whatsapp/unlink') as Map<String, dynamic>;
      if (mounted) setState(() => _status = s);
    });
  }

  Future<void> _test() => _run(() async {
        await _api.post('/whatsapp/test', {'phone': _phone.text.trim()});
        _snack('Test message sent to ${_phone.text.trim()}');
      });

  @override
  Widget build(BuildContext context) {
    final owner = context.read<AuthState>().user?.isOwner ?? false;
    final s = _status;

    return Scaffold(
      appBar: AppBar(title: const Text('WhatsApp alerts')),
      body: s == null
          ? Center(child: _loadError == null ? const CircularProgressIndicator() : Text(_loadError!))
          : ListView(padding: const EdgeInsets.all(16), children: [
              _statusCard(s),
              const SizedBox(height: 16),
              if (s['enabled'] == false)
                const Text('WhatsApp is turned off on this server (WHATSAPP=off).')
              else if (!owner)
                const Text('Only the vehicle owner can link or unlink WhatsApp.')
              else ...[
                _ownerNumber(),
                const SizedBox(height: 16),
                ..._body(s),
              ],
            ]),
    );
  }

  Widget _ownerNumber() => Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('Your WhatsApp number', style: TextStyle(fontWeight: FontWeight.bold)),
            const SizedBox(height: 4),
            const Text(
              "Gets a message with a photo when someone who is not a registered driver sits in the driver's seat. "
              'Use a different number from the linked one: WhatsApp does not notify you about messages you send yourself.',
              style: TextStyle(fontSize: 12),
            ),
            const SizedBox(height: 8),
            Row(children: [
              Expanded(
                child: TextField(
                  controller: _ownerPhone,
                  keyboardType: TextInputType.phone,
                  decoration: const InputDecoration(labelText: 'Owner number', hintText: '+923001234567'),
                ),
              ),
              const SizedBox(width: 8),
              FilledButton(onPressed: _busy || !_ownerLoaded ? null : _saveOwnerNumber, child: const Text('Save')),
            ]),
          ]),
        ),
      );

  Widget _statusCard(Map<String, dynamic> s) {
    final (icon, color, title) = switch (_state) {
      'connected' => (Icons.check_circle, safeColor, 'Connected as +${s['phone'] ?? ''}'),
      'qr' => (Icons.qr_code_2, warningColor, 'Waiting for the QR code to be scanned'),
      'connecting' => (Icons.sync, warningColor, 'Connecting to WhatsApp…'),
      _ => (Icons.link_off, Colors.blueGrey, 'Not linked'),
    };
    return Card(
      color: color.withValues(alpha: 0.12),
      child: ListTile(
        leading: Icon(icon, color: color, size: 36),
        title: Text(title, style: const TextStyle(fontWeight: FontWeight.bold)),
        subtitle: Text(_state == 'connected'
            ? 'Alerts that escalate are sent from this number to every emergency contact.'
            : s['error'] ?? 'Link a WhatsApp number to send alerts to emergency contacts.'),
      ),
    );
  }

  List<Widget> _body(Map<String, dynamic> s) {
    switch (_state) {
      case 'connected':
        return [
          const Text('Send a test message', style: TextStyle(fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          Row(children: [
            Expanded(
              child: TextField(
                controller: _phone,
                keyboardType: TextInputType.phone,
                decoration: const InputDecoration(labelText: 'Phone number', hintText: '+923001234567'),
              ),
            ),
            const SizedBox(width: 8),
            FilledButton.icon(onPressed: _busy ? null : _test, icon: const Icon(Icons.send), label: const Text('Send')),
          ]),
          const SizedBox(height: 24),
          OutlinedButton.icon(
            onPressed: _busy ? null : _unlink,
            icon: const Icon(Icons.link_off),
            label: const Text('Unlink this number'),
          ),
        ];
      case 'qr':
        final qr = s['qr'] as String?;
        return [
          if (qr != null)
            Center(
              child: Container(
                color: Colors.white,
                padding: const EdgeInsets.all(12),
                child: Image.memory(base64Decode(qr.split(',').last), width: 280, height: 280, gaplessPlayback: true),
              ),
            ),
          const SizedBox(height: 16),
          const _Steps(),
          const SizedBox(height: 8),
          TextButton(onPressed: _busy ? null : _unlink, child: const Text('Cancel')),
        ];
      case 'connecting':
        return [const Center(child: CircularProgressIndicator())];
      default:
        return [
          const _Steps(),
          const SizedBox(height: 16),
          FilledButton.icon(
            onPressed: _busy ? null : _link,
            icon: const Icon(Icons.qr_code),
            label: const Text('Link WhatsApp'),
          ),
          const SizedBox(height: 12),
          const Text(
            'Use a spare SIM if you can: this uses WhatsApp\'s linked-device feature unofficially, so WhatsApp '
            'could restrict the number. Contacts need no setup.',
            style: TextStyle(fontSize: 12),
          ),
        ];
    }
  }
}

class _Steps extends StatelessWidget {
  const _Steps();

  @override
  Widget build(BuildContext context) => const Text(
        '1. Press Link WhatsApp to show a QR code.\n'
        '2. On the phone with the sending number, open WhatsApp → Settings → Linked devices → Link a device.\n'
        '3. Scan the QR code. This screen shows "Connected" in a few seconds.',
      );
}

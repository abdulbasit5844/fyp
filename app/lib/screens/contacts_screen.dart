import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../api/api_client.dart';
import '../models.dart';
import '../state/auth_state.dart';

const maxContacts = 5;

/// Emergency contacts (FR6.4): 1 to 5 people who receive the GPS location
/// when an alert is not acknowledged.
class ContactsScreen extends StatefulWidget {
  const ContactsScreen({super.key});

  @override
  State<ContactsScreen> createState() => _ContactsScreenState();
}

class _ContactsScreenState extends State<ContactsScreen> {
  List<EmergencyContact>? _contacts;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final list = await context.read<ApiClient>().get('/contacts') as List;
      setState(() => _contacts = list.map((j) => EmergencyContact.fromJson(j)).toList());
    } catch (e) {
      setState(() => _error = e.toString());
    }
  }

  Future<void> _edit([EmergencyContact? c]) async {
    final saved = await showDialog<bool>(context: context, builder: (_) => _ContactDialog(contact: c));
    if (saved == true) _load();
  }

  Future<void> _delete(EmergencyContact c) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (d) => AlertDialog(
        title: Text('Remove ${c.name}?'),
        content: const Text('They will no longer receive emergency alerts.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(d, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(d, true), child: const Text('Remove')),
        ],
      ),
    );
    if (ok != true || !mounted) return;
    try {
      await context.read<ApiClient>().delete('/contacts/${c.id}');
      _load();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
    }
  }

  @override
  Widget build(BuildContext context) {
    final owner = context.read<AuthState>().user?.isOwner ?? false;
    final contacts = _contacts;
    final full = (contacts?.length ?? 0) >= maxContacts;

    return Scaffold(
      appBar: AppBar(title: Text('Emergency contacts${contacts == null ? '' : ' (${contacts.length}/$maxContacts)'}')),
      floatingActionButton: owner && contacts != null && !full
          ? FloatingActionButton.extended(
              onPressed: _edit, icon: const Icon(Icons.person_add), label: const Text('Add contact'))
          : null,
      body: contacts == null
          ? Center(child: _error == null ? const CircularProgressIndicator() : Text(_error!))
          : ListView(
              padding: const EdgeInsets.fromLTRB(12, 12, 12, 96),
              children: [
                if (contacts.isEmpty)
                  Card(
                    color: Theme.of(context).colorScheme.errorContainer,
                    child: const ListTile(
                      leading: Icon(Icons.warning),
                      title: Text('Add at least one emergency contact'),
                      subtitle: Text('Escalation cannot reach anyone until you do.'),
                    ),
                  ),
                if (full)
                  const Padding(
                    padding: EdgeInsets.all(8),
                    child: Text('You have the maximum of 5 contacts. Remove one to add another.'),
                  ),
                for (final c in contacts)
                  Card(
                    child: ListTile(
                      leading: CircleAvatar(child: Text('${c.priority}')),
                      title: Text(c.name),
                      subtitle: Text([c.phone, c.relationship, c.email].whereType<String>().where((s) => s.isNotEmpty).join(' • ')),
                      trailing: owner
                          ? Row(mainAxisSize: MainAxisSize.min, children: [
                              IconButton(icon: const Icon(Icons.edit), tooltip: 'Edit', onPressed: () => _edit(c)),
                              IconButton(icon: const Icon(Icons.delete), tooltip: 'Remove', onPressed: () => _delete(c)),
                            ])
                          : null,
                    ),
                  ),
              ],
            ),
    );
  }
}

class _ContactDialog extends StatefulWidget {
  const _ContactDialog({this.contact});
  final EmergencyContact? contact;

  @override
  State<_ContactDialog> createState() => _ContactDialogState();
}

class _ContactDialogState extends State<_ContactDialog> {
  final _form = GlobalKey<FormState>();
  late final _name = TextEditingController(text: widget.contact?.name);
  late final _phone = TextEditingController(text: widget.contact?.phone ?? '+92');
  late final _email = TextEditingController(text: widget.contact?.email);
  late final _relationship = TextEditingController(text: widget.contact?.relationship);
  late int _priority = widget.contact?.priority ?? 1;
  late bool _sms = widget.contact?.notifyBySms ?? true;
  bool _busy = false;
  String? _error;

  Future<void> _save() async {
    if (!_form.currentState!.validate()) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    final body = {
      'name': _name.text.trim(),
      'phone': _phone.text.replaceAll(RegExp(r'[\s-]'), ''),
      'email': _email.text.trim().isEmpty ? null : _email.text.trim(),
      'relationship': _relationship.text.trim(),
      'priority': _priority,
      'notifyBySms': _sms,
    }..removeWhere((k, v) => v == null);
    try {
      final api = context.read<ApiClient>();
      widget.contact == null
          ? await api.post('/contacts', body)
          : await api.patch('/contacts/${widget.contact!.id}', body);
      if (mounted) Navigator.pop(context, true);
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(widget.contact == null ? 'Add emergency contact' : 'Edit contact'),
      content: SizedBox(
        width: 400,
        child: Form(
          key: _form,
          child: SingleChildScrollView(
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              TextFormField(
                controller: _name,
                decoration: const InputDecoration(labelText: 'Name'),
                validator: (v) => (v ?? '').trim().isEmpty ? 'Required' : null,
              ),
              TextFormField(
                controller: _phone,
                decoration: const InputDecoration(labelText: 'Phone', helperText: 'International format, e.g. +923001234567'),
                keyboardType: TextInputType.phone,
                validator: (v) => RegExp(r'^\+[1-9]\d{7,14}$').hasMatch((v ?? '').replaceAll(RegExp(r'[\s-]'), ''))
                    ? null
                    : 'Use international format: +92…',
              ),
              TextFormField(controller: _relationship, decoration: const InputDecoration(labelText: 'Relationship (optional)')),
              TextFormField(
                controller: _email,
                decoration: const InputDecoration(labelText: 'Email (optional)'),
                keyboardType: TextInputType.emailAddress,
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<int>(
                initialValue: _priority,
                decoration: const InputDecoration(labelText: 'Priority'),
                items: [for (var i = 1; i <= maxContacts; i++) DropdownMenuItem(value: i, child: Text('$i'))],
                onChanged: (v) => setState(() => _priority = v ?? 1),
              ),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('SMS if they do not have the app'),
                value: _sms,
                onChanged: (v) => setState(() => _sms = v),
              ),
              if (_error != null) Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
            ]),
          ),
        ),
      ),
      actions: [
        TextButton(onPressed: _busy ? null : () => Navigator.pop(context, false), child: const Text('Cancel')),
        FilledButton(onPressed: _busy ? null : _save, child: Text(_busy ? 'Saving…' : 'Save')),
      ],
    );
  }
}

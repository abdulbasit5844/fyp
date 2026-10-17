import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../state/auth_state.dart';

/// Sign-in and registration (FR5.1, FR5.2) on one screen with a mode toggle.
class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _form = GlobalKey<FormState>();
  final _server = TextEditingController();
  final _name = TextEditingController();
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _confirm = TextEditingController();
  bool _register = false;
  bool _busy = false;
  bool _obscure = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _server.text = context.read<AuthState>().tokens.serverUrl;
  }

  Future<void> _submit() async {
    if (!_form.currentState!.validate()) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    final auth = context.read<AuthState>();
    try {
      if (_register) {
        await auth.register(_server.text, _name.text, _email.text, _password.text);
      } else {
        await auth.login(_server.text, _email.text, _password.text);
      }
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Scaffold(
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: Form(
              key: _form,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Icon(Icons.shield_moon, size: 64, color: scheme.primary),
                  const SizedBox(height: 12),
                  Text('Driver Safety', textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.headlineMedium),
                  const SizedBox(height: 4),
                  Text(_register ? 'Create your owner account' : 'Sign in to your vehicle',
                      textAlign: TextAlign.center),
                  const SizedBox(height: 24),
                  TextFormField(
                    controller: _server,
                    decoration: const InputDecoration(
                      labelText: 'Vehicle unit address',
                      helperText: 'e.g. http://pi.local:3000',
                      prefixIcon: Icon(Icons.router),
                    ),
                    keyboardType: TextInputType.url,
                    validator: (v) => Uri.tryParse(v ?? '')?.hasScheme == true ? null : 'Enter a URL like http://pi.local:3000',
                  ),
                  const SizedBox(height: 12),
                  if (_register) ...[
                    TextFormField(
                      controller: _name,
                      decoration: const InputDecoration(labelText: 'Full name', prefixIcon: Icon(Icons.person)),
                      textCapitalization: TextCapitalization.words,
                      validator: (v) => (v ?? '').trim().isEmpty ? 'Enter your name' : null,
                    ),
                    const SizedBox(height: 12),
                  ],
                  TextFormField(
                    controller: _email,
                    decoration: const InputDecoration(labelText: 'Email', prefixIcon: Icon(Icons.email)),
                    keyboardType: TextInputType.emailAddress,
                    autofillHints: const [AutofillHints.email],
                    validator: (v) => RegExp(r'^[^\s@]+@[^\s@]+\.[^\s@]+$').hasMatch((v ?? '').trim())
                        ? null
                        : 'Enter a valid email address',
                  ),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _password,
                    obscureText: _obscure,
                    decoration: InputDecoration(
                      labelText: 'Password',
                      prefixIcon: const Icon(Icons.lock),
                      suffixIcon: IconButton(
                        icon: Icon(_obscure ? Icons.visibility : Icons.visibility_off),
                        onPressed: () => setState(() => _obscure = !_obscure),
                      ),
                    ),
                    validator: (v) => (v ?? '').length < 8 ? 'At least 8 characters' : null,
                    onFieldSubmitted: (_) => _register ? null : _submit(),
                  ),
                  if (_register) ...[
                    const SizedBox(height: 12),
                    TextFormField(
                      controller: _confirm,
                      obscureText: _obscure,
                      decoration: const InputDecoration(labelText: 'Confirm password', prefixIcon: Icon(Icons.lock_outline)),
                      validator: (v) => v != _password.text ? 'Passwords do not match' : null,
                    ),
                  ],
                  if (_error != null) ...[
                    const SizedBox(height: 16),
                    Text(_error!, style: TextStyle(color: scheme.error)),
                  ],
                  const SizedBox(height: 24),
                  FilledButton(
                    onPressed: _busy ? null : _submit,
                    style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(52)),
                    child: _busy
                        ? const SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2))
                        : Text(_register ? 'Create account' : 'Sign in'),
                  ),
                  const SizedBox(height: 8),
                  TextButton(
                    onPressed: _busy ? null : () => setState(() {
                      _register = !_register;
                      _error = null;
                    }),
                    child: Text(_register ? 'Already have an account? Sign in' : 'New here? Create an account'),
                  ),
                  if (!_register)
                    TextButton(
                      onPressed: () => ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
                        content: Text('Ask the vehicle owner or administrator to reset your password.'),
                      )),
                      child: const Text('Forgot password?'),
                    ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  @override
  void dispose() {
    for (final c in [_server, _name, _email, _password, _confirm]) {
      c.dispose();
    }
    super.dispose();
  }
}

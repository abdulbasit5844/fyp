import 'dart:async';

import 'package:flutter/material.dart';
import 'package:media_kit/media_kit.dart';
import 'package:provider/provider.dart';

import 'api/api_client.dart';
import 'api/token_store.dart';
import 'models.dart';
import 'screens/alert_screen.dart';
import 'screens/home_screen.dart';
import 'screens/login_screen.dart';
import 'state/auth_state.dart';
import 'state/live_state.dart';
import 'state/theme_state.dart';
import 'theme.dart';

final navigatorKey = GlobalKey<NavigatorState>();

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  MediaKit.ensureInitialized();

  final tokens = TokenStore();
  final api = ApiClient(tokens);
  final auth = AuthState(api, tokens)..init();

  runApp(MultiProvider(
    providers: [
      Provider.value(value: api),
      ChangeNotifierProvider.value(value: auth),
      ChangeNotifierProvider(create: (_) => LiveState(api)),
      ChangeNotifierProvider(create: (_) => ThemeState()..load()),
    ],
    child: const DmsApp(),
  ));
}

class DmsApp extends StatelessWidget {
  const DmsApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Driver Safety',
      navigatorKey: navigatorKey,
      debugShowCheckedModeBanner: false,
      theme: buildTheme(Brightness.light),
      darkTheme: buildTheme(Brightness.dark),
      themeMode: context.watch<ThemeState>().mode,
      home: const _Root(),
    );
  }
}

/// Switches between sign-in and the app, and pops up the full-screen alert
/// whenever a new alert arrives.
class _Root extends StatefulWidget {
  const _Root();

  @override
  State<_Root> createState() => _RootState();
}

class _RootState extends State<_Root> {
  StreamSubscription<SafetyEvent>? _alerts;
  String? _showing;

  @override
  void initState() {
    super.initState();
    final live = context.read<LiveState>();
    _alerts = live.newAlerts.listen((event) async {
      if (_showing == event.id) return;
      _showing = event.id;
      final ctx = navigatorKey.currentContext;
      if (ctx != null && ctx.mounted) await showAlertPopup(ctx, event);
      _showing = null;
    });
  }

  @override
  void dispose() {
    _alerts?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthState>();
    final live = context.read<LiveState>();
    switch (auth.status) {
      case AuthStatus.loading:
        return const Scaffold(body: Center(child: CircularProgressIndicator()));
      case AuthStatus.signedOut:
        live.stop();
        return const LoginScreen();
      case AuthStatus.signedIn:
        live.start();
        return const HomeScreen();
    }
  }
}

import 'package:flutter/foundation.dart';

import '../api/api_client.dart';
import '../api/token_store.dart';
import '../models.dart';

enum AuthStatus { loading, signedOut, signedIn }

class AuthState extends ChangeNotifier {
  AuthState(this.api, this.tokens) {
    api.onSessionExpired = () => _signOutLocal();
  }

  final ApiClient api;
  final TokenStore tokens;
  AuthStatus status = AuthStatus.loading;
  User? user;

  /// Restores the previous session on app start.
  Future<void> init() async {
    try {
      await tokens.load();
    } catch (e) {
      // Never leave the app on the loading screen; fall back to sign-in.
      debugPrint('Could not restore the session: $e');
    }
    if (tokens.refreshToken != null) {
      try {
        user = User.fromJson(await api.get('/auth/me'));
        status = AuthStatus.signedIn;
        notifyListeners();
        return;
      } catch (_) {/* fall through to sign-in */}
    }
    status = AuthStatus.signedOut;
    notifyListeners();
  }

  Future<void> login(String server, String email, String password) async {
    await tokens.saveServer(server);
    await _accept(await api.post('/auth/login', {'email': email.trim(), 'password': password}));
  }

  Future<void> register(String server, String name, String email, String password) async {
    await tokens.saveServer(server);
    await _accept(await api.post('/auth/register', {'name': name.trim(), 'email': email.trim(), 'password': password}));
  }

  Future<void> _accept(dynamic session) async {
    await tokens.saveTokens(session['accessToken'], session['refreshToken']);
    user = User.fromJson(session['user']);
    status = AuthStatus.signedIn;
    notifyListeners();
  }

  Future<void> logout() async {
    try {
      await api.post('/auth/logout', {'refreshToken': tokens.refreshToken});
    } catch (_) {/* offline logout still clears the device */}
    await _signOutLocal();
  }

  Future<void> _signOutLocal() async {
    await tokens.clear();
    user = null;
    status = AuthStatus.signedOut;
    notifyListeners();
  }
}

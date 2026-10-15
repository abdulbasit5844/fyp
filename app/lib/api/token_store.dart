import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Persists the server address and session tokens. Tokens go to the OS
/// keychain when one is available, otherwise to app preferences (e.g. a
/// headless Raspberry Pi without a keyring).
class TokenStore {
  static const _secure = FlutterSecureStorage();
  static const _kAccess = 'accessToken';
  static const _kRefresh = 'refreshToken';
  static const _kServer = 'serverUrl';

  String? accessToken;
  String? refreshToken;
  String serverUrl = 'http://pi.local:3000';

  Future<void> load() async {
    final prefs = await SharedPreferences.getInstance();
    serverUrl = prefs.getString(_kServer) ?? serverUrl;
    accessToken = await _read(_kAccess);
    refreshToken = await _read(_kRefresh);
  }

  Future<void> saveServer(String url) async {
    serverUrl = url.trim().replaceAll(RegExp(r'/+$'), '');
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_kServer, serverUrl);
  }

  Future<void> saveTokens(String access, String refresh) async {
    accessToken = access;
    refreshToken = refresh;
    await _write(_kAccess, access);
    await _write(_kRefresh, refresh);
  }

  Future<void> clear() async {
    accessToken = null;
    refreshToken = null;
    await _write(_kAccess, null);
    await _write(_kRefresh, null);
  }

  Future<String?> _read(String key) async {
    try {
      return await _secure.read(key: key);
    } catch (_) {
      return (await SharedPreferences.getInstance()).getString(key);
    }
  }

  Future<void> _write(String key, String? value) async {
    try {
      value == null ? await _secure.delete(key: key) : await _secure.write(key: key, value: value);
    } catch (_) {
      final prefs = await SharedPreferences.getInstance();
      value == null ? await prefs.remove(key) : await prefs.setString(key, value);
    }
  }
}

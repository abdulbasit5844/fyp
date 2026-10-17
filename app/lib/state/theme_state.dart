import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Light / dark / follow-the-system appearance, remembered on this device.
class ThemeState extends ChangeNotifier {
  static const _key = 'themeMode';

  ThemeMode mode = ThemeMode.system;

  Future<void> load() async {
    try {
      final saved = (await SharedPreferences.getInstance()).getString(_key);
      mode = ThemeMode.values.firstWhere((m) => m.name == saved, orElse: () => ThemeMode.system);
      notifyListeners();
    } catch (_) {
      // Keep the system default if preferences are unavailable.
    }
  }

  Future<void> set(ThemeMode m) async {
    if (m == mode) return;
    mode = m;
    notifyListeners();
    try {
      await (await SharedPreferences.getInstance()).setString(_key, m.name);
    } catch (_) {}
  }

  /// One-tap switch from whatever is showing now to the opposite.
  Future<void> toggle(Brightness current) => set(current == Brightness.dark ? ThemeMode.light : ThemeMode.dark);
}

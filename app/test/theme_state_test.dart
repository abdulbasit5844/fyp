import 'package:dms_app/state/theme_state.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  test('theme choice is remembered and toggles between light and dark', () async {
    SharedPreferences.setMockInitialValues({});
    final t = ThemeState();
    await t.load();
    expect(t.mode, ThemeMode.system);

    await t.toggle(Brightness.light);
    expect(t.mode, ThemeMode.dark);
    await t.toggle(Brightness.dark);
    expect(t.mode, ThemeMode.light);

    await t.set(ThemeMode.dark);
    final reopened = ThemeState();
    await reopened.load();
    expect(reopened.mode, ThemeMode.dark);
  });
}

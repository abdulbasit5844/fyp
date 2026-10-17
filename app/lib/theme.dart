import 'package:flutter/material.dart';

import 'models.dart';

/// Material 3 theme (UI-1) with no text smaller than 14sp (UI-2).
ThemeData buildTheme(Brightness brightness) {
  final base = ThemeData(
    useMaterial3: true,
    colorSchemeSeed: const Color(0xFF1565C0),
    brightness: brightness,
  );
  final t = base.textTheme;
  return base.copyWith(
    textTheme: t.copyWith(
      bodySmall: t.bodySmall?.copyWith(fontSize: 14),
      labelSmall: t.labelSmall?.copyWith(fontSize: 14),
      labelMedium: t.labelMedium?.copyWith(fontSize: 14),
    ),
  );
}

/// Severity colours (USE-2): red for critical, amber for warning.
const criticalColor = Color(0xFFC62828);
const warningColor = Color(0xFFF9A825);
const safeColor = Color(0xFF2E7D32);

Color stateColor(DriverState s) => switch (s) {
      DriverState.safe => safeColor,
      DriverState.warning => warningColor,
      DriverState.critical => criticalColor,
    };

Color severityColor(String severity) => severity == 'critical' ? criticalColor : warningColor;

/// The same colour, lightened in dark mode so text and icons stay readable.
Color readable(BuildContext context, Color c) =>
    Theme.of(context).brightness == Brightness.dark ? Color.lerp(c, Colors.white, 0.35)! : c;

/// Icon for each event type (UI-4: text + icon on every alert).
IconData eventIcon(String type) => switch (type) {
      'drowsiness' => Icons.bedtime,
      'inattention' => Icons.visibility_off,
      'emotional_distress' => Icons.sentiment_very_dissatisfied,
      'unverified_driver' => Icons.person_off,
      'unauthorized_occupant' => Icons.no_accounts,
      'key_left_inside' => Icons.key,
      _ => Icons.warning_amber,
    };

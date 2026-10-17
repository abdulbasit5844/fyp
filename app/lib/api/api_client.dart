import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import 'token_store.dart';

class ApiException implements Exception {
  ApiException(this.status, this.message, [this.details]);
  final int status;
  final String message;
  final Map<String, dynamic>? details;

  /// Field errors from the backend's validation, joined for display.
  String get detailText =>
      details == null || details!.isEmpty ? message : details!.values.join('\n');

  @override
  String toString() => detailText;
}

/// Thin REST client for the Node backend. Refreshes the access token once on
/// a 401 (FR5.3) and calls [onSessionExpired] when that fails too.
class ApiClient {
  ApiClient(this.tokens);

  final TokenStore tokens;
  void Function()? onSessionExpired;
  Future<bool>? _refreshing;

  Uri uri(String path, [Map<String, dynamic>? query]) {
    final base = Uri.parse(tokens.serverUrl);
    return base.replace(
      path: '${base.path}/api$path',
      queryParameters: query?.map((k, v) => MapEntry(k, '$v')),
    );
  }

  Map<String, String> get authHeaders =>
      {if (tokens.accessToken != null) 'Authorization': 'Bearer ${tokens.accessToken}'};

  Future<dynamic> get(String path, {Map<String, dynamic>? query}) =>
      _send('GET', path, query: query);
  Future<dynamic> post(String path, [Object? body]) => _send('POST', path, body: body);
  Future<dynamic> patch(String path, Object body) => _send('PATCH', path, body: body);
  Future<dynamic> delete(String path) => _send('DELETE', path);

  Future<dynamic> _send(String method, String path,
      {Object? body, Map<String, dynamic>? query, bool retry = true}) async {
    final req = http.Request(method, uri(path, query))
      ..headers.addAll({...authHeaders, 'Content-Type': 'application/json'});
    if (body != null) req.body = jsonEncode(body);

    final http.Response res;
    try {
      res = await http.Response.fromStream(await req.send().timeout(const Duration(seconds: 10)));
    } on TimeoutException {
      throw ApiException(0, 'The vehicle unit did not respond. Check that you are on the same network.');
    } catch (_) {
      throw ApiException(0, 'Cannot reach ${tokens.serverUrl}. Check the server address and network.');
    }

    if (res.statusCode == 401 && retry && !path.startsWith('/auth/') && await refresh()) {
      return _send(method, path, body: body, query: query, retry: false);
    }

    final data = res.body.isEmpty ? null : jsonDecode(res.body);
    if (res.statusCode >= 400) {
      if (res.statusCode == 401 && !path.startsWith('/auth/')) onSessionExpired?.call();
      final map = data is Map<String, dynamic> ? data : const <String, dynamic>{};
      throw ApiException(
        res.statusCode,
        map['error'] as String? ?? 'Request failed (${res.statusCode})',
        (map['details'] as Map?)?.cast<String, dynamic>(),
      );
    }
    return data;
  }

  /// Exchanges the refresh token for a new pair. Concurrent callers share one request.
  Future<bool> refresh() {
    return _refreshing ??= () async {
      try {
        if (tokens.refreshToken == null) return false;
        final res = await http.post(uri('/auth/refresh'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({'refreshToken': tokens.refreshToken}));
        if (res.statusCode != 200) return false;
        final json = jsonDecode(res.body) as Map<String, dynamic>;
        await tokens.saveTokens(json['accessToken'] as String, json['refreshToken'] as String);
        return true;
      } catch (_) {
        return false;
      } finally {
        _refreshing = null;
      }
    }();
  }
}

// lib/services/sync_service.dart
import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:clipnote/services/local_db.dart';
import 'package:clipnote/services/api_service.dart';

class SyncService {
  SyncService(this._api);

  final ApiService _api;
  Timer? _timer;

  void start() {
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(seconds: 30), (_) => _drainOutbox());
  }

  void stop() => _timer?.cancel();

  Future<void> _drainOutbox() async {
    try {
      await localDb.open();
      final batch = await localDb.peekOutbox(limit: 25);
      for (final row in batch) {
        final id = row['id'] as int;
        final kind = row['kind'] as String;
        final payload = jsonDecode(row['payload'] as String) as Map<String, dynamic>;

        try {
          if (kind == 'confirm_download') {
            final mid = payload['meeting_id'] as int;
            await _api.confirmDownloadComplete(mid);
          }
          await localDb.deleteOutbox(id);
        } catch (e) {
          // leave it for later
          debugPrint('[SyncService] retry later: $e');
        }
      }
    } catch (e) {
      debugPrint('[SyncService] outbox error: $e');
    }
  }
}

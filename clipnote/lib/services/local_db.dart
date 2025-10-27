// lib/services/local_db.dart
import 'dart:async';
import 'package:sqflite/sqflite.dart';
import 'package:path/path.dart' as p;

class LocalMeetingDb {
  static const _dbName = 'meetings_local.db';
  static const _ver = 1;

  Database? _db;

  Future<void> open() async {
    if (_db != null) return;
    final dbPath = await getDatabasesPath();
    _db = await openDatabase(
      p.join(dbPath, _dbName),
      version: _ver,
      onCreate: (db, _) async {
        await db.execute('''
          CREATE TABLE IF NOT EXISTS meeting_file(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meeting_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            path TEXT NOT NULL,
            content_type TEXT,
            size_bytes INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
          );
        ''');

        await db.execute('''
          CREATE TABLE IF NOT EXISTS outbox(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,          -- e.g. "confirm_download"
            payload TEXT NOT NULL,       -- JSON
            try_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
          );
        ''');
      },
    );
  }

  // ---------------- Files ----------------
  Future<int> upsertFile({
    required int meetingId,
    required String filename,
    required String path,
    String? contentType,
    int? sizeBytes,
  }) async {
    return _db!.insert('meeting_file', {
      'meeting_id': meetingId,
      'filename': filename,
      'path': path,
      'content_type': contentType,
      'size_bytes': sizeBytes,
    });
  }

  Future<List<Map<String, Object?>>> listByMeeting(int meetingId) {
    return _db!.query(
      'meeting_file',
      where: 'meeting_id=?',
      whereArgs: [meetingId],
      orderBy: 'created_at DESC',
    );
  }

  Future<void> removeByMeeting(int meetingId) async {
    await _db!.delete('meeting_file', where: 'meeting_id=?', whereArgs: [meetingId]);
  }

  Future<void> removeByPath(String path) async {
    await _db!.delete('meeting_file', where: 'path=?', whereArgs: [path]);
  }

  // ---------------- Outbox ----------------
  Future<void> enqueueOutbox(String kind, String payloadJson) async {
    await _db!.insert('outbox', {'kind': kind, 'payload': payloadJson});
  }

  Future<List<Map<String, Object?>>> peekOutbox({int limit = 20}) {
    return _db!.query('outbox', orderBy: 'id ASC', limit: limit);
  }

  Future<void> deleteOutbox(int id) async {
    await _db!.delete('outbox', where: 'id=?', whereArgs: [id]);
  }
}

// A single global instance you can use anywhere
final localDb = LocalMeetingDb();

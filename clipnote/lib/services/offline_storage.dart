// lib/services/offline_storage.dart
import 'dart:io';
import 'dart:typed_data';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:path_provider/path_provider.dart';
import 'package:open_filex/open_filex.dart';
import 'local_db.dart';

Future<Directory> _meetingDir(int meetingId) async {
  final doc = await getApplicationDocumentsDirectory();
  final dir = Directory('${doc.path}/meetings/$meetingId');
  if (!await dir.exists()) await dir.create(recursive: true);
  return dir;
}

Future<File> saveMeetingBytes({
  required int meetingId,
  required String filename,
  required Uint8List bytes,
}) async {
  final dir = await _meetingDir(meetingId);
  final f = File('${dir.path}/$filename');
  final saved = await f.writeAsBytes(bytes, flush: true);
  return saved;
}

Future<bool> deleteMeetingFiles(int meetingId) async {
  final dir = await _meetingDir(meetingId);
  if (await dir.exists()) {
    await dir.delete(recursive: true);
  }
  return true;
}

Future<void> deleteSingleFile(String path) async {
  try {
    final f = File(path);
    if (await f.exists()) await f.delete();
    await localDb.removeByPath(path);
  } catch (e) {
    debugPrint('[OfflineStorage] deleteSingleFile error: $e');
  }
}

Future<void> openLocalFile(String path) async {
  await OpenFilex.open(path);
}

// Outbox enqueue helper
Future<void> enqueueConfirmDownload(int meetingId) async {
  await localDb.enqueueOutbox('confirm_download', jsonEncode({'meeting_id': meetingId}));
}

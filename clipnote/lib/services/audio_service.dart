// lib/services/audio_service.dart
// Android/iOS audio recorder using the `record` plugin v5.
// Exposes start() -> String? filePath, stop() -> String? filePath.

import 'dart:io';
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';

class AudioService {
  final AudioRecorder _rec = AudioRecorder();
  String? _currentPath;

  Future<String?> start() async {
    final hasPerm = await _rec.hasPermission();
    if (!hasPerm) return null;

    final dir = await getTemporaryDirectory();
    final ts = DateTime.now().millisecondsSinceEpoch;
    final path = '${dir.path}/clipnote_$ts.m4a';

    const config = RecordConfig(
      encoder: AudioEncoder.aacLc,
      bitRate: 128000,
      sampleRate: 44100,
      numChannels: 1,
    );

    await _rec.start(config, path: path);
    _currentPath = path;
    return path;
  }

  Future<String?> stop() async {
    final isRec = await _rec.isRecording();
    if (!isRec) return _currentPath;

    await _rec.stop();
    final p = _currentPath;
    _currentPath = null;
    if (p != null && await File(p).exists()) return p;
    return null;
  }

  Future<void> dispose() async {
    final isRec = await _rec.isRecording();
    if (isRec) await _rec.stop();
  }
}

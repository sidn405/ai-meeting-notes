// lib/services/media_service.dart
import 'dart:io';
import 'dart:typed_data';

import 'package:file_picker/file_picker.dart';
import 'package:image_picker/image_picker.dart';

/// Public DTO for picked media (no private types in public API).
class PickedMedia {
  final String filename;
  final Uint8List bytes;
  final String contentType; // e.g., audio/m4a, audio/mpeg, video/mp4, audio/wav
  final int sizeBytes;
  /// 'audio' | 'video'
  final String kind;

  const PickedMedia({
    required this.filename,
    required this.bytes,
    required this.contentType,
    required this.sizeBytes,
    required this.kind,
  });
}

class MediaService {
  final ImagePicker _picker = ImagePicker();

  /// Pick an audio file from device storage. Returns null if canceled.
  Future<PickedMedia?> pickAudio() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: const ['mp3', 'm4a', 'wav', 'mp4'], // mp4 audio too
      allowMultiple: false,
      withData: true, // try to get bytes directly when possible
    );
    if (result == null || result.files.isEmpty) return null;

    final f = result.files.single;
    final bytes = await _bytesFromPlatformFile(f);
    final filename = f.name;
    final contentType = _guessMime(filename);
    return PickedMedia(
      filename: filename,
      bytes: bytes,
      contentType: contentType,
      sizeBytes: bytes.length,
      kind: contentType.startsWith('video/') ? 'video' : 'audio',
    );
  }

  /// Record or pick a short video. Returns null if canceled.
  Future<PickedMedia?> pickVideo({Duration? maxDuration}) async {
    final XFile? x =
        await _picker.pickVideo(source: ImageSource.camera, maxDuration: maxDuration ?? const Duration(seconds: 60));
    if (x == null) return null;

    final file = File(x.path);
    final bytes = await file.readAsBytes();
    final filename = _basename(x.path);
    return PickedMedia(
      filename: filename,
      bytes: bytes,
      contentType: 'video/mp4', // camera video is mp4 on Android/iOS
      sizeBytes: bytes.length,
      kind: 'video',
    );
  }

  /// ------------ helpers (private) ------------

  Future<Uint8List> _bytesFromPlatformFile(PlatformFile f) async {
    if (f.bytes != null) return f.bytes!;
    if (f.path != null) return await File(f.path!).readAsBytes();
    // No data and no path — return empty list to avoid crashes.
    return Uint8List(0);
  }

  String _basename(String path) {
    final idx = path.replaceAll('\\', '/').lastIndexOf('/');
    return idx >= 0 ? path.substring(idx + 1) : path;
  }

  String _guessMime(String filename) {
    final lower = filename.toLowerCase();
    if (lower.endsWith('.m4a')) return 'audio/m4a';
    if (lower.endsWith('.mp3')) return 'audio/mpeg';
    if (lower.endsWith('.wav')) return 'audio/wav';
    if (lower.endsWith('.mp4')) return 'video/mp4';
    return 'application/octet-stream';
  }
}

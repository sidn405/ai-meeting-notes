// lib/services/media_service.dart
import 'dart:io' show File, Platform, RandomAccessFile;
import 'dart:typed_data';
import 'dart:convert';
import 'dio/dio.dart';
import 'file_picker/file_picker.dart';
import 'image_picker/image_picker.dart';

class MediaService {
  MediaService(this.apiBase, Dio? client) : dio = client ?? Dio();
  final String apiBase;
  final Dio dio;

  // ---- MIME + limits -------------------------------------------------------
  static const allowedAudio = ['mp3','m4a','wav'];
  static const allowedVideo = ['mp4'];

  static String mimeOf(String name) {
    final n = name.toLowerCase();
    if (n.endsWith('.mp3')) return 'audio/mpeg';
    if (n.endsWith('.m4a')) return 'audio/mp4';
    if (n.endsWith('.wav')) return 'audio/wav';
    if (n.endsWith('.mp4')) return 'video/mp4';
    return 'application/octet-stream';
  }

  // ---- Public APIs ---------------------------------------------------------
  /// Pick audio from file system (mp3/m4a/wav)
  Future<_PickedData?> pickAudio() async {
    final res = await FilePicker.platform.pickFiles(
      withData: true,
      type: FileType.custom,
      allowedExtensions: [...allowedAudio],
    );
    if (res == null || res.files.isEmpty) return null;
    final f = res.files.first;
    return _PickedData(
      filename: f.name,
      bytes: f.bytes!,
      contentType: mimeOf(f.name),
      size: f.bytes!.lengthInBytes,
    );
  }

  /// Record or pick a video (mp4). Uses the camera/gallery.
  Future<_PickedData?> pickOrRecordVideo({bool record = true}) async {
    final picker = ImagePicker();
    final XFile? x =
        record ? await picker.pickVideo(source: ImageSource.camera)
               : await picker.pickVideo(source: ImageSource.gallery);
    if (x == null) return null;
    final bytes = await x.readAsBytes();
    return _PickedData(
      filename: _ensureMp4Ext(x.name),
      bytes: bytes,
      contentType: 'video/mp4',
      size: bytes.lengthInBytes,
    );
  }

  /// Upload to Backblaze (simple PUT with Content-Length), then record asset
  Future<_Uploaded?> uploadAndRecord({
    required String meetingId,
    required _PickedData picked,
  }) async {
    // 1) presign
    final presign = await dio.post(
      '$apiBase/uploads/presign',
      data: {
        'filename': picked.filename,
        'content_type': picked.contentType,
        'folder': 'raw',
      },
      options: Options(headers: {'Content-Type': 'application/json'}),
    );
    final data = presign.data is Map
        ? presign.data
        : jsonDecode(presign.data as String);
    final putUrl = data['url'] as String;
    final key = data['key'] as String;
    final headers = Map<String, dynamic>.from(data['headers'] ?? {});
    final publicUrl = data['public_url'] as String?;

    // 2) PUT (fixed-length body → avoids 411 on B2)
    final hdrs = <String, String>{
      ...headers.map((k, v) => MapEntry(k, '$v')),
    };
    if (!Platform.environment.containsKey('FLUTTER_TEST')) {
      // Browsers auto-set Content-Length; on mobile/desktop we set it explicitly
      hdrs['Content-Length'] = picked.bytes.length.toString();
    }
    await dio.put(
      putUrl,
      data: picked.bytes,
      options: Options(headers: hdrs, contentType: headers['Content-Type']),
    );

    // 3) record in DB
    await dio.post(
      '$apiBase/meetings/$meetingId/assets',
      data: {
        's3_key': key,
        'filename': picked.filename,
        'type': picked.contentType.startsWith('video') ? 'video' : 'audio',
        'content_type': picked.contentType,
        'size_bytes': picked.size,
      },
      options: Options(headers: {'Content-Type': 'application/json'}),
    );

    return _Uploaded(key: key, publicUrl: publicUrl);
  }

  // ---- helpers -------------------------------------------------------------
  String _ensureMp4Ext(String name) =>
      name.toLowerCase().endsWith('.mp4') ? name : '$name.mp4';
}

class _PickedData {
  _PickedData({
    required this.filename,
    required this.bytes,
    required this.contentType,
    required this.size,
  });
  final String filename;
  final Uint8List bytes;
  final String contentType;
  final int size;
}

class _Uploaded {
  _Uploaded({required this.key, required this.publicUrl});
  final String key;
  final String? publicUrl;
}

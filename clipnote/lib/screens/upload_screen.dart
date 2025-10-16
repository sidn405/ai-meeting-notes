// lib/screens/upload_screen.dart
// Ready-to-use upload screen for audio/video files.
// - If constructed with an audioFile, it uploads that.
// - Otherwise lets the user pick a file (mp3/m4a/wav/mp4).
// - Uses presign -> PUT (fixed-length) -> POST /meetings/{id}/assets.

import 'dart:convert';
import 'dart:typed_data';
import 'dart:io' show File;
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:dio/dio.dart';
import 'package:file_picker/file_picker.dart';

const String API_BASE = "https://ai-meeting-notes-production-81d7.up.railway.app";

class UploadScreen extends StatefulWidget {
  const UploadScreen({super.key, this.audioFile, this.prefillFilename});

  /// Optional file provided by a previous screen (mobile/desktop only).
  final File? audioFile;

  /// Optional name to display if [audioFile] is provided.
  final String? prefillFilename;

  @override
  State<UploadScreen> createState() => _UploadScreenState();
}

class _UploadScreenState extends State<UploadScreen> {
  final dio = Dio(BaseOptions(connectTimeout: const Duration(seconds: 30)));
  final meetingIdCtrl = TextEditingController(text: "demo-meeting-1");

  double progress = 0.0;
  String status = 'Idle';
  String? lastKey;
  String? lastPublicUrl;

  // ----- small helpers -----
  void _setStatus(String s) => setState(() => status = s);
  void _setProgress(double p) => setState(() => progress = p.clamp(0, 1));

  void _toast(String msg) {
    final messenger = ScaffoldMessenger.of(context);
    messenger.hideCurrentSnackBar();
    messenger.showSnackBar(SnackBar(content: Text(msg)));
  }

  String _guessMime(String name) {
    final n = name.toLowerCase();
    if (n.endsWith('.mp3')) return 'audio/mpeg';
    if (n.endsWith('.m4a')) return 'audio/mp4'; // m4a => audio/mp4
    if (n.endsWith('.wav')) return 'audio/wav';
    if (n.endsWith('.mp4')) return 'video/mp4';
    return 'application/octet-stream';
  }

  @override
  void dispose() {
    meetingIdCtrl.dispose();
    super.dispose();
  }

  // ----- record the upload in your backend DB -----
  Future<void> _recordUpload({
    required String meetingId,
    required String key,
    required String filename,
    required String type, // "audio" | "video"
    String? contentType,
    int? sizeBytes,
    int? durationMs,
  }) async {
    try {
      await dio.post(
        "$API_BASE/meetings/$meetingId/assets",
        data: {
          "s3_key": key,
          "filename": filename,
          "type": type,
          "content_type": contentType,
          "size_bytes": sizeBytes,
          "duration_ms": durationMs,
        },
        options: Options(headers: {"Content-Type": "application/json"}),
      );
    } catch (e) {
      _toast("Saved file; server record failed: $e");
    }
  }

  // ----- main flow: pick (or use provided) and upload -----
  Future<void> _pickAndUpload() async {
    setState(() {
      progress = 0;
      status = "Preparing upload…";
      lastKey = null;
      lastPublicUrl = null;
    });

    Uint8List? bytes;
    String? filename;
    String? contentType;

    // If a file was provided by another screen (mobile/desktop only)
    if (!kIsWeb && widget.audioFile != null) {
      final f = widget.audioFile!;
      filename = widget.prefillFilename ?? f.uri.pathSegments.last;
      bytes = await f.readAsBytes();
      contentType = _guessMime(filename);
    } else {
      // Let user pick a file
      final result = await FilePicker.platform.pickFiles(
        withData: kIsWeb, // web needs bytes here
        type: FileType.custom,
        allowedExtensions: ['mp3', 'm4a', 'wav', 'mp4'],
      );
      if (result == null || result.files.isEmpty) {
        _setStatus("Cancelled");
        return;
      }

      final picked = result.files.first; // declare BEFORE usage
      filename = picked.name;
      contentType = _guessMime(filename);

      if (kIsWeb) {
        bytes = picked.bytes!;
      } else {
        final fileLocal = File(picked.path!); // declare local var
        bytes = await fileLocal.readAsBytes();
      }
    }

    // Safety: shouldn’t be null here
    final dataBytes = bytes!;
    final size = dataBytes.lengthInBytes;

    try {
      // 1) presign
      _setStatus("Requesting presigned URL…");
      final presign = await dio.post(
        "$API_BASE/uploads/presign",
        data: {
          "filename": filename,
          "content_type": contentType,
          "folder": "raw"
        },
        options: Options(headers: {"Content-Type": "application/json"}),
      );
      if (presign.statusCode != 200) {
        throw Exception('Presign failed: ${presign.statusCode} ${presign.data}');
      }
      final d =
          presign.data is Map ? presign.data : jsonDecode(presign.data as String);
      final putUrl = d["url"] as String;
      final key = d["key"] as String;
      final publicUrl = d["public_url"] as String?;
      final signedHeaders = Map<String, dynamic>.from(d["headers"] ?? {});

      // 2) upload (fixed-length body; set Content-Length on non-web)
      _setStatus("Uploading…");
      final hdrs = <String, String>{
        ...signedHeaders.map((k, v) => MapEntry(k, '$v')),
      };
      if (!kIsWeb) {
        hdrs['Content-Length'] = dataBytes.length.toString();
      }

      await dio.put(
        putUrl,
        data: dataBytes, // NOT a stream → avoids 411 on B2
        options: Options(
          headers: hdrs,
          contentType: signedHeaders['Content-Type']?.toString(),
        ),
        onSendProgress: (sent, total) {
          final denom = total == -1 ? dataBytes.length : total;
          _setProgress(sent / (denom > 0 ? denom : dataBytes.length));
        },
      );

      // 3) update UI
      setState(() {
        _setProgress(1.0);
        _setStatus("✅ Uploaded");
        lastKey = key;
        lastPublicUrl = publicUrl;
      });

      // 4) save DB record
      final meetingId = meetingIdCtrl.text.trim().isEmpty
          ? "demo-meeting-1"
          : meetingIdCtrl.text.trim();
      await _recordUpload(
        meetingId: meetingId,
        key: key,
        filename: filename!,
        type: contentType!.startsWith('video') ? 'video' : 'audio',
        contentType: contentType,
        sizeBytes: size,
      );
      _toast("Upload saved • $filename");
    } catch (e) {
      _setStatus("❌ Upload error: $e");
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Clipnote Uploads")),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TextField(
              controller: meetingIdCtrl,
              decoration: const InputDecoration(
                labelText: "Meeting ID",
                hintText: "e.g., demo-meeting-1",
              ),
            ),
            const SizedBox(height: 16),
            LinearProgressIndicator(value: progress),
            const SizedBox(height: 8),
            Text(status),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: _pickAndUpload,
              icon: const Icon(Icons.upload_file),
              label: const Text("Pick & Upload"),
            ),
            const SizedBox(height: 24),
            if (lastKey != null) SelectableText("Key: $lastKey"),
            if (lastPublicUrl != null) SelectableText("Public: $lastPublicUrl"),
          ],
        ),
      ),
    );
  }
}

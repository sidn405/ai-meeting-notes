// ignore_for_file: constant_identifier_names

import 'dart:convert';
import 'dart:io' show File, RandomAccessFile; // not used on web
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';

/// Your deployed API base
const String API_BASE =
    "https://ai-meeting-notes-production-81d7.up.railway.app";

/// Switch to multipart for large files (desktop/mobile only)
const int kMultipartThreshold = 80 * 1024 * 1024; // 80 MB

class UploadScreen extends StatefulWidget {
  const UploadScreen({super.key, this.audioFile, this.prefillFilename});

  final File? audioFile;          // used on mobile/desktop
  final String? prefillFilename;  // optional display name
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

  void _setStatus(String s) => setState(() => status = s);
  void _setProgress(double p) => setState(() => progress = p.clamp(0, 1));

  @override
  void dispose() {
    meetingIdCtrl.dispose();
    super.dispose();
  }

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

    // If a file was provided (e.g., from record_screen), use it
    if (!kIsWeb && widget.audioFile != null) {
      final f = widget.audioFile!;
      filename = widget.prefillFilename ?? f.uri.pathSegments.last;
      bytes = await f.readAsBytes();
      contentType = _guessMime(filename);
    } else {
      // --- PICKER BRANCH (declare variables BEFORE use) ---
      final result = await FilePicker.platform.pickFiles(
        withData: kIsWeb,
        type: FileType.custom,
        allowedExtensions: ['mp3', 'm4a', 'wav', 'mp4'],
      );
      if (result == null || result.files.isEmpty) {
        _setStatus("Cancelled");
        return;
      }

      final picked = result.files.first;         // <-- declared BEFORE usage
      filename = picked.name;
      contentType = _guessMime(filename);

      if (kIsWeb) {
        bytes = picked.bytes!;
      } else {
        final fileLocal = File(picked.path!);    // <-- use a declared variable
        bytes = await fileLocal.readAsBytes();
      }
    }

    final size = bytes!.lengthInBytes;

    // Post-upload: save a DB record for this asset
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
        final m = ScaffoldMessenger.of(context);
        m.hideCurrentSnackBar();
        m.showSnackBar(
          SnackBar(content: Text("Saved file; server record failed: $e")),
        );
      }
    }


    // SIMPLE UPLOAD (fixed-length body; set Content-Length on non-web)
    try {
      _setStatus("Requesting presigned URL…");
      final presign = await dio.post(
        "$API_BASE/uploads/presign",
        data: {"filename": filename, "content_type": contentType, "folder": "raw"},
        options: Options(headers: {"Content-Type": "application/json"}),
      );
      if (presign.statusCode != 200) {
        throw Exception('Presign failed: ${presign.statusCode} ${presign.data}');
      }
      final data =
          presign.data is Map ? presign.data : jsonDecode(presign.data as String);
      final putUrl = data["url"] as String;
      final key = data["key"] as String;
      final headers = Map<String, dynamic>.from(data["headers"] ?? {});
      final publicUrl = data["public_url"] as String?;

      _setStatus("Uploading…");
      final hdrs = <String, String>{...headers.map((k, v) => MapEntry(k, '$v'))};
      if (!kIsWeb) {
        hdrs['Content-Length'] = bytes.length.toString();
      }

      await dio.put(
        putUrl,
        data: bytes, // not a stream
        options: Options(headers: hdrs, contentType: headers['Content-Type']?.toString()),
        onSendProgress: (sent, total) {
          final denom = total == -1 ? bytes!.length : total;
          _setProgress(sent / (denom > 0 ? denom : bytes!.length));
        },
      );

      setState(() {
        _setProgress(1.0);
        _setStatus("✅ Uploaded (simple)");
        lastKey = key;
        lastPublicUrl = publicUrl;
      });

      await dio.post(
        "$API_BASE/meetings/${meetingIdCtrl.text.trim().isEmpty ? "demo-meeting-1" : meetingIdCtrl.text.trim()}/assets",
        data: {
          "s3_key": key,
          "filename": filename,
          "type": contentType!.startsWith('video') ? 'video' : 'audio',
          "content_type": contentType,
          "size_bytes": size,
        },
        options: Options(headers: {"Content-Type": "application/json"}),
      );
      _toast("Upload saved • $filename");
    } catch (e) {
      _setStatus("❌ Simple upload error: $e");
    }
  }


  // ---- MULTIPART UPLOAD (desktop/mobile only) ------------------------------

  Future<void> _uploadMultipart(
      File file, String filename, String contentType, int size) async {
    if (kIsWeb) {
      _toast("Large uploads via browser not supported here. Use desktop/mobile.");
      return;
    }

    RandomAccessFile? raf;
    try {
      _setStatus("Starting multipart…");
      final startRes = await dio.post(
        "$API_BASE/uploads/multipart/start",
        data: {"filename": filename, "content_type": contentType, "folder": "raw"},
        options: Options(headers: {"Content-Type": "application/json"}),
      );
      if (startRes.statusCode != 200) {
        throw Exception('Start failed: ${startRes.statusCode} ${startRes.data}');
      }
      final s =
          startRes.data is Map ? startRes.data : jsonDecode(startRes.data as String);
      final key = s["key"] as String;
      final uploadId = s["upload_id"] as String;
      final partSize = (s["part_size"] as num).toInt();

      raf = await file.open();
      final parts = <Map<String, dynamic>>[];
      int partNum = 1;
      int offset = 0;
      int sentTotal = 0;

      while (offset < size) {
        final remaining = size - offset;
        final chunkSize = remaining < partSize ? remaining : partSize;
        await raf.setPosition(offset);
        final bytes = await raf.read(chunkSize);

        _setStatus("Part $partNum presign…");
        final pUrlRes = await dio.post(
          "$API_BASE/uploads/multipart/part-url",
          data: {"key": key, "upload_id": uploadId, "part_number": partNum},
          options: Options(headers: {"Content-Type": "application/json"}),
        );
        if (pUrlRes.statusCode != 200) {
          throw Exception('part-url failed: ${pUrlRes.statusCode} ${pUrlRes.data}');
        }
        final url = (pUrlRes.data is Map
                ? pUrlRes.data["url"]
                : jsonDecode(pUrlRes.data as String)["url"])
            as String;

        _setStatus("Part $partNum uploading…");
        final resp = await dio.put(
          url,
          data: bytes, // fixed-length body per part
          options: Options(headers: {
            'Content-Length': bytes.length.toString(), // avoids 411 on B2
          }),
        );
        final eTag =
            (resp.headers["etag"]?.first ?? resp.headers.value("etag") ?? "")
                .replaceAll('"', '');

        parts.add({"ETag": eTag, "PartNumber": partNum});
        offset += chunkSize;
        sentTotal += chunkSize;
        _setProgress(sentTotal / size);
        partNum++;
      }

      _setStatus("Completing multipart…");
      final done = await dio.post(
        "$API_BASE/uploads/multipart/complete",
        data: {"key": key, "upload_id": uploadId, "parts": parts},
        options: Options(headers: {"Content-Type": "application/json"}),
      );
      if (done.statusCode != 200) {
        throw Exception('complete failed: ${done.statusCode} ${done.data}');
      }
      final d = done.data is Map ? done.data : jsonDecode(done.data as String);

      setState(() {
        _setProgress(1.0);
        _setStatus("✅ Uploaded (multipart)");
        lastKey = key;
        lastPublicUrl = d["public_url"] as String?;
      });

      await _recordUpload(
        meetingId: meetingIdCtrl.text.trim().isEmpty
            ? "demo-meeting-1"
            : meetingIdCtrl.text.trim(),
        key: key,
        filename: filename,
        type: contentType.startsWith('video') ? 'video' : 'audio',
        contentType: contentType,
        sizeBytes: size,
      );
      _toast("Upload saved • $filename");
    } catch (e) {
      _setStatus("❌ Multipart error: $e");
    } finally {
      await raf?.close();
    }
  }

  // ---- helpers --------------------------------------------------------------

  String _guessMime(String name) {
    final n = name.toLowerCase();
    if (n.endsWith('.mp3')) return 'audio/mpeg';
    if (n.endsWith('.m4a')) return 'audio/mp4'; // m4a => audio/mp4
    if (n.endsWith('.wav')) return 'audio/wav';
    if (n.endsWith('.mp4')) return 'video/mp4';
    return 'application/octet-stream';
  }

  void _toast(String msg) {
    final messenger = ScaffoldMessenger.of(context);
    messenger.hideCurrentSnackBar();
    messenger.showSnackBar(SnackBar(content: Text(msg)));
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
            const SizedBox(height: 12),
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

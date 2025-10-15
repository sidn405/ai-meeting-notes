// lib/upload_screen.dart
import 'dart:convert';
import 'dart:io';
import 'package:dio/dio.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
// ignore_for_file: constant_identifier_names

// Your deployed API base
const String API_BASE =
    "https://ai-meeting-notes-production-81d7.up.railway.app";

// Switch to multipart for large files (bytes)
const int kMultipartThreshold = 80 * 1024 * 1024; // 80 MB

class UploadScreen extends StatefulWidget {
  const UploadScreen({super.key});
  @override
  State<UploadScreen> createState() => _UploadScreenState();
}

class _UploadScreenState extends State<UploadScreen> {
  final dio = Dio(BaseOptions(connectTimeout: const Duration(seconds: 30)));
  double progress = 0.0;
  String status = 'Idle';
  String? lastKey;
  String? lastPublicUrl;

  void _setStatus(String s) => setState(() => status = s);
  void _setProgress(double p) => setState(() => progress = p.clamp(0, 1));

  Future<void> _pickAndUpload() async {
    setState(() {
      progress = 0;
      status = "Picking file…";
      lastKey = null;
      lastPublicUrl = null;
    });

    final result = await FilePicker.platform.pickFiles(
      withData: false,
      type: FileType.custom,
      allowedExtensions: ['mp3', 'm4a', 'wav', 'mp4'],
    );
    if (result == null || result.files.isEmpty) {
      _setStatus("Cancelled");
      return;
    }

    final picked = result.files.first;
    final filePath = picked.path!;
    final file = File(filePath);
    final filename = picked.name;
    final contentType = _guessMime(filename);
    final size = await file.length();

    if (size >= kMultipartThreshold) {
      await _uploadMultipart(file, filename, contentType, size);
    } else {
      await _uploadSimple(file, filename, contentType, size);
    }
  }

  Future<void> _uploadSimple(
      File file, String filename, String contentType, int size) async {
    try {
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
      final data =
          presign.data is Map ? presign.data : jsonDecode(presign.data as String);
      final putUrl = data["url"] as String;
      final key = data["key"] as String;
      final headers = Map<String, dynamic>.from(data["headers"] ?? {});
      final publicUrl = data["public_url"] as String?;

      _setStatus("Uploading…");
      // For <= 80MB we can safely load into memory
      int sent = 0;
      final bytes = await file.readAsBytes();     // load whole file
      await dio.put(
        putUrl,
        data: bytes,                              // not a Stream
        options: Options(
            headers: {
            ...Map<String, String>.from(headers.map((k, v) => MapEntry(k, '$v'))),
            'Content-Length': bytes.length.toString(),  // <-- required for B2
            },
            contentType: headers['Content-Type']?.toString(),
        ),
        onSendProgress: (sent, total) => _setProgress(sent / (total == -1 ? bytes.length : total)),
        );

      setState(() {
        _setProgress(1.0);
        _setStatus("✅ Uploaded (simple)");
        lastKey = key;
        lastPublicUrl = publicUrl;
      });
    } catch (e) {
      _setStatus("❌ Simple upload error: $e");
    }
  }

  Future<void> _uploadMultipart(
      File file, String filename, String contentType, int size) async {
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
            data: bytes,
            options: Options(headers: {
                'Content-Length': bytes.length.toString(),    // <-- important
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
    } catch (e) {
      _setStatus("❌ Multipart error: $e");
    } finally {
      await raf?.close();
    }
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
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Clipnote Uploads")),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
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

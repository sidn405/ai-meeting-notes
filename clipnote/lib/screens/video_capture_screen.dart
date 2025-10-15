// lib/video_capture_screen.dart
// Records a short video and uploads via your presign flow,
// then saves a DB record under /meetings/{id}/assets.

import 'dart:convert';
import 'dart:typed_data';
import 'dio/dio.dart';
import 'flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'image_picker/image_picker.dart';
import 'permission_handler/permission_handler.dart';

const String API_BASE = "https://ai-meeting-notes-production-81d7.up.railway.app";

class VideoCaptureScreen extends StatefulWidget {
  const VideoCaptureScreen({super.key});
  @override
  State<VideoCaptureScreen> createState() => _VideoCaptureScreenState();
}

class _VideoCaptureScreenState extends State<VideoCaptureScreen> {
  final dio = Dio(BaseOptions(connectTimeout: const Duration(seconds: 30)));
  final meetingIdCtrl = TextEditingController(text: "demo-meeting-1");
  final _picker = ImagePicker();

  double progress = 0;
  String status = "Idle";
  String? lastKey;
  String? lastPublicUrl;

  void _setStatus(String s) => setState(() => status = s);
  void _setProgress(double p) => setState(() => progress = p.clamp(0, 1));

  @override
  void dispose() {
    meetingIdCtrl.dispose();
    super.dispose();
  }

  Future<void> _recordAndUpload() async {
    // 1) Ask for permissions
    if (!(await _ensurePerms())) return;

    try {
      _setStatus("Opening camera…");
      // 2) Record video (maxDuration tweak as you like)
      final XFile? video = await _picker.pickVideo(
        source: ImageSource.camera,
        maxDuration: const Duration(minutes: 2),
      );
      if (video == null) {
        _setStatus("Cancelled");
        return;
      }

      // 3) Read bytes (mp4)
      final Uint8List bytes = await video.readAsBytes();
      final filename = _ensureMp4Ext(video.name);
      const contentType = "video/mp4";

      // 4) Presign
      _setStatus("Requesting presigned URL…");
      final presign = await dio.post(
        "$API_BASE/uploads/presign",
        data: {
          "filename": filename,
          "content_type": contentType,
          "folder": "raw",
        },
        options: Options(headers: {"Content-Type": "application/json"}),
      );
      if (presign.statusCode != 200) {
        throw Exception("Presign failed: ${presign.statusCode} ${presign.data}");
      }
      final data =
          presign.data is Map ? presign.data : jsonDecode(presign.data as String);
      final putUrl = data["url"] as String;
      final key = data["key"] as String;
      final headers = Map<String, dynamic>.from(data["headers"] ?? {});
      final publicUrl = data["public_url"] as String?;

      // 5) PUT (fixed-length body → avoids 411 on Backblaze)
      _setStatus("Uploading video…");
      final hdrs = <String, String>{
        ...headers.map((k, v) => MapEntry(k, '$v')),
      };
      if (!kIsWeb) {
        // Browsers set Content-Length automatically; native must set it explicitly.
        hdrs['Content-Length'] = bytes.length.toString();
      }
      await dio.put(
        putUrl,
        data: bytes, // NOT a stream; fixed length
        options: Options(headers: hdrs, contentType: headers['Content-Type']),
        onSendProgress: (sent, total) {
          final denom = total == -1 ? bytes.length : total;
          _setProgress(sent / (denom > 0 ? denom : bytes.length));
        },
      );

      // 6) Record asset in DB
      _setStatus("Saving record…");
      final meetingId = meetingIdCtrl.text.trim().isEmpty
          ? "demo-meeting-1"
          : meetingIdCtrl.text.trim();
      await dio.post(
        "$API_BASE/meetings/$meetingId/assets",
        data: {
          "s3_key": key,
          "filename": filename,
          "type": "video",
          "content_type": contentType,
          "size_bytes": bytes.length,
        },
        options: Options(headers: {"Content-Type": "application/json"}),
      );

      setState(() {
        lastKey = key;
        lastPublicUrl = publicUrl;
        _setProgress(1);
        _setStatus("✅ Uploaded & saved");
      });
      _toast("Video uploaded • $filename");
    } catch (e) {
      _setStatus("❌ Error: $e");
      _toast("Upload failed: $e");
    }
  }

  // Permissions: camera + microphone (+ read media)
  Future<bool> _ensurePerms() async {
    final req = await [
      Permission.camera,
      Permission.microphone,
      // These map to READ_MEDIA_* or READ_EXTERNAL_STORAGE as needed
      Permission.videos,
      Permission.audio,
    ].request();

    final ok = req.values.every((r) => r.isGranted);
    if (!ok) {
      _toast("Camera/Microphone permissions are required.");
    }
    return ok;
    // If you want to send users to settings on denial:
    // if (!ok) { await openAppSettings(); }
  }

  String _ensureMp4Ext(String name) =>
      name.toLowerCase().endsWith('.mp4') ? name : '$name.mp4';

  void _toast(String msg) {
    final m = ScaffoldMessenger.of(context);
    m.hideCurrentSnackBar();
    m.showSnackBar(SnackBar(content: Text(msg)));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Record & Upload Video")),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
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
            Align(
              alignment: Alignment.centerLeft,
              child: Text(status),
            ),
            const Spacer(),
            ElevatedButton.icon(
              onPressed: _recordAndUpload,
              icon: const Icon(Icons.videocam),
              label: const Text("Record & Upload"),
            ),
            const SizedBox(height: 12),
            if (lastKey != null) SelectableText("Key: $lastKey"),
            if (lastPublicUrl != null) SelectableText("Public: $lastPublicUrl"),
          ],
        ),
      ),
    );
  }
}

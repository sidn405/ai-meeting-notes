// lib/screens/upload_screen.dart
import 'dart:typed_data';
import 'dart:io' show File;
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import 'package:clipnote/services/api_service.dart';

class UploadScreen extends StatefulWidget {
  const UploadScreen({super.key, this.audioFile, this.prefillFilename});
  final File? audioFile;          // optional pre-provided file (mobile/desktop)
  final String? prefillFilename;  // optional name for provided file

  @override
  State<UploadScreen> createState() => _UploadScreenState();
}

class _UploadScreenState extends State<UploadScreen> {
  final api = ApiService.instance;

  final meetingIdCtrl = TextEditingController(text: "demo-meeting-1");
  final s3KeyCtrl = TextEditingController();
  final transcriptCtrl = TextEditingController();

  double progress = 0;
  String status = "Idle";
  String? lastKey;
  String? lastPublicUrl;
  bool showTranscriptBox = false;

  @override
  void dispose() {
    meetingIdCtrl.dispose();
    s3KeyCtrl.dispose();
    transcriptCtrl.dispose();
    super.dispose();
  }

  // ---------- helpers ----------
  void _setStatus(String s) => setState(() => status = s);
  void _setProgress(double p) => setState(() => progress = p.clamp(0, 1));

  String _guessMime(String name) {
    final n = name.toLowerCase();
    if (n.endsWith('.mp3')) return 'audio/mpeg';
    if (n.endsWith('.m4a')) return 'audio/mp4';
    if (n.endsWith('.wav')) return 'audio/wav';
    if (n.endsWith('.mp4')) return 'video/mp4';
    return 'application/octet-stream';
  }

  String _meetingId() {
    final v = meetingIdCtrl.text.trim();
    return v.isEmpty ? "demo-meeting-1" : v;
  }

  void _toast(String msg) {
    final m = ScaffoldMessenger.of(context);
    m.hideCurrentSnackBar();
    m.showSnackBar(SnackBar(content: Text(msg)));
  }

  // ---------- flows ----------
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

    if (!kIsWeb && widget.audioFile != null) {
      final f = widget.audioFile!;
      filename = widget.prefillFilename ?? f.uri.pathSegments.last;
      bytes = await f.readAsBytes();
      contentType = _guessMime(filename);
    } else {
      final result = await FilePicker.platform.pickFiles(
        withData: kIsWeb,
        type: FileType.custom,
        allowedExtensions: ['mp3', 'm4a', 'wav', 'mp4'],
      );
      if (result == null || result.files.isEmpty) {
        _setStatus("Cancelled");
        return;
      }
      final picked = result.files.first;
      filename = picked.name;
      contentType = _guessMime(filename);
      if (kIsWeb) {
        bytes = picked.bytes!;
      } else {
        final fileLocal = File(picked.path!);
        bytes = await fileLocal.readAsBytes();
      }
    }

    final dataBytes = bytes!;
    final size = dataBytes.length;

    try {
      _setStatus("Requesting presigned URL…");
      final signed = await api.presignUpload(
        filename: filename!,
        contentType: contentType!,
      );

      _setStatus("Uploading…");
      await api.putBytes(
        putUrl: signed.putUrl,
        bytes: dataBytes,
        headers: signed.headers,
      );

      setState(() {
        progress = 1;
        status = "✅ Uploaded";
        lastKey = signed.key;
        lastPublicUrl = signed.publicUrl;
      });

      await api.recordAsset(
        meetingId: _meetingId(),
        s3Key: signed.key,
        filename: filename,
        type: contentType.startsWith('video') ? 'video' : 'audio',
        contentType: contentType,
        sizeBytes: size,
      );

      _toast("Upload saved • $filename");
    } catch (e) {
      _setStatus("❌ Upload error: $e");
    }
  }

  Future<void> _process({required bool summarize}) async {
    final key = lastKey ?? s3KeyCtrl.text.trim();
    if (key.isEmpty) {
      _toast("Paste an S3 key or upload a file first.");
      return;
    }
    try {
      _setStatus(summarize ? "Starting transcribe + summarize…" : "Starting transcription…");
      await api.startProcessing(
        meetingId: _meetingId(),
        s3Key: key,
        summarize: summarize,
      );
      _toast("Processing started");
      _setStatus("Processing started");
    } catch (e) {
      _setStatus("❌ Failed to start processing: $e");
    }
  }

  Future<void> _submitTranscript({required bool summarize}) async {
    final txt = transcriptCtrl.text.trim();
    if (txt.isEmpty) {
      _toast("Paste or type a transcript first.");
      return;
    }
    try {
      _setStatus(summarize ? "Submitting transcript + summarize…" : "Submitting transcript…");
      await api.submitTranscript(
        meetingId: _meetingId(),
        transcript: txt,
        summarize: summarize,
      );
      _toast("Transcript submitted");
      _setStatus("Transcript submitted");
    } catch (e) {
      _setStatus("❌ Transcript submit failed: $e");
    }
  }

  // ---------- UI ----------
  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;

    Widget card(Widget child) => Container(
          decoration: BoxDecoration(
            color: cs.surface.withOpacity(0.9),
            borderRadius: BorderRadius.circular(20),
            boxShadow: [
              BoxShadow(
                color: cs.shadow.withOpacity(0.06),
                blurRadius: 24,
                offset: const Offset(0, 8),
              )
            ],
            border: Border.all(color: cs.outlineVariant, width: 1),
          ),
          padding: const EdgeInsets.all(16),
          child: child,
        );

    final hasProcessKey =
        (lastKey?.isNotEmpty ?? false) || s3KeyCtrl.text.trim().isNotEmpty;

    return Scaffold(
      appBar: AppBar(
        title: const Text("Uploads"),
        elevation: 0,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            // Header
            card(Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  "Clipnote Uploads",
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                ),
                const SizedBox(height: 8),
                Text(
                  "Pick a file to upload, or paste an S3 key. Then transcribe or summarize.",
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: meetingIdCtrl,
                  decoration: const InputDecoration(
                    labelText: "Meeting ID",
                    hintText: "e.g., demo-meeting-1",
                  ),
                ),
                const SizedBox(height: 12),
                LinearProgressIndicator(value: progress),
                const SizedBox(height: 6),
                Text(status),
              ],
            )),

            const SizedBox(height: 16),

            // Upload from device
            card(Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  "Upload from device",
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                ),
                const SizedBox(height: 10),
                FilledButton.icon(
                  onPressed: _pickAndUpload,
                  icon: const Icon(Icons.upload_file),
                  label: const Text("Pick & Upload"),
                ),
                if (lastKey != null) ...[
                  const SizedBox(height: 8),
                  SelectableText(
                    "Uploaded key: $lastKey",
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                  if (lastPublicUrl != null)
                    SelectableText(
                      "Public URL: $lastPublicUrl",
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                ],
              ],
            )),

            const SizedBox(height: 16),

            // Use existing key + process
            card(Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  "Process existing upload",
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                ),
                const SizedBox(height: 10),
                TextField(
                  controller: s3KeyCtrl,
                  decoration: const InputDecoration(
                    labelText: "Paste S3 key",
                    hintText: "e.g., raw/123456_file.m4a",
                  ),
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: FilledButton(
                        onPressed: hasProcessKey ? () => _process(summarize: false) : null,
                        child: const Text("Transcribe only"),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: FilledButton.tonal(
                        onPressed: hasProcessKey ? () => _process(summarize: true) : null,
                        child: const Text("Transcribe & Summarize"),
                      ),
                    ),
                  ],
                ),
              ],
            )),

            const SizedBox(height: 16),

            // From transcript (no audio)
            card(Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  children: [
                    Text(
                      "From transcript (no audio)",
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.w600,
                          ),
                    ),
                    const Spacer(),
                    Switch(
                      value: showTranscriptBox,
                      onChanged: (v) => setState(() => showTranscriptBox = v),
                    ),
                  ],
                ),
                AnimatedCrossFade(
                  duration: const Duration(milliseconds: 180),
                  crossFadeState: showTranscriptBox
                      ? CrossFadeState.showFirst
                      : CrossFadeState.showSecond,
                  firstChild: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      const SizedBox(height: 8),
                      TextField(
                        controller: transcriptCtrl,
                        minLines: 4,
                        maxLines: 12,
                        decoration: const InputDecoration(
                          labelText: "Paste transcript",
                          alignLabelWithHint: true,
                        ),
                      ),
                      const SizedBox(height: 12),
                      Row(
                        children: [
                          Expanded(
                            child: OutlinedButton(
                              onPressed: () => _submitTranscript(summarize: false),
                              child: const Text("Transcribe only"),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: OutlinedButton(
                              onPressed: () => _submitTranscript(summarize: true),
                              child: const Text("Transcribe & Summarize"),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                  secondChild: const SizedBox.shrink(),
                ),
              ],
            )),
          ],
        ),
      ),
    );
  }
}

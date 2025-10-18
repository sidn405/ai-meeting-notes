import 'dart:typed_data';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import '../services/api_service.dart';
import 'progress_screen.dart';

class UploadScreen extends StatefulWidget {
  const UploadScreen({super.key});

  @override
  State<UploadScreen> createState() => _UploadScreenState();
}

class _UploadScreenState extends State<UploadScreen> {
  final api = ApiService.I;

  final _meetingId = TextEditingController(text: 'demo-meeting-1');
  final _titleCtrl = TextEditingController();
  final _transcriptCtrl = TextEditingController();
  bool _busy = false;
  String? _lastKey;
  String? _publicUrl;

  @override
  void dispose() {
    _meetingId.dispose();
    _titleCtrl.dispose();
    _transcriptCtrl.dispose();
    super.dispose();
  }

  // ---------- UI ----------
  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Upload')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 28),
        children: [
          Text('Pick a file to upload', style: t.textTheme.titleLarge),
          const SizedBox(height: 12),

          // From transcript (no audio)
          _outlinedButton(
            context,
            icon: Icons.description_outlined,
            label: 'From transcript (no audio)',
            onPressed: _showTranscriptDialog,
          ),
          const SizedBox(height: 16),

          // Choose audio/video & upload
          _filledButton(
            context,
            icon: Icons.upload_rounded,
            label: 'Choose audio/video & upload',
            onPressed: _busy ? null : _pickAndUpload,
          ),

          if (_busy) ...[
            const SizedBox(height: 16),
            const LinearProgressIndicator(),
          ],

          if (_lastKey != null) ...[
            const SizedBox(height: 20),
            Text('Uploaded S3 key:', style: t.textTheme.titleMedium),
            const SizedBox(height: 6),
            SelectableText(_lastKey!),
            if (_publicUrl != null) ...[
              const SizedBox(height: 12),
              Text('Public URL:', style: t.textTheme.titleMedium),
              const SizedBox(height: 6),
              SelectableText(_publicUrl!),
            ],
            const SizedBox(height: 16),
            _filledButton(
              context,
              icon: Icons.play_arrow_rounded,
              label: 'Start processing (transcribe & summarize)',
              onPressed: () async {
                if (_lastKey == null) return;
                await api.startProcessing(
                  meetingId: _meetingId.text.trim(),
                  s3key: _lastKey!,
                  mode: 'transcribe_and_summarize',
                );
                if (!mounted) return;
                Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (_) =>
                        ProgressScreen(meetingId: _meetingId.text.trim()),
                  ),
                );
              },
            ),
          ],
        ],
      ),
    );
  }

  // ---------- Actions ----------
  Future<void> _pickAndUpload() async {
    setState(() => _busy = true);
    try {
      final result = await FilePicker.platform.pickFiles(
        allowMultiple: false,
        withData: true,
        type: FileType.custom,
        allowedExtensions: const [
          'm4a',
          'mp3',
          'wav',
          'aac',
          'mp4',
          'mov',
          'mkv',
          'webm'
        ],
      );
      if (result == null || result.files.single.bytes == null) {
        setState(() => _busy = false);
        return;
      }

      final PlatformFile file = result.files.single;
      final Uint8List bytes = file.bytes!;
      final filename = file.name;
      final contentType = _guessMime(filename);

      final presign = await api.presignUpload(
        filename: filename,
        contentType: contentType,
        folder: 'raw',
      );

      await api.putBytes(
        url: presign.url,
        bytes: bytes,
        headers: presign.headers ?? const {},
        method: presign.method ?? 'PUT',
      );

      await api.recordAsset(
        meetingId: _meetingId.text.trim(),
        key: presign.key,
        publicUrl: presign.publicUrl,
      );

      setState(() {
        _lastKey = presign.key;
        _publicUrl = presign.publicUrl;
      });
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _showTranscriptDialog() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (c) {
        final bottom = MediaQuery.of(c).viewInsets.bottom;
        return Padding(
          padding: EdgeInsets.fromLTRB(16, 8, 16, bottom + 16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: _titleCtrl,
                textInputAction: TextInputAction.next,
                decoration: const InputDecoration(
                  labelText: 'Title (optional)',
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _transcriptCtrl,
                maxLines: 8,
                decoration: const InputDecoration(
                  labelText: 'Paste transcript text',
                  alignLabelWithHint: true,
                ),
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: FilledButton.tonal(
                      onPressed: () async {
                        await api.submitTranscript(
                          meetingId: _meetingId.text.trim(),
                          title: _titleCtrl.text.trim().isEmpty
                              ? null
                              : _titleCtrl.text.trim(),
                          transcript: _transcriptCtrl.text,
                          summarize: false,
                        );
                        if (!mounted) return;
                        Navigator.pop(c);
                        Navigator.of(context).push(
                          MaterialPageRoute(
                            builder: (_) =>
                                ProgressScreen(meetingId: _meetingId.text),
                          ),
                        );
                      },
                      child: const Text('Transcribe only'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: FilledButton(
                      onPressed: () async {
                        await api.submitTranscript(
                          meetingId: _meetingId.text.trim(),
                          title: _titleCtrl.text.trim().isEmpty
                              ? null
                              : _titleCtrl.text.trim(),
                          transcript: _transcriptCtrl.text,
                          summarize: true,
                        );
                        if (!mounted) return;
                        Navigator.pop(c);
                        Navigator.of(context).push(
                          MaterialPageRoute(
                            builder: (_) =>
                                ProgressScreen(meetingId: _meetingId.text),
                          ),
                        );
                      },
                      child: const Text('Transcribe & Summarize'),
                    ),
                  ),
                ],
              ),
            ],
          ),
        );
      },
    );
  }

  // ---------- Helpers ----------
  String _guessMime(String filename) {
    final f = filename.toLowerCase();
    if (f.endsWith('.m4a')) return 'audio/m4a';
    if (f.endsWith('.mp3')) return 'audio/mpeg';
    if (f.endsWith('.wav')) return 'audio/wav';
    if (f.endsWith('.aac')) return 'audio/aac';
    if (f.endsWith('.mp4')) return 'video/mp4';
    if (f.endsWith('.mov')) return 'video/quicktime';
    if (f.endsWith('.mkv')) return 'video/x-matroska';
    if (f.endsWith('.webm')) return 'video/webm';
    return 'application/octet-stream';
  }

  Widget _outlinedButton(BuildContext context,
      {required IconData icon,
      required String label,
      required VoidCallback onPressed}) {
    final scheme = Theme.of(context).colorScheme;
    return SizedBox(
      height: 56,
      child: OutlinedButton.icon(
        onPressed: onPressed,
        icon: Icon(icon),
        label: Text(label),
        style: OutlinedButton.styleFrom(
          foregroundColor: scheme.primary,
          side: BorderSide(color: scheme.outlineVariant),
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(28)),
          textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
        ),
      ),
    );
  }

  Widget _filledButton(BuildContext context,
      {required IconData icon,
      required String label,
      required VoidCallback? onPressed}) {
    final scheme = Theme.of(context).colorScheme;
    return SizedBox(
      height: 56,
      child: ElevatedButton.icon(
        onPressed: onPressed,
        icon: Icon(icon),
        label: Text(label),
        style: ElevatedButton.styleFrom(
          backgroundColor: scheme.primary,
          foregroundColor: scheme.onPrimary,
          disabledBackgroundColor: scheme.primary.withOpacity(.4),
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(28)),
          textStyle: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
        ),
      ),
    );
  }
}

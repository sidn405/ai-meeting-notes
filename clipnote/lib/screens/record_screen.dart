// lib/screens/record_screen.dart
import 'dart:io';

import 'package:flutter/material.dart';
import '../services/audio_service.dart';
import 'upload_screen.dart' as up; // 👈 prefix import guarantees we use THIS file's class

class RecordScreen extends StatefulWidget {
  const RecordScreen({super.key});

  @override
  State<RecordScreen> createState() => _RecordScreenState();
}

class _RecordScreenState extends State<RecordScreen> {
  final AudioService _audio = AudioService();
  bool _isRecording = false;
  String? _lastPath;

  @override
  void dispose() {
    _audio.dispose();
    super.dispose();
  }

  Future<void> _start() async {
    try {
      final path = await _audio.start();
      if (path == null) {
        _snack("Recording not available on this platform.");
        return;
      }
      setState(() {
        _isRecording = true;
        _lastPath = path;
      });
    } catch (e) {
      _snack("Failed to start: $e");
    }
  }

  Future<void> _stopAndSend() async {
    try {
      final path = await _audio.stop();
      if (path == null) {
        _snack("No recording produced.");
        setState(() => _isRecording = false);
        return;
      }
      setState(() {
        _isRecording = false;
        _lastPath = path;
      });

      // Navigate to UploadScreen with the recorded file
      if (mounted) {
        Navigator.of(context).push(
          MaterialPageRoute(
            builder: (_) => up.UploadScreen(
              audioFile: File(path),
              prefillFilename: File(path).uri.pathSegments.last,
            ),
          ),
        );
      }
    } catch (e) {
      _snack("Failed to stop: $e");
      setState(() => _isRecording = false);
    }
  }

  void _snack(String msg) {
    final m = ScaffoldMessenger.of(context);
    m.hideCurrentSnackBar();
    m.showSnackBar(SnackBar(content: Text(msg)));
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Record')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Card(
              elevation: 1,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  children: [
                    Text(
                      _isRecording ? "Recording…" : "Ready",
                      style: theme.textTheme.titleMedium,
                    ),
                    const SizedBox(height: 8),
                    if (_lastPath != null)
                      Text(
                        "Last: ${_lastPath!}",
                        style: theme.textTheme.bodySmall,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),
            if (!_isRecording)
              FilledButton.icon(
                onPressed: _start,
                icon: const Icon(Icons.fiber_manual_record),
                label: const Text("Start recording"),
              )
            else
              FilledButton.icon(
                onPressed: _stopAndSend,
                icon: const Icon(Icons.stop_circle_outlined),
                label: const Text("Stop & send to Upload"),
              ),
          ],
        ),
      ),
    );
  }
}

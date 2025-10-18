import 'dart:io';
import 'package:flutter/material.dart';
import '../services/audio_service.dart';
import 'upload_screen.dart';

class RecordScreen extends StatefulWidget {
  const RecordScreen({super.key});

  @override
  State<RecordScreen> createState() => _RecordScreenState();
}

class _RecordScreenState extends State<RecordScreen> {
  final AudioService _audio = AudioService();
  bool _isRecording = false;
  String? _lastPath;
  Duration _recordingDuration = Duration.zero;

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
        _recordingDuration = Duration.zero;
      });
      
      // Start duration timer
      _startDurationTimer();
    } catch (e) {
      _snack("Failed to start: $e");
    }
  }

  void _startDurationTimer() {
    Future.delayed(const Duration(seconds: 1), () {
      if (_isRecording && mounted) {
        setState(() {
          _recordingDuration = _recordingDuration + const Duration(seconds: 1);
        });
        _startDurationTimer();
      }
    });
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

      if (mounted) {
        Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => const UploadScreen()),
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

  String _formatDuration(Duration duration) {
    String twoDigits(int n) => n.toString().padLeft(2, '0');
    final minutes = twoDigits(duration.inMinutes.remainder(60));
    final seconds = twoDigits(duration.inSeconds.remainder(60));
    return '$minutes:$seconds';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: Colors.white),
          onPressed: () => Navigator.of(context).pop(),
        ),
        title: const Text(
          'Record',
          style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
        ),
        centerTitle: true,
      ),
      extendBodyBehindAppBar: true,
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [Color(0xFF667eea), Color(0xFF764ba2)],
          ),
        ),
        child: SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const SizedBox(height: 40),
                
                // Recording Status
                Container(
                  padding: const EdgeInsets.all(24),
                  decoration: BoxDecoration(
                    color: Colors.white.withOpacity(0.15),
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(
                      color: Colors.white.withOpacity(0.3),
                      width: 1,
                    ),
                  ),
                  child: Column(
                    children: [
                      Icon(
                        _isRecording ? Icons.fiber_manual_record : Icons.mic,
                        size: 60,
                        color: _isRecording ? Colors.red : Colors.white,
                      ),
                      const SizedBox(height: 16),
                      Text(
                        _isRecording ? "Recording..." : "Ready",
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 24,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      if (_isRecording) ...[
                        const SizedBox(height: 8),
                        Text(
                          _formatDuration(_recordingDuration),
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 32,
                            fontWeight: FontWeight.w300,
                            fontFeatures: [FontFeature.tabularFigures()],
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
                
                const Spacer(),
                
                if (_lastPath != null && !_isRecording)
                  Container(
                    padding: const EdgeInsets.all(16),
                    margin: const EdgeInsets.only(bottom: 16),
                    decoration: BoxDecoration(
                      color: Colors.white.withOpacity(0.15),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                        color: Colors.white.withOpacity(0.3),
                        width: 1,
                      ),
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.check_circle, color: Colors.white, size: 20),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Text(
                            "Last recording saved",
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 14,
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ],
                    ),
                  ),
                
                if (!_isRecording)
                  SizedBox(
                    height: 56,
                    child: ElevatedButton.icon(
                      onPressed: _start,
                      icon: const Icon(Icons.fiber_manual_record),
                      label: const Text(
                        "Start Recording",
                        style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
                      ),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.red,
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                      ),
                    ),
                  )
                else
                  SizedBox(
                    height: 56,
                    child: ElevatedButton.icon(
                      onPressed: _stopAndSend,
                      icon: const Icon(Icons.stop_circle_outlined),
                      label: const Text(
                        "Stop & Upload",
                        style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
                      ),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.white,
                        foregroundColor: const Color(0xFF667eea),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
import 'package:flutter/material.dart';
import 'package:clipnote/services/api_service.dart';
import 'package:clipnote/screens/transcript_screen.dart';
import 'package:clipnote/screens/results_screen.dart';
import 'dart:async';

class ProgressScreen extends StatefulWidget {
  final int meetingId;

  const ProgressScreen({
    super.key,
    required this.meetingId,
  });

  @override
  State<ProgressScreen> createState() => _ProgressScreenState();
}

class _ProgressScreenState extends State<ProgressScreen> {
  final _apiService = ApiService.I;
  Timer? _pollTimer;
  
  String _status = 'queued';
  int _progress = 0;
  String _step = 'Starting...';
  bool _hasError = false;
  bool _hasTranscript = false;
  bool _hasSummary = false;

  @override
  void initState() {
    super.initState();
    _startPolling();
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }

  void _startPolling() {
    _pollStatus();
    _pollTimer = Timer.periodic(const Duration(seconds: 2), (_) => _pollStatus());
  }

  Future<void> _pollStatus() async {
    try {
      final status = await _apiService.getMeetingStatus(widget.meetingId);
      
      if (!mounted) return;
      
      setState(() {
        _status = status['status'] ?? 'unknown';
        _progress = status['progress'] ?? 0;
        _step = status['step'] ?? 'Processing...';
        _hasError = _status == 'failed';
        _hasTranscript = status['has_transcript'] ?? false;
        _hasSummary = status['has_summary'] ?? false;
      });

      // Stop polling when done or failed
      if (_status == 'delivered' || _status == 'failed') {
        _pollTimer?.cancel();
      }
    } catch (e) {
      print('Error polling status: $e');
      if (!mounted) return;
      
      setState(() {
        _hasError = true;
        _step = 'Error checking status';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return WillPopScope(
      onWillPop: () async {
        // Allow back button navigation
        return true;
      },
      child: Scaffold(
        appBar: AppBar(
          backgroundColor: Colors.transparent,
          elevation: 0,
          leading: IconButton(
            icon: const Icon(Icons.arrow_back, color: Colors.white),
            onPressed: () => Navigator.of(context).pop(),
          ),
          title: const Text(
            'Processing Meeting',
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
            child: Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    // Progress indicator
                    if (_hasError)
                      Container(
                        padding: const EdgeInsets.all(24),
                        decoration: BoxDecoration(
                          color: Colors.red.withOpacity(0.2),
                          shape: BoxShape.circle,
                        ),
                        child: const Icon(
                          Icons.error_outline,
                          size: 80,
                          color: Colors.white,
                        ),
                      )
                    else if (_status == 'delivered')
                      Container(
                        padding: const EdgeInsets.all(24),
                        decoration: BoxDecoration(
                          color: Colors.green.withOpacity(0.2),
                          shape: BoxShape.circle,
                        ),
                        child: const Icon(
                          Icons.check_circle_outline,
                          size: 80,
                          color: Colors.white,
                        ),
                      )
                    else
                      SizedBox(
                        width: 120,
                        height: 120,
                        child: Stack(
                          alignment: Alignment.center,
                          children: [
                            SizedBox(
                              width: 120,
                              height: 120,
                              child: CircularProgressIndicator(
                                value: _progress > 0 ? _progress / 100 : null,
                                strokeWidth: 8,
                                backgroundColor: Colors.white.withOpacity(0.3),
                                valueColor: const AlwaysStoppedAnimation<Color>(Colors.white),
                              ),
                            ),
                            Text(
                              '${_progress}%',
                              style: const TextStyle(
                                fontSize: 32,
                                fontWeight: FontWeight.bold,
                                color: Colors.white,
                              ),
                            ),
                          ],
                        ),
                      ),
                    
                    const SizedBox(height: 32),
                    
                    // Status text
                    Text(
                      _hasError
                          ? 'Processing Failed'
                          : _status == 'delivered'
                              ? 'Processing Complete!'
                              : 'Processing Your Meeting',
                      style: const TextStyle(
                        fontSize: 28,
                        fontWeight: FontWeight.bold,
                        color: Colors.white,
                      ),
                      textAlign: TextAlign.center,
                    ),
                    
                    const SizedBox(height: 16),
                    
                    // Current step
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                      decoration: BoxDecoration(
                        color: Colors.white.withOpacity(0.2),
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: Text(
                        _step,
                        style: const TextStyle(
                          fontSize: 16,
                          color: Colors.white,
                        ),
                        textAlign: TextAlign.center,
                      ),
                    ),
                    
                    const SizedBox(height: 40),
                    
                    // Action buttons when complete
                    if (_status == 'delivered') ...[
                      if (_hasTranscript)
                        SizedBox(
                          width: double.infinity,
                          child: ElevatedButton.icon(
                            onPressed: () {
                              Navigator.of(context).pushReplacement(
                                MaterialPageRoute(
                                  builder: (_) => TranscriptScreen(meetingId: widget.meetingId),
                                ),
                              );
                            },
                            icon: const Icon(Icons.description),
                            label: const Text('View Transcript'),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: Colors.white,
                              foregroundColor: const Color(0xFF667eea),
                              padding: const EdgeInsets.symmetric(vertical: 16),
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(12),
                              ),
                            ),
                          ),
                        ),
                      
                      if (_hasTranscript && _hasSummary) const SizedBox(height: 12),
                      
                      if (_hasSummary)
                        SizedBox(
                          width: double.infinity,
                          child: ElevatedButton.icon(
                            onPressed: () {
                              Navigator.of(context).pushReplacement(
                                MaterialPageRoute(
                                  builder: (_) => ResultsScreen(meetingId: widget.meetingId),
                                ),
                              );
                            },
                            icon: const Icon(Icons.auto_awesome),
                            label: const Text('View Summary'),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: Colors.white,
                              foregroundColor: const Color(0xFF667eea),
                              padding: const EdgeInsets.symmetric(vertical: 16),
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(12),
                              ),
                            ),
                          ),
                        ),
                      
                      const SizedBox(height: 12),
                      
                      SizedBox(
                        width: double.infinity,
                        child: OutlinedButton.icon(
                          onPressed: () => Navigator.of(context).pop(),
                          icon: const Icon(Icons.home),
                          label: const Text('Back to Home'),
                          style: OutlinedButton.styleFrom(
                            foregroundColor: Colors.white,
                            side: const BorderSide(color: Colors.white, width: 2),
                            padding: const EdgeInsets.symmetric(vertical: 16),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(12),
                            ),
                          ),
                        ),
                      ),
                    ] else if (_hasError) ...[
                      SizedBox(
                        width: double.infinity,
                        child: ElevatedButton.icon(
                          onPressed: () => Navigator.of(context).pop(),
                          icon: const Icon(Icons.arrow_back),
                          label: const Text('Go Back'),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: Colors.white,
                            foregroundColor: Colors.red,
                            padding: const EdgeInsets.symmetric(vertical: 16),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(12),
                            ),
                          ),
                        ),
                      ),
                    ] else ...[
                      // Show info while processing
                      Text(
                        'This may take a few minutes...',
                        style: TextStyle(
                          fontSize: 14,
                          color: Colors.white.withOpacity(0.8),
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
import 'package:flutter/material.dart';
import 'package:clipnote/services/api_service.dart';
import 'dart:async';

class ProgressScreen extends StatefulWidget {
  final int meetingId;  // Changed from String to int

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
      });

      // Stop polling when done or failed
      if (_status == 'delivered' || _status == 'failed') {
        _pollTimer?.cancel();
        
        if (_status == 'delivered') {
          // Wait a moment before navigating
          await Future.delayed(const Duration(seconds: 1));
          if (!mounted) return;
          
          // Navigate to meeting detail or back to home
          Navigator.of(context).pop(); // Go back to home/meetings list
        }
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
    return Scaffold(
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
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
                    const Icon(
                      Icons.error_outline,
                      size: 80,
                      color: Colors.white,
                    )
                  else if (_status == 'delivered')
                    const Icon(
                      Icons.check_circle_outline,
                      size: 80,
                      color: Colors.white,
                    )
                  else
                    SizedBox(
                      width: 80,
                      height: 80,
                      child: CircularProgressIndicator(
                        value: _progress > 0 ? _progress / 100 : null,
                        strokeWidth: 6,
                        backgroundColor: Colors.white.withOpacity(0.3),
                        valueColor: const AlwaysStoppedAnimation<Color>(Colors.white),
                      ),
                    ),
                  
                  const SizedBox(height: 32),
                  
                  // Status text
                  Text(
                    _hasError
                        ? 'Processing Failed'
                        : _status == 'delivered'
                            ? 'Complete!'
                            : 'Processing...',
                    style: const TextStyle(
                      fontSize: 28,
                      fontWeight: FontWeight.bold,
                      color: Colors.white,
                    ),
                  ),
                  
                  const SizedBox(height: 16),
                  
                  // Progress percentage
                  if (!_hasError && _status != 'delivered')
                    Text(
                      '${_progress}%',
                      style: TextStyle(
                        fontSize: 48,
                        fontWeight: FontWeight.bold,
                        color: Colors.white.withOpacity(0.9),
                      ),
                    ),
                  
                  const SizedBox(height: 24),
                  
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
                  
                  // Action button
                  if (_hasError)
                    ElevatedButton(
                      onPressed: () => Navigator.of(context).pop(),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.white,
                        foregroundColor: const Color(0xFF667eea),
                        padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 16),
                      ),
                      child: const Text('Go Back'),
                    )
                  else if (_status == 'delivered')
                    ElevatedButton(
                      onPressed: () => Navigator.of(context).pop(),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.white,
                        foregroundColor: const Color(0xFF667eea),
                        padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 16),
                      ),
                      child: const Text('View Meetings'),
                    ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
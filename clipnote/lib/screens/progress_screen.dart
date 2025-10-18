import 'dart:async';
import 'package:flutter/material.dart';
import 'package:clipnote/services/api_service.dart';

class ProgressScreen extends StatefulWidget {
  final String meetingId;
  const ProgressScreen({super.key, required this.meetingId});

  @override
  State<ProgressScreen> createState() => _ProgressScreenState();
}

class _ProgressScreenState extends State<ProgressScreen> {
  final _apiService = ApiService.I;

  Timer? _timer;
  String _state = 'queued';
  double _progress = 0.0;
  String _statusText = 'Starting...';
  String? _etaText;
  bool _hasError = false;

  @override
  void initState() {
    super.initState();
    _fetchOnce();
    _timer = Timer.periodic(const Duration(seconds: 2), (_) => _fetchOnce());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _fetchOnce() async {
    try {
      final status = await _apiService.getMeetingStatus(widget.meetingId);

      final state = status['state'] as String? ?? 'queued';
      final progress = (status['progress'] as num?)?.toDouble() ?? 0.0;
      final message = status['message'] as String? ?? '';
      final eta = status['eta'] as String?;

      if (!mounted) return;
      setState(() {
        _state = state;
        _progress = progress.clamp(0.0, 1.0);
        _statusText = message.isEmpty ? 'Processing...' : message;
        _etaText = eta;
        _hasError = state == 'error';
      });

      if (state == 'done' || state == 'error') {
        _timer?.cancel();
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _statusText = 'Failed to fetch status: $e';
        _hasError = true;
      });
    }
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
          'Processing',
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
                
                // Status Icon
                Center(
                  child: Container(
                    width: 120,
                    height: 120,
                    decoration: BoxDecoration(
                      color: Colors.white.withOpacity(0.2),
                      shape: BoxShape.circle,
                    ),
                    child: Center(
                      child: _hasError
                          ? const Icon(Icons.error_outline, size: 60, color: Colors.white)
                          : _state == 'done'
                              ? const Icon(Icons.check_circle_outline, size: 60, color: Colors.white)
                              : const CircularProgressIndicator(
                                  strokeWidth: 4,
                                  valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                                ),
                    ),
                  ),
                ),
                
                const SizedBox(height: 40),
                
                // Status Card
                Container(
                  padding: const EdgeInsets.all(24),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(16),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withOpacity(0.1),
                        blurRadius: 10,
                        offset: const Offset(0, 4),
                      ),
                    ],
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                            decoration: BoxDecoration(
                              color: _hasError
                                  ? Colors.red.shade100
                                  : _state == 'done'
                                      ? Colors.green.shade100
                                      : const Color(0xFF667eea).withOpacity(0.1),
                              borderRadius: BorderRadius.circular(20),
                            ),
                            child: Text(
                              _state.toUpperCase(),
                              style: TextStyle(
                                fontWeight: FontWeight.bold,
                                fontSize: 12,
                                color: _hasError
                                    ? Colors.red.shade700
                                    : _state == 'done'
                                        ? Colors.green.shade700
                                        : const Color(0xFF667eea),
                              ),
                            ),
                          ),
                        ],
                      ),
                      
                      const SizedBox(height: 16),
                      
                      Text(
                        _statusText,
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                      
                      const SizedBox(height: 16),
                      
                      LinearProgressIndicator(
                        value: _progress,
                        backgroundColor: Colors.grey.shade200,
                        valueColor: AlwaysStoppedAnimation<Color>(
                          _hasError ? Colors.red : const Color(0xFF667eea),
                        ),
                        minHeight: 8,
                        borderRadius: BorderRadius.circular(4),
                      ),
                      
                      const SizedBox(height: 8),
                      
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(
                            '${(_progress * 100).toInt()}%',
                            style: TextStyle(
                              fontSize: 12,
                              color: Colors.grey.shade600,
                            ),
                          ),
                          if (_etaText != null)
                            Text(
                              'ETA: $_etaText',
                              style: TextStyle(
                                fontSize: 12,
                                color: Colors.grey.shade600,
                              ),
                            ),
                        ],
                      ),
                    ],
                  ),
                ),
                
                const Spacer(),
                
                if (_state == 'done')
                  SizedBox(
                    height: 56,
                    child: ElevatedButton.icon(
                      onPressed: () {
                        // TODO: Navigate to results screen
                        Navigator.of(context).pop();
                      },
                      icon: const Icon(Icons.visibility),
                      label: const Text(
                        'View Results',
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
                  )
                else if (_hasError)
                  SizedBox(
                    height: 56,
                    child: ElevatedButton.icon(
                      onPressed: () => Navigator.of(context).pop(),
                      icon: const Icon(Icons.arrow_back),
                      label: const Text(
                        'Go Back',
                        style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
                      ),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.white,
                        foregroundColor: Colors.red,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                      ),
                    ),
                  )
                else
                  OutlinedButton(
                    onPressed: () => Navigator.of(context).pop(),
                    style: OutlinedButton.styleFrom(
                      side: const BorderSide(color: Colors.white),
                      foregroundColor: Colors.white,
                      minimumSize: const Size(double.infinity, 56),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                    child: const Text(
                      'Cancel',
                      style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
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
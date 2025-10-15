import 'dart:async';
import 'flutter/material.dart';
import '../services/api_service.dart';
import 'results_screen.dart';

class ProgressScreen extends StatefulWidget {
  final int meetingId;

  const ProgressScreen({super.key, required this.meetingId});

  @override
  State<ProgressScreen> createState() => _ProgressScreenState();
}

class _ProgressScreenState extends State<ProgressScreen> {
  final _apiService = ApiService();
  Timer? _timer;
  Map<String, dynamic>? _meetingData;
  String _status = 'queued';
  int _progress = 0;
  String _step = 'Initializing...';

  @override
  void initState() {
    super.initState();
    _startPolling();
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  void _startPolling() {
    _timer = Timer.periodic(const Duration(seconds: 2), (_) {
      _fetchMeetingStatus();
    });
    _fetchMeetingStatus(); // Initial fetch
  }

  Future<void> _fetchMeetingStatus() async {
    try {
      final data = await _apiService.getMeetingStatus(widget.meetingId);
      
      setState(() {
        _meetingData = data;
        _status = data['status'] ?? 'queued';
        _progress = data['progress'] ?? 0;
        _step = data['step'] ?? 'Processing...';
      });

      if (_status == 'delivered' || _status == 'failed') {
        _timer?.cancel();
        
        if (_status == 'delivered' && mounted) {
          // Navigate to results
          Navigator.of(context).pushReplacement(
            MaterialPageRoute(
              builder: (_) => ResultsScreen(meetingId: widget.meetingId),
            ),
          );
        }
      }
    } catch (e) {
      print('Error fetching meeting status: $e');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Processing'),
        backgroundColor: const Color(0xFF667eea),
      ),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              // Progress circle
              SizedBox(
                width: 200,
                height: 200,
                child: Stack(
                  alignment: Alignment.center,
                  children: [
                    CircularProgressIndicator(
                      value: _progress / 100,
                      strokeWidth: 8,
                      backgroundColor: Colors.grey.shade300,
                      valueColor: const AlwaysStoppedAnimation<Color>(Color(0xFF667eea)),
                    ),
                    Text(
                      '$_progress%',
                      style: const TextStyle(
                        fontSize: 48,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 40),

              // Status badge
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
                decoration: BoxDecoration(
                  color: _getStatusColor().withOpacity(0.2),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Text(
                  _status.toUpperCase(),
                  style: TextStyle(
                    color: _getStatusColor(),
                    fontWeight: FontWeight.bold,
                    fontSize: 16,
                  ),
                ),
              ),

              const SizedBox(height: 16),

              // Current step
              Text(
                _step,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  fontSize: 18,
                  color: Colors.grey,
                ),
              ),

              if (_status == 'failed') ...[
                const SizedBox(height: 40),
                ElevatedButton(
                  onPressed: () => Navigator.of(context).pop(),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.red,
                  ),
                  child: const Text('Go Back'),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Color _getStatusColor() {
    switch (_status) {
      case 'delivered':
        return Colors.green;
      case 'failed':
        return Colors.red;
      case 'processing':
        return Colors.orange;
      default:
        return Colors.blue;
    }
  }
}
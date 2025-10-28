import 'package:flutter/material.dart';
import 'package:clipnote/services/api_service.dart';
import 'package:url_launcher/url_launcher.dart';
import 'dart:async';
import 'transcript_screen.dart';
import 'results_screen.dart';
import 'package:clipnote/services/local_db.dart';
import 'package:clipnote/services/offline_storage.dart';
import 'package:clipnote/services/sync_service.dart';


class MeetingsListScreen extends StatefulWidget {
  final String? initialFilter;
  
  const MeetingsListScreen({super.key, this.initialFilter});

  @override
  State<MeetingsListScreen> createState() => _MeetingsListScreenState();
}

// Use a MaterialColor so .shade50/.shade700 are valid
final MaterialColor badgeSwatch = Colors.blue; // <-- rename from badgeColor if needed

class _MeetingsListScreenState extends State<MeetingsListScreen> {
  final _api = ApiService.I;
  List<Map<String, dynamic>> _meetings = [];
  List<Map<String, dynamic>> _filteredMeetings = [];
  
  bool _isLoading = true;
  String _searchQuery = '';
  String _filterStatus = 'all';
  Timer? _autoDownloadTimer;

  @override
  void initState() {
    super.initState();
    localDb.open();
    if (widget.initialFilter != null) {
      _filterStatus = widget.initialFilter!;
    }
    _loadMeetings();
    _startAutoDownloadPolling();
  }

  Future<void> _loadMeetings() async {
    setState(() => _isLoading = true);
    
    try {
      final meetings = await _api.getMeetings();
      setState(() {
        _meetings = meetings;
        _filteredMeetings = meetings;
        _isLoading = false;
      });
      _filterMeetings();
    } catch (e) {
      print('Error loading meetings: $e');
      setState(() => _isLoading = false);
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to load meetings: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  void _filterMeetings() {
    setState(() {
      _filteredMeetings = _meetings.where((meeting) {
        final matchesSearch = _searchQuery.isEmpty ||
            meeting['title'].toString().toLowerCase().contains(_searchQuery.toLowerCase());
        
        bool matchesStatus = false;
        
        if (_filterStatus == 'all') {
          matchesStatus = true;
        } else if (_filterStatus == 'this_month') {
          try {
            final createdAt = DateTime.parse(meeting['created_at']);
            final now = DateTime.now();
            matchesStatus = createdAt.year == now.year && createdAt.month == now.month;
          } catch (e) {
            matchesStatus = false;
          }
        } else if (_filterStatus == 'processing') {
          matchesStatus = meeting['status'] == 'processing' || meeting['status'] == 'queued';
        } else if (_filterStatus == 'delivered') {
          // Match any completed status
          matchesStatus = _isCompletedStatus(meeting['status'] ?? '');
        } else {
          matchesStatus = meeting['status'] == _filterStatus;
        }
        
        return matchesSearch && matchesStatus;
      }).toList();
    });
  }

  void _showFilterSheet() {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) => SafeArea(
        child: Container(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Filter by Status',
                style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 16),
              _filterOption('All Meetings', 'all'),
              _filterOption('Delivered', 'delivered'),
              _filterOption('Processing', 'processing'),
              _filterOption('This Month', 'this_month'),
              _filterOption('Failed', 'failed'),
              const SizedBox(height: 20),
            ],
          ),
        ),
      ),
    );
  }

  Widget _filterOption(String label, String value) {
    return RadioListTile<String>(
      title: Text(label),
      value: value,
      groupValue: _filterStatus,
      activeColor: const Color(0xFF667eea),
      onChanged: (val) {
        setState(() {
          _filterStatus = val!;
          _filterMeetings();
        });
        Navigator.pop(context);
      },
    );
  }

  String _formatDate(String? dateStr) {
    if (dateStr == null) return 'No date';
    try {
      final date = DateTime.parse(dateStr);
      final now = DateTime.now();
      final difference = now.difference(date);
      
      if (difference.inDays == 0) {
        final hour = date.hour > 12 ? date.hour - 12 : (date.hour == 0 ? 12 : date.hour);
        final minute = date.minute.toString().padLeft(2, '0');
        final period = date.hour >= 12 ? 'PM' : 'AM';
        return 'Today $hour:$minute $period';
      } else if (difference.inDays == 1) {
        return 'Yesterday';
      } else if (difference.inDays < 7) {
        return '${difference.inDays} days ago';
      } else {
        final months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        return '${months[date.month - 1]} ${date.day}, ${date.year}';
      }
    } catch (e) {
      return 'Invalid date';
    }
  }

  Widget _buildStorageBadge(Map<String, dynamic> meeting) {
    final hasCloudStorage = _api.hasCloudStorage;
    final status = meeting['status'] ?? '';
    
    if (hasCloudStorage) {
      // Pro/Business - Cloud Storage
      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        decoration: BoxDecoration(
          color: badgeSwatch.shade50,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.cloud, size: 12, color: badgeSwatch.shade50),
            const SizedBox(width: 4),
            Text(
              'Cloud',
              style: TextStyle(
                fontSize: 10,
                fontWeight: FontWeight.w600,
                color: badgeSwatch.shade700,
              ),
            ),
          ],
        ),
      );
    } else {
      // Free/Starter - Device Storage
      Color badgeColor;
      String badgeText;
      IconData badgeIcon;
      
      if (status == 'ready_for_download' || status == 'processing' || status == 'queued') {
        badgeColor = Colors.orange;
        badgeText = 'Saving...';
        badgeIcon = Icons.downloading;
      } else if (status == 'downloaded_to_device') {
        badgeColor = Colors.green;
        badgeText = 'On Device';
        badgeIcon = Icons.check_circle;
      } else {
        badgeColor = Colors.green;
        badgeText = 'Device';
        badgeIcon = Icons.phone_android;
      }
      
      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        decoration: BoxDecoration(
          color: badgeSwatch.shade50,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(badgeIcon, size: 12, color: badgeSwatch.shade700),
            const SizedBox(width: 4),
            Text(
              badgeText,
              style: TextStyle(
                fontSize: 10,
                fontWeight: FontWeight.w600,
                color: badgeSwatch.shade700,
              ),
            ),
          ],
        ),
      );
    }
  }

  String _getScreenTitle() {
    switch (_filterStatus) {
      case 'delivered':
        return 'Completed Meetings';
      case 'processing':
        return 'Processing Meetings';
      case 'this_month':
        return 'This Month';
      case 'failed':
        return 'Failed Meetings';
      default:
        return 'My Meetings';
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
          onPressed: () => Navigator.pop(context),
        ),
        title: Text(
          _getScreenTitle(),
          style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
        ),
        centerTitle: true,
        actions: [
          IconButton(
            icon: const Icon(Icons.search, color: Colors.white),
            onPressed: () => _showSearchDialog(),
          ),
          IconButton(
            icon: Icon(
              _filterStatus == 'all' ? Icons.filter_list : Icons.filter_alt,
              color: Colors.white,
            ),
            onPressed: _showFilterSheet,
          ),
        ],
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
          child: _isLoading
              ? const Center(
                  child: CircularProgressIndicator(
                    valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                  ),
                )
              : _filteredMeetings.isEmpty
                  ? _buildEmptyState()
                  : _buildMeetingsList(),
        ),
      ),
    );
  }

  void _showSearchDialog() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Search Meetings'),
        content: TextField(
          autofocus: true,
          decoration: const InputDecoration(
            hintText: 'Enter meeting title...',
            prefixIcon: Icon(Icons.search),
          ),
          onChanged: (value) {
            setState(() {
              _searchQuery = value;
              _filterMeetings();
            });
          },
        ),
        actions: [
          TextButton(
            onPressed: () {
              setState(() {
                _searchQuery = '';
                _filterMeetings();
              });
              Navigator.pop(context);
            },
            child: const Text('Clear'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyState() {
    String emptyMessage;
    if (_searchQuery.isNotEmpty || _filterStatus != 'all') {
      emptyMessage = 'No meetings found with current filters';
    } else {
      emptyMessage = 'Start recording or upload your first meeting to see it here';
    }

    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              padding: const EdgeInsets.all(32),
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.2),
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.folder_open,
                size: 80,
                color: Colors.white,
              ),
            ),
            const SizedBox(height: 24),
            Text(
              _searchQuery.isNotEmpty || _filterStatus != 'all'
                  ? 'No Meetings Found'
                  : 'No Meetings Yet',
              style: const TextStyle(
                color: Colors.white,
                fontSize: 24,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 12),
            Text(
              emptyMessage,
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 16,
              ),
            ),
            if (_searchQuery.isNotEmpty || _filterStatus != 'all') ...[
              const SizedBox(height: 20),
              ElevatedButton(
                onPressed: () {
                  setState(() {
                    _searchQuery = '';
                    _filterStatus = 'all';
                    _filterMeetings();
                  });
                },
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.white,
                  foregroundColor: const Color(0xFF667eea),
                ),
                child: const Text('Clear Filters'),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildMeetingsList() {
    return RefreshIndicator(
      onRefresh: _loadMeetings,
      color: const Color(0xFF667eea),
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: _filteredMeetings.length,
        itemBuilder: (context, index) {
          final meeting = _filteredMeetings[index];
          return _meetingCard(
            id: meeting['id'],
            title: meeting['title'] ?? 'Untitled Meeting',
            date: _formatDate(meeting['created_at']),
            status: meeting['status'] ?? 'unknown',
            progress: meeting['progress'] ?? 0,
            hasTranscript: meeting['has_transcript'] ?? false,
            hasSummary: meeting['has_summary'] ?? false,
          );
        },
      ),
    );
  }

  Widget _meetingCard({
    required int id,
    required String title,
    required String date,
    required String status,
    required int progress,
    required bool hasTranscript,
    required bool hasSummary,
  }) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
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
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: () => _showMeetingDetails(id, title, status),
          borderRadius: BorderRadius.circular(16),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: const Color(0xFF667eea).withOpacity(0.1),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Icon(
                        _getStatusIcon(status),
                        color: _getStatusColor(status),
                        size: 24,
                      ),
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            title,
                            style: const TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.bold,
                            ),
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                          ),
                          const SizedBox(height: 6),
                          Row(
                            children: [
                              Icon(Icons.calendar_today, size: 14, color: Colors.grey.shade600),
                              const SizedBox(width: 4),
                              Text(
                                date,
                                style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                      decoration: BoxDecoration(
                        color: _getStatusColor(status),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(
                        _getStatusLabel(status),
                        style: const TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.bold,
                          color: Colors.white,
                        ),
                      ),
                    ),
                  ],
                ),
                if (status == 'processing' || status == 'queued') ...[
                  const SizedBox(height: 12),
                  ClipRRect(
                    borderRadius: BorderRadius.circular(4),
                    child: LinearProgressIndicator(
                      value: progress / 100,
                      backgroundColor: Colors.grey.shade200,
                      valueColor: AlwaysStoppedAnimation<Color>(_getStatusColor(status)),
                      minHeight: 6,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    '$progress% complete',
                    style: TextStyle(fontSize: 11, color: Colors.grey.shade600),
                  ),
                ],
                if (status == 'delivered') ...[
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      if (hasTranscript)
                        _availableChip(Icons.description, 'Transcript'),
                      if (hasTranscript && hasSummary) const SizedBox(width: 8),
                      if (hasSummary)
                        _availableChip(Icons.auto_awesome, 'Summary'),
                    ],
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _availableChip(IconData icon, String label) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: Colors.green.shade50,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.green.shade200),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: Colors.green.shade700),
          const SizedBox(width: 4),
          Text(
            label,
            style: TextStyle(
              fontSize: 11,
              color: Colors.green.shade700,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }

  IconData _getStatusIcon(String status) {
    if (_isCompletedStatus(status)) {
      return Icons.check_circle;
    }
    
    switch (status.toLowerCase()) {
      case 'processing':
      case 'queued':
        return Icons.hourglass_empty;
      case 'failed':
        return Icons.error;
      case 'ready_for_download':
        return Icons.downloading;
      default:
        return Icons.help;
    }
  }

  // Helper method to check if status represents a completed meeting
  bool _isCompletedStatus(String status) {
    final completedStatuses = [
      'delivered',
      'completed',
      'complete',
      'done',
      'finished',
      'downloaded_to_device',
    ];
    return completedStatuses.contains(status.toLowerCase());
  }

  String _getStatusLabel(String status) {
    if (_isCompletedStatus(status)) {
      return 'DONE';
    }
    
    switch (status.toLowerCase()) {
      case 'processing':
        return 'PROCESSING';
      case 'queued':
        return 'QUEUED';
      case 'failed':
        return 'FAILED';
      case 'ready_for_download':
        return 'READY';
      default:
        return status.toUpperCase();
    }
  }

  Color _getStatusColor(String status) {
    if (_isCompletedStatus(status)) {
      return Colors.green;
    }
    
    switch (status.toLowerCase()) {
      case 'processing':
      case 'queued':
        return const Color(0xFF667eea);
      case 'failed':
        return Colors.red;
      case 'ready_for_download':
        return Colors.orange;
      default:
        return Colors.grey;
    }
  }

  void _showMeetingDetails(int id, String title, String status) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) => SafeArea(
        child: DraggableScrollableSheet(
          initialChildSize: 0.6,
          minChildSize: 0.4,
          maxChildSize: 0.9,
          expand: false,
          builder: (context, scrollController) => SingleChildScrollView(
            controller: scrollController,
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Center(
                    child: Container(
                      width: 40,
                      height: 4,
                      decoration: BoxDecoration(
                        color: Colors.grey.shade300,
                        borderRadius: BorderRadius.circular(2),
                      ),
                    ),
                  ),
                  const SizedBox(height: 20),
                  Text(
                    title,
                    style: const TextStyle(
                      fontSize: 24,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 20),
                  if (_isCompletedStatus(status)) ...[
                    _actionButton(
                      icon: Icons.description,
                      label: 'View Transcript',
                      onPressed: () {
                        Navigator.pop(context);
                        Navigator.of(this.context).push(
                          MaterialPageRoute(
                            builder: (_) => TranscriptScreen(meetingId: id),
                          ),
                        );
                      },
                    ),
                    const SizedBox(height: 12),
                    _actionButton(
                      icon: Icons.auto_awesome,
                      label: 'View Summary',
                      onPressed: () {
                        Navigator.pop(context);
                        Navigator.of(this.context).push(
                          MaterialPageRoute(
                            builder: (_) => ResultsScreen(meetingId: id),
                          ),
                        );
                      },
                    ),
                    const SizedBox(height: 12),
                    _actionButton(
                      icon: Icons.email,
                      label: 'Email Meeting',
                      onPressed: () {
                        Navigator.pop(context);
                        _emailMeeting(id, title);
                      },
                    ),
                    const SizedBox(height: 12),
                    _actionButton(
                      icon: Icons.download,
                      label: 'Download Files',
                      onPressed: () {
                        Navigator.pop(context);
                        _downloadMeetingFiles(id, title);
                      },
                    ),
                    const SizedBox(height: 12),
                    _actionButton(
                      icon: Icons.delete,
                      label: 'Delete Meeting',
                      color: Colors.red,
                      onPressed: () {
                        Navigator.pop(context);
                        _deleteMeeting(id, title);
                      },
                    ),
                  ] else if (status == 'processing' || status == 'queued') ...[
                    const Center(
                      child: Column(
                        children: [
                          CircularProgressIndicator(),
                          SizedBox(height: 16),
                          Text(
                            'Processing in progress...',
                            style: TextStyle(fontSize: 16),
                          ),
                        ],
                      ),
                    ),
                  ] else if (status == 'failed') ...[
                    Center(
                      child: Column(
                        children: [
                          Icon(Icons.error_outline, color: Colors.red, size: 48),
                          const SizedBox(height: 16),
                          const Text(
                            'This meeting failed to process',
                            style: TextStyle(color: Colors.red, fontSize: 16),
                          ),
                          const SizedBox(height: 20),
                          _actionButton(
                            icon: Icons.delete,
                            label: 'Delete Meeting',
                            color: Colors.red,
                            onPressed: () {
                              Navigator.pop(context);
                              _deleteMeeting(id, title);
                            },
                          ),
                        ],
                      ),
                    ),
                  ] else ...[
                    Center(
                      child: Column(
                        children: [
                          Icon(Icons.info_outline, color: Colors.orange, size: 48),
                          const SizedBox(height: 16),
                          Text(
                            'Status: ${_getStatusLabel(status)}',
                            style: const TextStyle(fontSize: 16),
                          ),
                          const SizedBox(height: 8),
                          Text(
                            'This meeting is in an unknown state',
                            style: TextStyle(color: Colors.grey.shade600, fontSize: 14),
                          ),
                        ],
                      ),
                    ),
                  ],
                  const SizedBox(height: 20),
                  TextButton(
                    onPressed: () => Navigator.pop(context),
                    child: const Center(child: Text('Close')),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Future<void> _emailMeeting(int id, String title) async {
    final emailController = TextEditingController();
    bool isSending = false;
    
    showDialog(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('Email Meeting'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: emailController,
                keyboardType: TextInputType.emailAddress,
                decoration: InputDecoration(
                  labelText: 'Email Address',
                  hintText: 'Enter email address',
                  prefixIcon: const Icon(Icons.email, color: Color(0xFF667eea)),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                  contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                ),
              ),
              const SizedBox(height: 12),
              Text(
                'Meeting: $title',
                style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: isSending ? null : () => Navigator.pop(context),
              child: const Text('Cancel'),
            ),
            ElevatedButton.icon(
              onPressed: isSending
                  ? null
                  : () async {
                      final email = emailController.text.trim();
                      
                      if (email.isEmpty) {
                        ScaffoldMessenger.of(this.context).showSnackBar(
                          const SnackBar(
                            content: Text('Please enter an email address'),
                            backgroundColor: Colors.red,
                          ),
                        );
                        return;
                      }

                      // Basic email validation
                      if (!RegExp(r'^[^@]+@[^@]+\.[^@]+').hasMatch(email)) {
                        ScaffoldMessenger.of(this.context).showSnackBar(
                          const SnackBar(
                            content: Text('Please enter a valid email address'),
                            backgroundColor: Colors.red,
                          ),
                        );
                        return;
                      }

                      setDialogState(() => isSending = true);

                      try {
                        await _api.sendMeetingEmail(id, email);
                        
                        if (!mounted) return;
                        Navigator.pop(context);
                        
                        ScaffoldMessenger.of(this.context).showSnackBar(
                          SnackBar(
                            content: Text('Meeting sent to $email'),
                            backgroundColor: Colors.green,
                          ),
                        );
                      } catch (e) {
                        print('Error sending email: $e');
                        setDialogState(() => isSending = false);
                        
                        if (!mounted) return;
                        
                        ScaffoldMessenger.of(this.context).showSnackBar(
                          SnackBar(
                            content: Text('Failed to send email: ${e.toString().replaceAll("Exception: ", "")}'),
                            backgroundColor: Colors.red,
                            duration: const Duration(seconds: 4),
                          ),
                        );
                      }
                    },
              icon: isSending
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                      ),
                    )
                  : const Icon(Icons.send, size: 18),
              label: Text(isSending ? 'Sending...' : 'Send'),
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF667eea),
                foregroundColor: Colors.white,
                disabledBackgroundColor: Colors.grey,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _downloadMeetingFiles(int id, String title) async {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) => SafeArea(
        child: Container(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text(
                'Download Files',
                style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 20),
              ListTile(
                leading: const CircleAvatar(
                  backgroundColor: Color(0xFFE3F2FD),
                  child: Icon(Icons.description, color: Color(0xFF667eea)),
                ),
                title: const Text('Transcript'),
                subtitle: const Text('Download as .txt file'),
                trailing: const Icon(Icons.download),
                onTap: () {
                  Navigator.pop(context);
                  _downloadFile(id, 'transcript', title);
                },
              ),
              ListTile(
                leading: const CircleAvatar(
                  backgroundColor: Color(0xFFFFF3E0),
                  child: Icon(Icons.auto_awesome, color: Colors.orange),
                ),
                title: const Text('Summary'),
                subtitle: const Text('Download as .txt file'),
                trailing: const Icon(Icons.download),
                onTap: () {
                  Navigator.pop(context);
                  _downloadFile(id, 'summary', title);
                },
              ),
              ListTile(
                leading: const CircleAvatar(
                  backgroundColor: Color(0xFFFFEBEE),
                  child: Icon(Icons.picture_as_pdf, color: Colors.red),
                ),
                title: const Text('Full Report'),
                subtitle: const Text('Download as PDF (if available)'),
                trailing: const Icon(Icons.download),
                onTap: () {
                  Navigator.pop(context);
                  _downloadFile(id, 'pdf', title);
                },
              ),
              const Divider(height: 30),
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 8.0),
                child: Text(
                  'Offline Packages',
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: Colors.grey,
                  ),
                ),
              ),
              ListTile(
                leading: const CircleAvatar(
                  backgroundColor: Color(0xFFE8F5E9),
                  child: Icon(Icons.web, color: Colors.green),
                ),
                title: const Text('HTML Viewer'),
                subtitle: const Text('Beautiful offline viewer'),
                trailing: const Icon(Icons.offline_bolt),
                onTap: () {
                  Navigator.pop(context);
                  _downloadOfflinePackage(id, 'html', title);
                },
              ),
              ListTile(
                leading: const CircleAvatar(
                  backgroundColor: Color(0xFFFCE4EC),
                  child: Icon(Icons.folder_zip, color: Colors.pink),
                ),
                title: const Text('ZIP Archive'),
                subtitle: const Text('Complete package with all files'),
                trailing: const Icon(Icons.offline_bolt),
                onTap: () {
                  Navigator.pop(context);
                  _downloadOfflinePackage(id, 'zip', title);
                },
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _downloadFile(int id, String type, String title) async {
    final isCloudStorage = _api.hasCloudStorage;
    final loadingMessage = isCloudStorage 
        ? 'Downloading from cloud...' 
        : 'Preparing $type...';
    final successMessage = isCloudStorage
        ? 'Downloaded from cloud'
        : 'Saved to device';
    
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        content: Row(
          children: [
            const CircularProgressIndicator(),
            const SizedBox(width: 20),
            Text(loadingMessage),
          ],
        ),
      ),
    );

    try {
      final downloadInfo = await _api.downloadMeetingFile(id, type);
      final url = downloadInfo['download_url'];
      final uri = Uri.parse(url);
      
      if (!mounted) return;
      Navigator.pop(context);
      
      if (await canLaunchUrl(uri)) {
        await launchUrl(uri, mode: LaunchMode.externalApplication);
        
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(successMessage),
            backgroundColor: Colors.green,
            duration: const Duration(seconds: 2),
          ),
        );
      } else {
        throw Exception('Could not open download URL');
      }
    } catch (e) {
      print('Error downloading file: $e');
      
      if (!mounted) return;
      Navigator.pop(context);
      
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Download failed: ${e.toString().replaceAll("Exception: ", "")}'),
          backgroundColor: Colors.red,
          duration: const Duration(seconds: 4),
        ),
      );
    }
  }
  
  Future<void> _downloadOfflinePackage(int id, String format, String title) async {
    final formatLabel = format == 'html' ? 'HTML Viewer' : 'ZIP Archive';
    
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        content: Row(
          children: [
            const CircularProgressIndicator(),
            const SizedBox(width: 20),
            Text('Preparing $formatLabel...'),
          ],
        ),
      ),
    );

    try {
      final downloadInfo = await _api.downloadOfflinePackage(id, format);
      final url = downloadInfo['download_url'];
      final uri = Uri.parse(url);
      
      if (!mounted) return;
      Navigator.pop(context);
      
      if (await canLaunchUrl(uri)) {
        await launchUrl(uri, mode: LaunchMode.externalApplication);
        
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Row(
              children: [
                const Icon(Icons.offline_bolt, color: Colors.white),
                const SizedBox(width: 12),
                Expanded(
                  child: Text('$formatLabel ready for offline use'),
                ),
              ],
            ),
            backgroundColor: Colors.green,
            duration: const Duration(seconds: 3),
          ),
        );
      } else {
        throw Exception('Could not open download URL');
      }
    } catch (e) {
      print('Error downloading offline package: $e');
      
      if (!mounted) return;
      Navigator.pop(context);
      
      String errorMessage = e.toString().replaceAll("Exception: ", "");
      
      // Handle specific error cases
      if (errorMessage.contains('cloud-stored')) {
        errorMessage = 'This meeting is in cloud storage.\nUse individual download options instead.';
      }
      
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Download failed: $errorMessage'),
          backgroundColor: Colors.red,
          duration: const Duration(seconds: 5),
        ),
      );
    }
  }
  
  Future<void> _deleteMeeting(int id, String title) async {
    // Confirm deletion
    final confirm = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Meeting'),
        content: Text('Are you sure you want to delete "$title"?\n\nThis action cannot be undone.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.red,
              foregroundColor: Colors.white,
            ),
            child: const Text('Delete'),
          ),
        ],
      ),
    );

    if (confirm != true) return;

    // Show deleting dialog
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => const AlertDialog(
        content: Row(
          children: [
            CircularProgressIndicator(),
            SizedBox(width: 20),
            Text('Deleting...'),
          ],
        ),
      ),
    );

    try {
      await _api.deleteMeeting(id);
      
      if (!mounted) return;
      Navigator.pop(context);
      
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Meeting deleted successfully'),
          backgroundColor: Colors.green,
        ),
      );
      
      // Refresh the list
      _loadMeetings();
    } catch (e) {
      print('Error deleting meeting: $e');
      
      if (!mounted) return;
      Navigator.pop(context);
      
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Failed to delete meeting: ${e.toString().replaceAll("Exception: ", "")}'),
          backgroundColor: Colors.red,
          duration: const Duration(seconds: 4),
        ),
      );
    }
  }

  Widget _actionButton({
    required IconData icon,
    required String label,
    required VoidCallback onPressed,
    Color? color,
  }) {
    return SizedBox(
      width: double.infinity,
      child: ElevatedButton.icon(
        onPressed: onPressed,
        icon: Icon(icon),
        label: Text(label),
        style: ElevatedButton.styleFrom(
          backgroundColor: color ?? const Color(0xFF667eea),
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(vertical: 14),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
      ),
    );
  }
 

  @override
  void dispose() {
    _autoDownloadTimer?.cancel();
    super.dispose();
  }

  void _startAutoDownloadPolling() {
    // Only poll for Free/Starter tiers (device storage)
    if (!_api.shouldAutoDownload) {
      print('[MeetingsList] Skipping auto-download (cloud storage tier)');
      return;
    }
    
    print('[MeetingsList] Starting auto-download polling...');
    
    // Check immediately
    _checkForAutoDownloads();
    
    // Then check every 10 seconds
    _autoDownloadTimer = Timer.periodic(
      const Duration(seconds: 10),
      (timer) => _checkForAutoDownloads(),
    );
  }

  Future<void> _checkForAutoDownloads() async {
    try {
      final meetings = await _api.getMeetings();
      
      for (var meeting in meetings) {
        if (meeting['status'] == 'ready_for_download') {
          print('[MeetingsList] 🔽 Auto-downloading meeting ${meeting['id']}');
          await _autoDownloadMeeting(meeting);
        }
      }
    } catch (e) {
      print('[MeetingsList] Error checking for auto-downloads: $e');
    }
  }

  Future<void> _autoDownloadMeeting(Map<String, dynamic> meeting) async {
    final int id = meeting['id'];
    final String title = meeting['title'] ?? 'Untitled';
    
    try {
      print('[MeetingsList] 📥 Auto-downloading: $title');
      
      // Download transcript
      bool transcriptSuccess = false;
      try {
        await _downloadFileSilently(id, 'transcript', title);
        transcriptSuccess = true;
        print('[MeetingsList] ✅ Transcript downloaded');
      } catch (e) {
        print('[MeetingsList] ⚠️ Transcript download failed: $e');
      }
      
      // Download summary
      bool summarySuccess = false;
      try {
        await _downloadFileSilently(id, 'summary', title);
        summarySuccess = true;
        print('[MeetingsList] ✅ Summary downloaded');
      } catch (e) {
        print('[MeetingsList] ⚠️ Summary download failed: $e');
      }
      
      // If both succeeded, confirm download to backend
      if (transcriptSuccess && summarySuccess) {
        await _api.confirmDownloadComplete(id);
        
        // Refresh meetings list
        await _loadMeetings();
        
        // Show success notification
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('✅ "$title" saved to device'),
              backgroundColor: Colors.green,
              duration: const Duration(seconds: 3),
            ),
          );
        }
      }
    } catch (e) {
      print('[MeetingsList] ❌ Auto-download failed for $title: $e');
    }
  }

  Future<void> _downloadFileSilently(int id, String type, String title) async {
    try {
      final downloadInfo = await _api.downloadMeetingFile(id, type);
      final url = downloadInfo['download_url'];
      final uri = Uri.parse(url);
      
      if (await canLaunchUrl(uri)) {
        await launchUrl(uri, mode: LaunchMode.externalApplication);
      } else {
        throw Exception('Could not open download URL');
      }
    } catch (e) {
      print('[MeetingsList] Error downloading $type: $e');
      rethrow;
    }
  }
}
class LocalFilesSection extends StatefulWidget {
  const LocalFilesSection({super.key, required this.meetingId});
  final int meetingId;
  @override
  State<LocalFilesSection> createState() => _LocalFilesSectionState();
}
class _LocalFilesSectionState extends State<LocalFilesSection> {
  Future<List<Map<String, Object?>>> _load() => localDb.listByMeeting(widget.meetingId);
  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<Map<String, Object?>>>(
      future: _load(),
      builder: (context, snap) {
        final items = snap.data ?? const [];
        if (items.isEmpty) {
          return const SizedBox.shrink(); // nothing saved yet
        }
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SizedBox(height: 8),
            const Text('Saved on device', style: TextStyle(fontWeight: FontWeight.w600)),
            const SizedBox(height: 8),
            ...items.map((r) {
              final filename = (r['filename'] as String?) ?? 'file';
              final path = (r['path'] as String?) ?? '';
              final size = (r['size_bytes'] as int?) ?? 0;
              return ListTile(
                dense: true,
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.insert_drive_file),
                title: Text(filename, maxLines: 1, overflow: TextOverflow.ellipsis),
                subtitle: Text('${size}B'),
                trailing: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    IconButton(
                      icon: const Icon(Icons.open_in_new),
                      onPressed: () => openLocalFile(path),
                      tooltip: 'Open',
                    ),
                    IconButton(
                      icon: const Icon(Icons.delete_forever),
                      onPressed: () async {
                        await deleteSingleFile(path);
                        if (mounted) setState(() {});
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(content: Text('Deleted $filename')),
                        );
                      },
                      tooltip: 'Delete',
                    ),
                  ],
                ),
              );
            }),
            const SizedBox(height: 8),
            Align(
              alignment: Alignment.centerRight,
              child: TextButton.icon(
                icon: const Icon(Icons.delete_sweep),
                label: const Text('Delete all for this meeting'),
                onPressed: () async {
                  await deleteMeetingFiles(widget.meetingId);
                  await localDb.removeByMeeting(widget.meetingId);
                  if (mounted) setState(() {});
                },
              ),
            ),
          ],
        );
      },
    );
  }
}

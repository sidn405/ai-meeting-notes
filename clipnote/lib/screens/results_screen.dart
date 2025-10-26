import 'package:flutter/material.dart';
import 'package:clipnote/services/api_service.dart';
import '../models/meeting.dart';
import 'package:flutter/services.dart';

class ResultsScreen extends StatefulWidget {
  final int meetingId;

  const ResultsScreen({super.key, required this.meetingId});

  @override
  State<ResultsScreen> createState() => _ResultsScreenState();
}

class _ResultsScreenState extends State<ResultsScreen> {
  final _apiService = ApiService.I;
  Summary? _summary;
  bool _isLoading = true;
  bool _isUploading = false;
  String? _storageLocation;
  bool _canUploadToCloud = false;
  String? _userTier;

  @override
  void initState() {
    super.initState();
    _fetchSummary();
    _checkCloudStatus();
  }

  Future<void> _checkCloudStatus() async {
    try {
      final status = await _apiService.getCloudStatus(widget.meetingId);
      setState(() {
        _storageLocation = status['storage_location'];
        _canUploadToCloud = status['can_upload_to_cloud'] ?? false;
        _userTier = status['tier'];
      });
    } catch (e) {
      print('Error checking cloud status: $e');
    }
  }

  Future<void> _uploadToCloud() async {
    setState(() => _isUploading = true);
    
    try {
      final result = await _apiService.uploadMeetingToCloud(widget.meetingId);
      
      setState(() {
        _isUploading = false;
        _storageLocation = 'cloud';
        _canUploadToCloud = false;
      });
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(result['message'] ?? 'Uploaded to cloud successfully!'),
            backgroundColor: Colors.green,
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    } catch (e) {
      setState(() => _isUploading = false);
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to upload to cloud: $e'),
            backgroundColor: Colors.red,
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    }
  }

  Future<void> _downloadTranscript() async {
    try {
      await _apiService.downloadMeeting(widget.meetingId, 'transcript');
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Transcript downloaded successfully!'),
            backgroundColor: Colors.green,
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to download: $e'),
            backgroundColor: Colors.red,
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    }
  }

  Future<void> _downloadSummary() async {
    try {
      await _apiService.downloadMeeting(widget.meetingId, 'summary');
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Summary downloaded successfully!'),
            backgroundColor: Colors.green,
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to download: $e'),
            backgroundColor: Colors.red,
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    }
  }

  Future<void> _fetchSummary() async {
    try {
      final data = await _apiService.getMeetingSummary(widget.meetingId);
      setState(() {
        _summary = Summary.fromJson(data);
        _isLoading = false;
      });
    } catch (e) {
      print('Error fetching summary: $e');
      setState(() => _isLoading = false);
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
          'Meeting Summary',
          style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
        ),
        centerTitle: true,
        actions: [
          // Storage location indicator
          if (_storageLocation != null)
            Padding(
              padding: const EdgeInsets.only(right: 8.0),
              child: Center(
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  decoration: BoxDecoration(
                    color: _storageLocation == 'cloud' 
                        ? Colors.blue.withOpacity(0.2)
                        : Colors.white.withOpacity(0.2),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        _storageLocation == 'cloud' ? Icons.cloud_done : Icons.phone_android,
                        size: 16,
                        color: Colors.white,
                      ),
                      const SizedBox(width: 4),
                      Text(
                        _storageLocation == 'cloud' ? 'Cloud' : 'Local',
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          // Options menu
          PopupMenuButton<String>(
            icon: const Icon(Icons.more_vert, color: Colors.white),
            onSelected: (value) {
              if (value == 'download_transcript') {
                _downloadTranscript();
              } else if (value == 'download_summary') {
                _downloadSummary();
              } else if (value == 'upload_to_cloud') {
                _uploadToCloud();
              }
            },
            itemBuilder: (context) => [
              const PopupMenuItem(
                value: 'download_transcript',
                child: Row(
                  children: [
                    Icon(Icons.download, size: 20),
                    SizedBox(width: 12),
                    Text('Download Transcript'),
                  ],
                ),
              ),
              const PopupMenuItem(
                value: 'download_summary',
                child: Row(
                  children: [
                    Icon(Icons.download, size: 20),
                    SizedBox(width: 12),
                    Text('Download Summary'),
                  ],
                ),
              ),
              // Show upload to cloud for Pro/Business
              if (_canUploadToCloud && (_userTier == 'professional' || _userTier == 'business'))
                const PopupMenuItem(
                  value: 'upload_to_cloud',
                  child: Row(
                    children: [
                      Icon(Icons.cloud_upload, size: 20, color: Colors.blue),
                      SizedBox(width: 12),
                      Text('Upload to Cloud', style: TextStyle(color: Colors.blue)),
                    ],
                  ),
                ),
            ],
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
              : _summary == null
                  ? Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const Icon(Icons.error_outline, size: 60, color: Colors.white),
                          const SizedBox(height: 16),
                          const Text(
                            'No summary available',
                            style: TextStyle(color: Colors.white, fontSize: 18),
                          ),
                          const SizedBox(height: 24),
                          ElevatedButton(
                            onPressed: () => Navigator.of(context).pop(),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: Colors.white,
                              foregroundColor: const Color(0xFF667eea),
                            ),
                            child: const Text('Go Back'),
                          ),
                        ],
                      ),
                    )
                  : Stack(
                      children: [
                        _buildSummaryContent(_summary!),
                        // Show uploading overlay
                        if (_isUploading)
                          Container(
                            color: Colors.black54,
                            child: const Center(
                              child: Card(
                                child: Padding(
                                  padding: EdgeInsets.all(24.0),
                                  child: Column(
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      CircularProgressIndicator(),
                                      SizedBox(height: 16),
                                      Text(
                                        'Uploading to Cloud...',
                                        style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                                      ),
                                    ],
                                  ),
                                ),
                              ),
                            ),
                          ),
                      ],
                    ),
        ),
      ),
      floatingActionButton: _canUploadToCloud && !_isUploading
          ? FloatingActionButton.extended(
              onPressed: _uploadToCloud,
              backgroundColor: Colors.blue,
              icon: const Icon(Icons.cloud_upload),
              label: const Text('Upload to Cloud'),
            )
          : null,
    );
  }

  Widget _buildSummaryContent(Summary summary) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _buildSection(
          'Executive Summary',
          summary.executiveSummary,
          Icons.summarize,
        ),
        const SizedBox(height: 16),
        _buildDecisionsSection(summary),
        const SizedBox(height: 16),
        _buildActionItemsSection(summary),
      ],
    );
  }

  Widget _buildSection(String title, String content, IconData icon) {
    return Container(
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
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: const Color(0xFF667eea).withOpacity(0.1),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Icon(icon, color: const Color(0xFF667eea), size: 24),
                ),
                const SizedBox(width: 12),
                Text(
                  title,
                  style: const TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Text(
              content,
              style: const TextStyle(fontSize: 15, height: 1.6),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDecisionsSection(Summary summary) {
    return Container(
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
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: const Color(0xFF667eea).withOpacity(0.1),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Icon(Icons.check_circle, color: Color(0xFF667eea), size: 24),
                ),
                const SizedBox(width: 12),
                const Text(
                  'Key Decisions',
                  style: TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            if (summary.keyDecisions.isEmpty)
              const Text('No key decisions recorded')
            else
              ...summary.keyDecisions.asMap().entries.map(
                    (entry) => Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Container(
                            margin: const EdgeInsets.only(top: 4),
                            padding: const EdgeInsets.all(6),
                            decoration: const BoxDecoration(
                              color: Color(0xFF667eea),
                              shape: BoxShape.circle,
                            ),
                            child: Text(
                              '${entry.key + 1}',
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 10,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Text(
                              entry.value,
                              style: const TextStyle(fontSize: 15, height: 1.5),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
          ],
        ),
      ),
    );
  }

  Widget _buildActionItemsSection(Summary summary) {
    return Container(
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
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: const Color(0xFF667eea).withOpacity(0.1),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Icon(Icons.assignment, color: Color(0xFF667eea), size: 24),
                ),
                const SizedBox(width: 12),
                const Text(
                  'Action Items',
                  style: TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            if (summary.actionItems.isEmpty)
              const Text('No action items')
            else
              ...summary.actionItems.map(
                (item) => Container(
                  margin: const EdgeInsets.only(bottom: 12),
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: Colors.grey.shade50,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: Colors.grey.shade200),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              item.task ?? 'No task',
                              style: const TextStyle(
                                fontSize: 15,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                          if (item.priority != null)
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                              decoration: BoxDecoration(
                                color: _getPriorityColor(item.priority ?? 'Medium'),
                                borderRadius: BorderRadius.circular(12),
                              ),
                              child: Text(
                                item.priority ?? 'Medium',
                                style: const TextStyle(
                                  fontSize: 11,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ),
                        ],
                      ),
                      if (item.owner != null) ...[
                        const SizedBox(height: 8),
                        Row(
                          children: [
                            Icon(Icons.person_outline, size: 16, color: Colors.grey.shade600),
                            const SizedBox(width: 4),
                            Text(
                              item.owner!,
                              style: TextStyle(
                                fontSize: 13,
                                color: Colors.grey.shade700,
                              ),
                            ),
                          ],
                        ),
                      ],
                    ],
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Color _getPriorityColor(String priority) {
    switch (priority.toLowerCase()) {
      case 'high':
        return Colors.red.shade200;
      case 'medium':
        return Colors.orange.shade200;
      case 'low':
        return Colors.blue.shade200;
      default:
        return Colors.grey.shade200;
    }
  }
}
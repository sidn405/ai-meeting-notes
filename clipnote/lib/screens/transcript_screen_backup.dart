import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:clipnote/services/api_service.dart';

class TranscriptScreen extends StatefulWidget {
  final int meetingId;

  const TranscriptScreen({super.key, required this.meetingId});

  @override
  State<TranscriptScreen> createState() => _TranscriptScreenState();
}

class _TranscriptScreenState extends State<TranscriptScreen> {
  final _apiService = ApiService.I;
  String? _transcript;
  String? _meetingTitle;
  bool _isLoading = true;
  double _fontSize = 16.0;

  @override
  void initState() {
    super.initState();
    _fetchTranscript();
  }

  Future<void> _fetchTranscript() async {
    try {
      final data = await _apiService.getMeetingTranscript(widget.meetingId);
      setState(() {
        _transcript = data['transcript'];
        _meetingTitle = data['title'] ?? 'Meeting Transcript';
        _isLoading = false;
      });
    } catch (e) {
      print('Error fetching transcript: $e');
      setState(() => _isLoading = false);
    }
  }

  void _copyToClipboard() {
    if (_transcript != null) {
      Clipboard.setData(ClipboardData(text: _transcript!));
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Transcript copied to clipboard'),
          backgroundColor: Colors.green,
          duration: Duration(seconds: 2),
        ),
      );
    }
  }

  void _shareTranscript() {
    if (_transcript != null) {
      // Show share dialog with options
      _showShareDialog();
    }
  }

  void _showShareDialog() {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) => Container(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text(
              'Share Transcript',
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 20),
            ListTile(
              leading: const Icon(Icons.email, color: Color(0xFF667eea)),
              title: const Text('Email'),
              onTap: () {
                Navigator.pop(context);
                _emailTranscript();
              },
            ),
            ListTile(
              leading: const Icon(Icons.copy, color: Color(0xFF667eea)),
              title: const Text('Copy to Clipboard'),
              onTap: () {
                Navigator.pop(context);
                _copyToClipboard();
              },
            ),
            ListTile(
              leading: const Icon(Icons.download, color: Color(0xFF667eea)),
              title: const Text('Download as Text File'),
              onTap: () {
                Navigator.pop(context);
                _downloadTranscript();
              },
            ),
          ],
        ),
      ),
    );
  }

  void _emailTranscript() async {
    if (_transcript == null) return;
    
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Email Transcript'),
        content: const Text(
          'Email functionality requires additional setup.\n\n'
          'The transcript has been copied to your clipboard. '
          'You can paste it into your email app.',
        ),
        actions: [
          TextButton(
            onPressed: () {
              Navigator.pop(context);
              _copyToClipboard();
            },
            child: const Text('Copy & Close'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('OK'),
          ),
        ],
      ),
    );
  }

  void _downloadTranscript() async {
    if (_transcript == null) return;
    
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Download'),
        content: const Text(
          'To download files, please install these packages:\n\n'
          'path_provider: ^2.1.1\n'
          'permission_handler: ^11.0.1\n\n'
          'Then implement file download functionality.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('OK'),
          ),
        ],
      ),
    );
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
          'Transcript',
          style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
        ),
        centerTitle: true,
        actions: [
          IconButton(
            icon: const Icon(Icons.share, color: Colors.white),
            onPressed: _shareTranscript,
            tooltip: 'Share',
          ),
          PopupMenuButton<String>(
            icon: const Icon(Icons.more_vert, color: Colors.white),
            onSelected: (value) {
              if (value == 'copy') {
                _copyToClipboard();
              } else if (value == 'download') {
                _downloadTranscript();
              } else if (value == 'email') {
                _emailTranscript();
              }
            },
            itemBuilder: (context) => [
              const PopupMenuItem(
                value: 'copy',
                child: Row(
                  children: [
                    Icon(Icons.copy, size: 20),
                    SizedBox(width: 12),
                    Text('Copy'),
                  ],
                ),
              ),
              const PopupMenuItem(
                value: 'email',
                child: Row(
                  children: [
                    Icon(Icons.email, size: 20),
                    SizedBox(width: 12),
                    Text('Email'),
                  ],
                ),
              ),
              const PopupMenuItem(
                value: 'download',
                child: Row(
                  children: [
                    Icon(Icons.download, size: 20),
                    SizedBox(width: 12),
                    Text('Download'),
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
              : _transcript == null
                  ? _buildErrorState()
                  : _buildTranscriptContent(),
        ),
      ),
      floatingActionButton: _transcript != null
          ? FloatingActionButton(
              onPressed: _showFontSizeDialog,
              backgroundColor: Colors.white,
              child: const Icon(Icons.text_fields, color: Color(0xFF667eea)),
            )
          : null,
    );
  }

  Widget _buildErrorState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.error_outline, size: 60, color: Colors.white),
          const SizedBox(height: 16),
          const Text(
            'No transcript available',
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
    );
  }

  Widget _buildTranscriptContent() {
    return Column(
      children: [
        Container(
          margin: const EdgeInsets.all(16),
          padding: const EdgeInsets.all(16),
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
              const Icon(Icons.description, color: Colors.white, size: 20),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  _meetingTitle ?? 'Transcript',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ],
          ),
        ),
        Expanded(
          child: Container(
            margin: const EdgeInsets.fromLTRB(16, 0, 16, 16),
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
            child: ClipRRect(
              borderRadius: BorderRadius.circular(16),
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(20),
                child: SelectableText(
                  _transcript!,
                  style: TextStyle(
                    fontSize: _fontSize,
                    height: 1.6,
                    color: Colors.black87,
                  ),
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }

  void _showFontSizeDialog() {
    showDialog(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('Text Size'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text('Size:'),
                  Text(
                    '${_fontSize.toInt()}',
                    style: const TextStyle(fontWeight: FontWeight.bold),
                  ),
                ],
              ),
              Slider(
                value: _fontSize,
                min: 12,
                max: 24,
                divisions: 12,
                activeColor: const Color(0xFF667eea),
                onChanged: (value) {
                  setDialogState(() => _fontSize = value);
                  setState(() => _fontSize = value);
                },
              ),
              const SizedBox(height: 8),
              Text(
                'Preview Text',
                style: TextStyle(fontSize: _fontSize),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Close'),
            ),
          ],
        ),
      ),
    );
  }
}
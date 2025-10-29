import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:clipnote/services/api_service.dart';
import 'package:url_launcher/url_launcher.dart';

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
      _showShareDialog();
    }
  }

  void _showShareDialog() {
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.white,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) => SafeArea(
        child: Container(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: Colors.grey.shade300,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              const SizedBox(height: 16),
              const Text(
                'Share Transcript',
                style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 20),
              ListTile(
                leading: const CircleAvatar(
                  backgroundColor: Color(0xFFE3F2FD),
                  child: Icon(Icons.email, color: Color(0xFF667eea)),
                ),
                title: const Text('Email'),
                subtitle: const Text('Send transcript via email'),
                onTap: () {
                  Navigator.pop(context);
                  _showEmailDialog();
                },
              ),
              ListTile(
                leading: const CircleAvatar(
                  backgroundColor: Color(0xFFE8F5E9),
                  child: Icon(Icons.copy, color: Colors.green),
                ),
                title: const Text('Copy to Clipboard'),
                subtitle: const Text('Copy transcript text'),
                onTap: () {
                  Navigator.pop(context);
                  _copyToClipboard();
                },
              ),
              //ListTile(
                //leading: const CircleAvatar(
                  //backgroundColor: Color(0xFFFFF3E0),
                  //child: Icon(Icons.download, color: Colors.orange),
                //),
                //title: const Text('Download'),
                //subtitle: const Text('Download as text file'),
                //onTap: () {
                 // Navigator.pop(context);
                  //_downloadTranscript();
                //},
              //),
            ],
          ),
        ),
      ),
    );
  }

  void _showEmailDialog() {
    final emailController = TextEditingController();
    bool isSending = false;

    showDialog(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('Email Transcript'),
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
                'Transcript for: ${_meetingTitle ?? "Meeting"}',
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
                        await _apiService.sendMeetingEmail(widget.meetingId, email);
                        
                        if (!mounted) return;
                        Navigator.pop(context);
                        
                        ScaffoldMessenger.of(this.context).showSnackBar(
                          SnackBar(
                            content: Text('Transcript sent to $email'),
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

  void _downloadTranscript() async {
    if (_transcript == null) return;

    try {
      // Get download URL from API
      final downloadInfo = await _apiService.downloadMeetingFile(
        widget.meetingId,
        'transcript',
      );
      
      final url = downloadInfo['download_url'];
      final uri = Uri.parse(url);
      
      if (await canLaunchUrl(uri)) {
        await launchUrl(uri, mode: LaunchMode.externalApplication);
        
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Download started...'),
            backgroundColor: Colors.green,
            duration: Duration(seconds: 2),
          ),
        );
      } else {
        throw Exception('Could not open download URL');
      }
    } catch (e) {
      print('Error downloading transcript: $e');
      
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Download failed: ${e.toString().replaceAll("Exception: ", "")}'),
          backgroundColor: Colors.red,
        ),
      );
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
          const SizedBox(width: 8),
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
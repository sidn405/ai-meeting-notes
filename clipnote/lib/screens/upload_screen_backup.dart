import 'dart:typed_data';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:clipnote/services/api_service.dart';
import 'package:clipnote/screens/progress_screen.dart';

class UploadScreen extends StatefulWidget {
  const UploadScreen({super.key});

  @override
  State<UploadScreen> createState() => _UploadScreenState();
}

class _UploadScreenState extends State<UploadScreen> {
  final api = ApiService.I;
  
  final List<Map<String, String>> _languages = [
    {'code': 'auto', 'name': 'Auto-Detect'},
    {'code': 'en', 'name': 'English'},
    {'code': 'es', 'name': 'Spanish'},
    {'code': 'fr', 'name': 'French'},
    {'code': 'de', 'name': 'German'},
    {'code': 'it', 'name': 'Italian'},
    {'code': 'pt', 'name': 'Portuguese'},
    {'code': 'nl', 'name': 'Dutch'},
    {'code': 'pl', 'name': 'Polish'},
    {'code': 'ru', 'name': 'Russian'},
    {'code': 'zh', 'name': 'Chinese'},
    {'code': 'ja', 'name': 'Japanese'},
    {'code': 'ko', 'name': 'Korean'},
    {'code': 'ar', 'name': 'Arabic'},
    {'code': 'hi', 'name': 'Hindi'},
    {'code': 'tr', 'name': 'Turkish'},
    {'code': 'vi', 'name': 'Vietnamese'},
    {'code': 'th', 'name': 'Thai'},
    {'code': 'sv', 'name': 'Swedish'},
    {'code': 'da', 'name': 'Danish'},
  ];

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
        title: const Text(
          'Upload Your Meeting',
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
          child: ListView(
            padding: const EdgeInsets.all(20),
            children: [
              const Center(
                child: Text(
                  'AI-powered transcription and summarization in minutes',
                  style: TextStyle(color: Colors.white70, fontSize: 14),
                  textAlign: TextAlign.center,
                ),
              ),
              const SizedBox(height: 24),
              
              _sectionCard(
                title: 'From Transcript (No Audio)',
                badge: 'AI Summarization',
                onTap: _showTranscriptDialog,
              ),
              
              const SizedBox(height: 16),
              
              _sectionCard(
                title: 'Upload Meeting (Audio/Video)',
                badge: 'AI-Powered',
                badgeColor: const Color(0xFF764ba2),
                trailing: const Text(
                  'Multi-Language',
                  style: TextStyle(fontSize: 12, color: Colors.white70),
                ),
                onTap: _showMediaDialog,
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _sectionCard({
    required String title,
    required String badge,
    Color badgeColor = const Color(0xFF667eea),
    Widget? trailing,
    required VoidCallback onTap,
  }) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.1),
            blurRadius: 10,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(12),
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Flexible(
                            child: Text(
                              title,
                              style: const TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                            decoration: BoxDecoration(
                              color: badgeColor,
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Text(
                              badge,
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 10,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                        ],
                      ),
                      if (trailing != null) ...[
                        const SizedBox(height: 4),
                        trailing,
                      ],
                    ],
                  ),
                ),
                const Icon(Icons.arrow_forward_ios, size: 16, color: Colors.grey),
              ],
            ),
          ),
        ),
      ),
    );
  }

  void _showTranscriptDialog() {
    final titleCtrl = TextEditingController();
    final transcriptCtrl = TextEditingController();
    bool isSubmitting = false;
    
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      backgroundColor: Colors.white,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (c) {
        return StatefulBuilder(
          builder: (context, setModalState) {
            return Padding(
              padding: EdgeInsets.only(
                left: 20,
                right: 20,
                top: 8,
                bottom: MediaQuery.of(c).viewInsets.bottom + 20,
              ),
              child: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'From Transcript',
                      style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 20),
                    
                    TextField(
                      controller: titleCtrl,
                      textInputAction: TextInputAction.next,
                      enabled: !isSubmitting,
                      decoration: InputDecoration(
                        labelText: 'Title (optional)',
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(8),
                        ),
                        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                      ),
                    ),
                    
                    const SizedBox(height: 16),
                    
                    TextField(
                      controller: transcriptCtrl,
                      maxLines: 5,
                      enabled: !isSubmitting,
                      decoration: InputDecoration(
                        labelText: 'Paste transcript text',
                        alignLabelWithHint: true,
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(8),
                        ),
                        contentPadding: const EdgeInsets.all(16),
                      ),
                    ),
                    
                    const SizedBox(height: 20),
                    
                    SizedBox(
                      width: double.infinity,
                      height: 48,
                      child: ElevatedButton.icon(
                        onPressed: isSubmitting ? null : () async {
                          if (transcriptCtrl.text.trim().isEmpty) {
                            ScaffoldMessenger.of(this.context).showSnackBar(
                              const SnackBar(content: Text('Please enter transcript text')),
                            );
                            return;
                          }
                          
                          setModalState(() => isSubmitting = true);
                          
                          try {
                            print('Submitting transcript...');
                            final meetingId = await api.submitTranscript(
                              title: titleCtrl.text.trim().isEmpty 
                                  ? 'Untitled Meeting' 
                                  : titleCtrl.text.trim(),
                              transcript: transcriptCtrl.text,
                            );
                            
                            print('Transcript submitted, meeting ID: $meetingId');
                            
                            if (!mounted) return;
                            Navigator.pop(c);
                            Navigator.of(this.context).pushReplacement(
                              MaterialPageRoute(
                                builder: (_) => ProgressScreen(meetingId: meetingId),
                              ),
                            );
                          } catch (e) {
                            print('Error submitting transcript: $e');
                            setModalState(() => isSubmitting = false);
                            if (!mounted) return;
                            
                            String errorMessage = 'Error: $e';
                            if (e.toString().contains('TimeoutException')) {
                              errorMessage = 'Request timed out. Please check your internet connection.';
                            } else if (e.toString().contains('SocketException')) {
                              errorMessage = 'Cannot connect to server. Please check your internet connection.';
                            }
                            
                            ScaffoldMessenger.of(this.context).showSnackBar(
                              SnackBar(
                                content: Text(errorMessage),
                                duration: const Duration(seconds: 5),
                                backgroundColor: Colors.red,
                              ),
                            );
                          }
                        },
                        icon: isSubmitting 
                            ? const SizedBox(
                                width: 20,
                                height: 20,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                                ),
                              )
                            : const Icon(Icons.auto_awesome),
                        label: Text(
                          isSubmitting ? 'Processing...' : 'Summarize',
                          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                        ),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: const Color(0xFF667eea),
                          foregroundColor: Colors.white,
                          disabledBackgroundColor: Colors.grey,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(8),
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            );
          },
        );
      },
    );
  }

  void _showMediaDialog() {
    final titleCtrl = TextEditingController();
    final emailCtrl = TextEditingController();
    final hintsCtrl = TextEditingController();
    String selectedLanguage = 'auto';
    bool saveToCloud = false;  // ADD THIS LINE
    bool isSubmitting = false;
    
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      backgroundColor: Colors.white,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (c) {
        return StatefulBuilder(
          builder: (context, setModalState) {
            return Padding(
              padding: EdgeInsets.only(
                left: 20,
                right: 20,
                top: 8,
                bottom: MediaQuery.of(c).viewInsets.bottom + 20,
              ),
              child: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Upload Meeting (Audio/Video)',
                      style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 4),
                    const Text(
                      'Upload audio or video files for automatic transcription and AI summarization.',
                      style: TextStyle(fontSize: 12, color: Colors.grey),
                    ),
                    
                    const SizedBox(height: 16),
                    
                    TextField(
                      controller: titleCtrl,
                      textInputAction: TextInputAction.next,
                      decoration: InputDecoration(
                        labelText: 'Meeting Title',
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(8),
                        ),
                        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                      ),
                    ),
                    
                    const SizedBox(height: 12),
                    
                    TextField(
                      controller: emailCtrl,
                      keyboardType: TextInputType.emailAddress,
                      decoration: InputDecoration(
                        labelText: 'Email results to (optional)',
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(8),
                        ),
                        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                        suffixIcon: const Icon(Icons.email, color: Color(0xFF667eea), size: 20),
                      ),
                    ),
                    
                    const SizedBox(height: 12),
                    
                    DropdownButtonFormField<String>(
                      value: selectedLanguage,
                      decoration: InputDecoration(
                        labelText: 'Language',
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(8),
                        ),
                        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                        prefixIcon: const Icon(Icons.language, color: Color(0xFF667eea), size: 20),
                      ),
                      items: _languages.map((lang) {
                        return DropdownMenuItem<String>(
                          value: lang['code'],
                          child: Text(lang['name']!),
                        );
                      }).toList(),
                      onChanged: (value) {
                        setModalState(() => selectedLanguage = value!);
                      },
                    ),
                    
                    const SizedBox(height: 12),
                    
                    TextField(
                      controller: hintsCtrl,
                      decoration: InputDecoration(
                        labelText: 'Hints / Terminology (optional)',
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(8),
                        ),
                        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                        helperText: 'Comma separated names, acronyms, or industry jargon',
                        helperMaxLines: 2,
                      ),
                    ),
                    
                    const SizedBox(height: 12),
                    
                    // Storage Toggle
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: Colors.grey.shade50,
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: Colors.grey.shade300),
                      ),
                      child: Row(
                        children: [
                          Icon(
                            saveToCloud ? Icons.cloud : Icons.phone_android,
                            color: const Color(0xFF667eea),
                            size: 20,
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  saveToCloud ? 'Save to Cloud' : 'Save to Device',
                                  style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14),
                                ),
                                Text(
                                  saveToCloud ? 'Pro feature' : 'Free tier storage',
                                  style: TextStyle(fontSize: 11, color: Colors.grey.shade600),
                                ),
                              ],
                            ),
                          ),
                          Switch(
                            value: saveToCloud,
                            onChanged: (val) {
                              setModalState(() => saveToCloud = val);
                            },
                            activeColor: const Color(0xFF667eea),
                          ),
                        ],
                      ),
                    ),
                    
                    const SizedBox(height: 16),
                    
                    // Audio/Video File Section
                    const Text(
                      'Audio/Video File',
                      style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
                    ),
                    const SizedBox(height: 8),
                    
                    OutlinedButton.icon(
                      onPressed: isSubmitting ? null : () async {
                        Navigator.pop(c);
                        await _pickAndUploadFile(
                          title: titleCtrl.text.trim(),
                          email: emailCtrl.text.trim(),
                          language: selectedLanguage,
                          hints: hintsCtrl.text.trim(),
                          saveToCloud: saveToCloud,
                          transcribeOnly: false,
                        );
                      },
                      icon: const Icon(Icons.upload_file, size: 20),
                      label: const Text('Browse'),
                      style: OutlinedButton.styleFrom(
                        minimumSize: const Size(double.infinity, 40),
                        side: BorderSide(color: Colors.grey.shade400),
                        foregroundColor: Colors.black87,
                      ),
                    ),
                    
                    const SizedBox(height: 6),
                    const Text(
                      'Supported formats: .mp3, .m4a, .wav, .mp4, .mov, .mkv, .webm',
                      style: TextStyle(fontSize: 11, color: Colors.grey),
                    ),
                    
                    const SizedBox(height: 16),
                    
                    // Action Buttons
                    Row(
                      children: [
                        Expanded(
                          child: OutlinedButton.icon(
                            onPressed: isSubmitting ? null : () async {
                              setModalState(() => isSubmitting = true);
                              Navigator.pop(c);
                              await _pickAndUploadFile(
                                title: titleCtrl.text.trim(),
                                email: emailCtrl.text.trim(),
                                language: selectedLanguage,
                                hints: hintsCtrl.text.trim(),
                                saveToCloud: saveToCloud,
                                transcribeOnly: true,
                              );
                            },
                            icon: const Icon(Icons.description, size: 18),
                            label: const Text('Transcribe Only'),
                            style: OutlinedButton.styleFrom(
                              minimumSize: const Size(0, 44),
                              side: const BorderSide(color: Color(0xFF667eea)),
                              foregroundColor: const Color(0xFF667eea),
                            ),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: ElevatedButton.icon(
                            onPressed: isSubmitting ? null : () async {
                              setModalState(() => isSubmitting = true);
                              Navigator.pop(c);
                              await _pickAndUploadFile(
                                title: titleCtrl.text.trim(),
                                email: emailCtrl.text.trim(),
                                language: selectedLanguage,
                                hints: hintsCtrl.text.trim(),
                                saveToCloud: saveToCloud,
                                transcribeOnly: false,
                              );
                            },
                            icon: const Icon(Icons.auto_awesome, size: 18),
                            label: const Text('Transcribe & Summarize'),
                            style: ElevatedButton.styleFrom(
                              minimumSize: const Size(0, 44),
                              backgroundColor: const Color(0xFF667eea),
                              foregroundColor: Colors.white,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            );
          },
        );
      },
    );
  }

  Future<void> _pickAndUploadFile({
    required String title,
    required String email,
    required String language,
    required String hints,
    required bool saveToCloud,      // ADD THIS
    required bool transcribeOnly,
  }) async {
    try {
      print('Starting file picker...');
      final result = await FilePicker.platform.pickFiles(
        allowMultiple: false,
        withData: true,
        type: FileType.custom,
        allowedExtensions: const ['m4a', 'mp3', 'wav', 'aac', 'mp4', 'mov', 'mkv', 'webm'],
      );
      
      if (result == null || result.files.single.bytes == null) {
        print('File picker cancelled');
        return;
      }

      final PlatformFile file = result.files.single;
      final Uint8List bytes = file.bytes!;
      final filename = file.name;

      print('File selected: $filename (${bytes.length} bytes)');

      if (!mounted) return;
      showDialog(
        context: context,
        barrierDismissible: false,
        builder: (c) => const Center(child: CircularProgressIndicator()),
      );

      print('Uploading meeting to backend...');
      final meetingId = await api.uploadMeeting(
        title: title.isEmpty ? 'Untitled Meeting' : title,
        fileBytes: bytes,
        filename: filename,
        email: email.isEmpty ? null : email,
        language: language == 'auto' ? null : language,
        hints: hints.isEmpty ? null : hints,
        
      );
      
      print('Meeting uploaded successfully: $meetingId');

      if (!mounted) return;
      Navigator.pop(context); // Close loading dialog
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(
          builder: (_) => ProgressScreen(meetingId: meetingId),
        ),
      );
    } catch (e) {
      print('Upload error: $e');
      if (!mounted) return;
      Navigator.pop(context); // Close loading dialog
      
      String errorMessage = 'Upload failed: $e';
      if (e.toString().contains('TimeoutException')) {
        errorMessage = 'Upload timed out. This file might be too large or your connection is slow. Please try again.';
      } else if (e.toString().contains('SocketException')) {
        errorMessage = 'Cannot connect to server. Please check your internet connection.';
      } else if (e.toString().contains('413')) {
        errorMessage = 'File is too large for your account tier. Please upgrade or use a smaller file.';
      }
      
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(errorMessage),
          duration: const Duration(seconds: 5),
          backgroundColor: Colors.red,
        ),
      );
    }
  }
}

  String _guessMime(String filename) {
    final f = filename.toLowerCase();
    if (f.endsWith('.m4a')) return 'audio/m4a';
    if (f.endsWith('.mp3')) return 'audio/mpeg';
    if (f.endsWith('.wav')) return 'audio/wav';
    if (f.endsWith('.aac')) return 'audio/aac';
    if (f.endsWith('.mp4')) return 'video/mp4';
    if (f.endsWith('.mov')) return 'video/quicktime';
    if (f.endsWith('.mkv')) return 'video/x-matroska';
    if (f.endsWith('.webm')) return 'video/webm';
    return 'application/octet-stream';
  }

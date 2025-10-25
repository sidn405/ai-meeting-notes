import 'dart:typed_data';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:clipnote/services/api_service.dart';
import 'package:clipnote/screens/progress_screen.dart';
import 'package:clipnote/screens/transcript_screen.dart';
import 'package:image_picker/image_picker.dart';

class UploadScreen extends StatefulWidget {
  const UploadScreen({super.key});

  @override
  State<UploadScreen> createState() => _UploadScreenState();
}

class _UploadScreenState extends State<UploadScreen> {
  final api = ApiService.I;
  final _picker = ImagePicker();
  
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
    final currentTier = api.currentTier ?? 'free';
    final isBusinessTier = currentTier == 'business';

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

              const SizedBox(height: 16),
              
              _sectionCard(
                title: 'Record Video',
                badge: 'Business Only',
                badgeColor: Colors.orange,
                trailing: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      Icons.videocam,
                      size: 16,
                      color: isBusinessTier ? Colors.white70 : Colors.grey.shade400,
                    ),
                    const SizedBox(width: 4),
                    Text(
                      'Live Camera',
                      style: TextStyle(
                        fontSize: 12,
                        color: isBusinessTier ? Colors.white70 : Colors.grey.shade400,
                      ),
                    ),
                  ],
                ),
                onTap: isBusinessTier
                    ? _showRecordVideoDialog
                    : () => _showUpgradePrompt(),
                opacity: isBusinessTier ? 1.0 : 0.6,
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
    double opacity = 1.0,
  }) {
    return Opacity(
      opacity: opacity,
      child: Container(
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
      ),
    );
  }

  void _showUpgradePrompt() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Row(
          children: [
            Icon(Icons.lock, color: Colors.orange.shade700),
            const SizedBox(width: 12),
            const Text('Business Feature'),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Live video recording is exclusive to Business tier subscribers.',
              style: TextStyle(fontSize: 16),
            ),
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.orange.shade50,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: Colors.orange.shade200),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Business Tier Includes:',
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      color: Colors.orange.shade900,
                    ),
                  ),
                  const SizedBox(height: 8),
                  _featureItem('📹 Live video recording'),
                  _featureItem('100 meetings/month'),
                  _featureItem('500MB max file size'),
                  _featureItem('Priority processing'),
                ],
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(context);
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('Upgrade to Business tier from home screen'),
                  backgroundColor: Colors.orange,
                ),
              );
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.orange,
              foregroundColor: Colors.white,
            ),
            child: const Text('Upgrade'),
          ),
        ],
      ),
    );
  }

  Widget _featureItem(String text) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Text(text, style: const TextStyle(fontSize: 14)),
    );
  }

  void _showTranscriptDialog() {
    final titleCtrl = TextEditingController();
    final transcriptCtrl = TextEditingController();
    final emailCtrl = TextEditingController();
    final hintsCtrl = TextEditingController();
    String selectedLanguage = 'auto';
    bool saveToCloud = false;
    bool isSubmitting = false;
    PlatformFile? selectedFile;
    
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
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Flexible(
                    child: SingleChildScrollView(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            'From Transcript (No Audio)',
                            style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
                          ),
                          const SizedBox(height: 4),
                          const Text(
                            'Paste or upload transcript text for AI summarization',
                            style: TextStyle(fontSize: 12, color: Colors.grey),
                          ),
                          
                          const SizedBox(height: 16),
                          
                          TextField(
                            controller: titleCtrl,
                            textInputAction: TextInputAction.next,
                            enabled: !isSubmitting,
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
                            textInputAction: TextInputAction.next,
                            enabled: !isSubmitting,
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
                            onChanged: isSubmitting ? null : (value) {
                              setModalState(() => selectedLanguage = value!);
                            },
                          ),
                          
                          const SizedBox(height: 12),
                          
                          TextField(
                            controller: hintsCtrl,
                            enabled: !isSubmitting,
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
                                  onChanged: isSubmitting ? null : (val) {
                                    setModalState(() => saveToCloud = val);
                                  },
                                  activeColor: const Color(0xFF667eea),
                                ),
                              ],
                            ),
                          ),
                          
                          const SizedBox(height: 16),
                          
                          const Text(
                            'Transcript Text',
                            style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
                          ),
                          const SizedBox(height: 8),
                          
                          OutlinedButton.icon(
                            onPressed: isSubmitting ? null : () async {
                              try {
                                final result = await FilePicker.platform.pickFiles(
                                  allowMultiple: false,
                                  withData: true,
                                  type: FileType.custom,
                                  allowedExtensions: const ['txt', 'doc', 'docx', 'pdf'],
                                );
                                
                                if (result != null && result.files.single.bytes != null) {
                                  final bytes = result.files.single.bytes!;
                                  final text = String.fromCharCodes(bytes);
                                  
                                  setModalState(() {
                                    selectedFile = result.files.single;
                                    transcriptCtrl.text = text;
                                  });
                                }
                              } catch (e) {
                                print('File picker error: $e');
                                ScaffoldMessenger.of(this.context).showSnackBar(
                                  SnackBar(content: Text('Error reading file: $e')),
                                );
                              }
                            },
                            icon: Icon(
                              selectedFile != null ? Icons.check_circle : Icons.upload_file,
                              size: 20,
                              color: selectedFile != null ? Colors.green : null,
                            ),
                            label: Text(selectedFile != null ? 'File Loaded' : 'Browse Text File'),
                            style: OutlinedButton.styleFrom(
                              minimumSize: const Size(double.infinity, 40),
                              side: BorderSide(
                                color: selectedFile != null ? Colors.green : Colors.grey.shade400,
                              ),
                              foregroundColor: selectedFile != null ? Colors.green : Colors.black87,
                            ),
                          ),
                          
                          if (selectedFile != null) ...[
                            const SizedBox(height: 8),
                            Container(
                              padding: const EdgeInsets.all(8),
                              decoration: BoxDecoration(
                                color: Colors.green.shade50,
                                borderRadius: BorderRadius.circular(4),
                                border: Border.all(color: Colors.green.shade200),
                              ),
                              child: Row(
                                children: [
                                  const Icon(Icons.attach_file, size: 16, color: Colors.green),
                                  const SizedBox(width: 8),
                                  Expanded(
                                    child: Text(
                                      selectedFile!.name,
                                      style: const TextStyle(fontSize: 12),
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  ),
                                  Text(
                                    '${(selectedFile!.size / 1024).toStringAsFixed(1)} KB',
                                    style: TextStyle(fontSize: 11, color: Colors.grey.shade600),
                                  ),
                                ],
                              ),
                            ),
                          ],
                          
                          const SizedBox(height: 8),
                          
                          TextField(
                            controller: transcriptCtrl,
                            maxLines: 8,
                            enabled: !isSubmitting,
                            decoration: InputDecoration(
                              hintText: 'Paste your meeting transcript here...',
                              alignLabelWithHint: true,
                              border: OutlineInputBorder(
                                borderRadius: BorderRadius.circular(8),
                              ),
                              contentPadding: const EdgeInsets.all(16),
                            ),
                          ),
                          
                          const SizedBox(height: 6),
                          const Text(
                            'Supported file formats: .txt, .doc, .docx, .pdf',
                            style: TextStyle(fontSize: 11, color: Colors.grey),
                          ),
                        ],
                      ),
                    ),
                  ),
                  
                  const SizedBox(height: 16),
                  SafeArea(
                    top: false,
                    child: SizedBox(
                      width: double.infinity,
                      height: 48,
                      child: ElevatedButton.icon(
                        onPressed: (isSubmitting || transcriptCtrl.text.trim().isEmpty) 
                            ? null 
                            : () async {
                          setModalState(() => isSubmitting = true);
                          
                          try {
                            print('Submitting transcript...');
                            final meetingId = await api.submitTranscript(
                              title: titleCtrl.text.trim().isEmpty 
                                  ? 'Untitled Meeting' 
                                  : titleCtrl.text.trim(),
                              transcript: transcriptCtrl.text,
                              email: emailCtrl.text.trim().isEmpty ? null : emailCtrl.text.trim(),
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
                  ),
                ],
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
    bool saveToCloud = false;
    bool isSubmitting = false;
    PlatformFile? selectedFile;
    
    final tierLimits = {
      'free': 25,
      'starter': 50,
      'professional': 200,
      'business': 500,
    };
    
    final currentTier = api.currentTier;
    final maxFileSizeMB = tierLimits[currentTier] ?? 25;
    
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
            final fileSizeMB = selectedFile != null 
                ? (selectedFile!.size / (1024 * 1024)) 
                : 0.0;
            final isFileTooLarge = fileSizeMB > maxFileSizeMB;
            
            return Padding(
              padding: EdgeInsets.only(
                left: 20,
                right: 20,
                top: 8,
                bottom: MediaQuery.of(c).viewInsets.bottom + 20,
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Flexible(
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
                    Text(
                      'Upload audio or video files for automatic transcription and AI summarization. Max file size: ${maxFileSizeMB}MB',
                      style: const TextStyle(fontSize: 12, color: Colors.grey),
                    ),
                    
                    const SizedBox(height: 16),
                    
                    TextField(
                      controller: titleCtrl,
                      textInputAction: TextInputAction.next,
                      enabled: !isSubmitting,
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
                      enabled: !isSubmitting,
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
                      onChanged: isSubmitting ? null : (value) {
                        setModalState(() => selectedLanguage = value!);
                      },
                    ),
                    
                    const SizedBox(height: 12),
                    
                    TextField(
                      controller: hintsCtrl,
                      enabled: !isSubmitting,
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
                            onChanged: isSubmitting ? null : (val) {
                              setModalState(() => saveToCloud = val);
                            },
                            activeColor: const Color(0xFF667eea),
                          ),
                        ],
                      ),
                    ),
                    
                    const SizedBox(height: 16),
                    
                    const Text(
                      'Audio/Video File',
                      style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
                    ),
                    const SizedBox(height: 8),
                    
                    OutlinedButton.icon(
                      onPressed: isSubmitting ? null : () async {
                        try {
                          final result = await FilePicker.platform.pickFiles(
                            allowMultiple: false,
                            withData: true,
                            type: FileType.custom,
                            allowedExtensions: const ['m4a', 'mp3', 'wav', 'aac', 'mp4', 'mov', 'mkv', 'webm'],
                          );
                          
                          if (result != null && result.files.single.bytes != null) {
                            setModalState(() {
                              selectedFile = result.files.single;
                            });
                          }
                        } catch (e) {
                          print('File picker error: $e');
                          ScaffoldMessenger.of(this.context).showSnackBar(
                            SnackBar(content: Text('Error selecting file: $e')),
                          );
                        }
                      },
                      icon: Icon(
                        selectedFile != null ? Icons.check_circle : Icons.upload_file, 
                        size: 20,
                        color: selectedFile != null 
                            ? (isFileTooLarge ? Colors.orange : Colors.green)
                            : null,
                      ),
                      label: Text(selectedFile != null ? 'File Selected' : 'Browse Files'),
                      style: OutlinedButton.styleFrom(
                        minimumSize: const Size(double.infinity, 40),
                        side: BorderSide(
                          color: selectedFile != null 
                              ? (isFileTooLarge ? Colors.orange : Colors.green)
                              : Colors.grey.shade400,
                        ),
                        foregroundColor: selectedFile != null 
                            ? (isFileTooLarge ? Colors.orange : Colors.green)
                            : Colors.black87,
                      ),
                    ),
                    
                    if (selectedFile != null) ...[
                      const SizedBox(height: 8),
                      Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: isFileTooLarge ? Colors.orange.shade50 : Colors.green.shade50,
                          borderRadius: BorderRadius.circular(4),
                          border: Border.all(
                            color: isFileTooLarge ? Colors.orange.shade200 : Colors.green.shade200
                          ),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Icon(
                                  isFileTooLarge ? Icons.warning : Icons.attach_file,
                                  size: 16,
                                  color: isFileTooLarge ? Colors.orange : Colors.green,
                                ),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: Text(
                                    selectedFile!.name,
                                    style: const TextStyle(fontSize: 12),
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                ),
                                Text(
                                  '${fileSizeMB.toStringAsFixed(1)} MB',
                                  style: TextStyle(
                                    fontSize: 11,
                                    color: isFileTooLarge ? Colors.orange : Colors.grey.shade600,
                                    fontWeight: isFileTooLarge ? FontWeight.bold : FontWeight.normal,
                                  ),
                                ),
                              ],
                            ),
                            if (isFileTooLarge) ...[
                              const SizedBox(height: 4),
                              Text(
                                '⚠️ File exceeds ${maxFileSizeMB}MB limit for $currentTier tier',
                                style: const TextStyle(fontSize: 11, color: Colors.orange),
                              ),
                            ],
                          ],
                        ),
                      ),
                    ],
                    
                    const SizedBox(height: 6),
                    const Text(
                      'Supported formats: .mp3, .m4a, .wav, .mp4, .mov, .mkv, .webm',
                      style: TextStyle(fontSize: 11, color: Colors.grey),
                    ),
                    
                    if (isFileTooLarge) ...[
                      const SizedBox(height: 12),
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          gradient: const LinearGradient(
                            colors: [Color(0xFF667eea), Color(0xFF764ba2)],
                          ),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Row(
                          children: [
                            const Icon(Icons.rocket_launch, color: Colors.white, size: 20),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  const Text(
                                    'Upgrade to upload larger files',
                                    style: TextStyle(
                                      color: Colors.white,
                                      fontWeight: FontWeight.w600,
                                      fontSize: 13,
                                    ),
                                  ),
                                  const SizedBox(height: 2),
                                  Text(
                                    'Starter: 50MB • Pro: 200MB • Business: 500MB',
                                    style: TextStyle(
                                      color: Colors.white.withOpacity(0.9),
                                      fontSize: 11,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            const Icon(Icons.arrow_forward, color: Colors.white, size: 16),
                          ],
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ),
            
            const SizedBox(height: 16),
            SafeArea(
              top: false,
              child: Padding(
                padding: const EdgeInsets.only(left: 20, right: 20, bottom: 20),
                child: Row(
                  children: [
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: (isSubmitting || selectedFile == null || isFileTooLarge) 
                            ? null 
                            : () async {
                          setModalState(() => isSubmitting = true);
                          Navigator.pop(c);
                          await _uploadSelectedFile(
                            file: selectedFile!,
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
                          minimumSize: const Size(0, 48),
                          side: const BorderSide(color: Color(0xFF667eea)),
                          foregroundColor: const Color(0xFF667eea),
                        ),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: ElevatedButton.icon(
                        onPressed: (isSubmitting || selectedFile == null || isFileTooLarge) 
                            ? null 
                            : () async {
                          setModalState(() => isSubmitting = true);
                          Navigator.pop(c);
                          await _uploadSelectedFile(
                            file: selectedFile!,
                            title: titleCtrl.text.trim(),
                            email: emailCtrl.text.trim(),
                            language: selectedLanguage,
                            hints: hintsCtrl.text.trim(),
                            saveToCloud: saveToCloud,
                            transcribeOnly: false,
                          );
                        },
                        icon: isSubmitting 
                            ? const SizedBox(
                                width: 16,
                                height: 16,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                                ),
                              )
                            : const Icon(Icons.auto_awesome, size: 16),
                        label: const Text(
                          'Transcribe &\nSummarize',
                          style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, height: 1.2),
                          textAlign: TextAlign.center,
                        ),
                        style: ElevatedButton.styleFrom(
                          minimumSize: const Size(0, 56),
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
                          backgroundColor: const Color(0xFF667eea),
                          foregroundColor: Colors.white,
                          disabledBackgroundColor: Colors.grey,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
            );
          },
        );
      },
    );
  }

  void _showRecordVideoDialog() {
    final titleCtrl = TextEditingController();
    final emailCtrl = TextEditingController();
    final hintsCtrl = TextEditingController();
    String selectedLanguage = 'auto';
    bool saveToCloud = false;
    bool isRecording = false;
    bool isSubmitting = false;
    Uint8List? recordedVideoBytes;
    String? recordedVideoName;
    
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
            final videoSizeMB = recordedVideoBytes != null 
                ? (recordedVideoBytes!.length / (1024 * 1024)) 
                : 0.0;

            return Padding(
              padding: EdgeInsets.only(
                left: 20,
                right: 20,
                top: 8,
                bottom: MediaQuery.of(c).viewInsets.bottom + 20,
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Flexible(
                    child: SingleChildScrollView(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              const Expanded(
                                child: Text(
                                  'Record Video',
                                  style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
                                ),
                              ),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                decoration: BoxDecoration(
                                  color: Colors.orange,
                                  borderRadius: BorderRadius.circular(12),
                                ),
                                child: const Text(
                                  'BUSINESS',
                                  style: TextStyle(
                                    color: Colors.white,
                                    fontSize: 10,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 4),
                          const Text(
                            'Record video directly from your camera for transcription and AI summarization',
                            style: TextStyle(fontSize: 12, color: Colors.grey),
                          ),
                          
                          const SizedBox(height: 16),
                          
                          TextField(
                            controller: titleCtrl,
                            textInputAction: TextInputAction.next,
                            enabled: !isSubmitting,
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
                            enabled: !isSubmitting,
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
                            onChanged: isSubmitting ? null : (value) {
                              setModalState(() => selectedLanguage = value!);
                            },
                          ),
                          
                          const SizedBox(height: 12),
                          
                          TextField(
                            controller: hintsCtrl,
                            enabled: !isSubmitting,
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
                                  onChanged: isSubmitting ? null : (val) {
                                    setModalState(() => saveToCloud = val);
                                  },
                                  activeColor: const Color(0xFF667eea),
                                ),
                              ],
                            ),
                          ),
                          
                          const SizedBox(height: 16),
                          
                          const Text(
                            'Video Recording',
                            style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
                          ),
                          const SizedBox(height: 8),
                          
                          OutlinedButton.icon(
                            onPressed: (isSubmitting || isRecording) ? null : () async {
                              setModalState(() => isRecording = true);
                              
                              try {
                                final XFile? video = await _picker.pickVideo(
                                  source: ImageSource.camera,
                                  maxDuration: const Duration(minutes: 10),
                                );
                                
                                if (video != null) {
                                  final bytes = await video.readAsBytes();
                                  setModalState(() {
                                    recordedVideoBytes = bytes;
                                    recordedVideoName = video.name.endsWith('.mp4') 
                                        ? video.name 
                                        : '${video.name}.mp4';
                                    isRecording = false;
                                  });
                                } else {
                                  setModalState(() => isRecording = false);
                                }
                              } catch (e) {
                                print('Camera error: $e');
                                setModalState(() => isRecording = false);
                                ScaffoldMessenger.of(this.context).showSnackBar(
                                  SnackBar(content: Text('Camera error: $e')),
                                );
                              }
                            },
                            icon: Icon(
                              recordedVideoBytes != null ? Icons.check_circle : Icons.videocam,
                              size: 20,
                              color: recordedVideoBytes != null ? Colors.green : null,
                            ),
                            label: Text(
                              isRecording 
                                  ? 'Opening Camera...' 
                                  : recordedVideoBytes != null 
                                      ? 'Video Recorded' 
                                      : 'Start Recording',
                            ),
                            style: OutlinedButton.styleFrom(
                              minimumSize: const Size(double.infinity, 48),
                              side: BorderSide(
                                color: recordedVideoBytes != null 
                                    ? Colors.green 
                                    : Colors.grey.shade400,
                              ),
                              foregroundColor: recordedVideoBytes != null 
                                  ? Colors.green 
                                  : Colors.black87,
                            ),
                          ),
                          
                          if (recordedVideoBytes != null) ...[
                            const SizedBox(height: 8),
                            Container(
                              padding: const EdgeInsets.all(12),
                              decoration: BoxDecoration(
                                color: Colors.green.shade50,
                                borderRadius: BorderRadius.circular(8),
                                border: Border.all(color: Colors.green.shade200),
                              ),
                              child: Row(
                                children: [
                                  const Icon(Icons.video_library, size: 20, color: Colors.green),
                                  const SizedBox(width: 12),
                                  Expanded(
                                    child: Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        Text(
                                          recordedVideoName ?? 'recorded_video.mp4',
                                          style: const TextStyle(
                                            fontSize: 14,
                                            fontWeight: FontWeight.w600,
                                          ),
                                        ),
                                        Text(
                                          '${videoSizeMB.toStringAsFixed(1)} MB',
                                          style: TextStyle(
                                            fontSize: 12,
                                            color: Colors.grey.shade600,
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                  IconButton(
                                    icon: const Icon(Icons.close, size: 20),
                                    onPressed: () {
                                      setModalState(() {
                                        recordedVideoBytes = null;
                                        recordedVideoName = null;
                                      });
                                    },
                                  ),
                                ],
                              ),
                            ),
                          ],
                          
                          const SizedBox(height: 6),
                          const Text(
                            'Tip: Keep videos under 10 minutes for best results',
                            style: TextStyle(fontSize: 11, color: Colors.grey),
                          ),
                        ],
                      ),
                    ),
                  ),
                  
                  const SizedBox(height: 16),
                  SafeArea(
                    top: false,
                    child: Padding(
                      padding: const EdgeInsets.only(bottom: 20),
                      child: Row(
                        children: [
                          Expanded(
                            child: OutlinedButton.icon(
                              onPressed: (isSubmitting || recordedVideoBytes == null) 
                                  ? null 
                                  : () async {
                                setModalState(() => isSubmitting = true);
                                Navigator.pop(c);
                                await _uploadRecordedVideo(
                                  videoBytes: recordedVideoBytes!,
                                  filename: recordedVideoName!,
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
                                minimumSize: const Size(0, 48),
                                side: const BorderSide(color: Color(0xFF667eea)),
                                foregroundColor: const Color(0xFF667eea),
                              ),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: ElevatedButton.icon(
                              onPressed: (isSubmitting || recordedVideoBytes == null) 
                                  ? null 
                                  : () async {
                                setModalState(() => isSubmitting = true);
                                Navigator.pop(c);
                                await _uploadRecordedVideo(
                                  videoBytes: recordedVideoBytes!,
                                  filename: recordedVideoName!,
                                  title: titleCtrl.text.trim(),
                                  email: emailCtrl.text.trim(),
                                  language: selectedLanguage,
                                  hints: hintsCtrl.text.trim(),
                                  saveToCloud: saveToCloud,
                                  transcribeOnly: false,
                                );
                              },
                              icon: isSubmitting 
                                  ? const SizedBox(
                                      width: 16,
                                      height: 16,
                                      child: CircularProgressIndicator(
                                        strokeWidth: 2,
                                        valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                                      ),
                                    )
                                  : const Icon(Icons.auto_awesome, size: 16),
                              label: const Text(
                                'Transcribe &\nSummarize',
                                style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, height: 1.2),
                                textAlign: TextAlign.center,
                              ),
                              style: ElevatedButton.styleFrom(
                                minimumSize: const Size(0, 56),
                                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
                                backgroundColor: const Color(0xFF667eea),
                                foregroundColor: Colors.white,
                                disabledBackgroundColor: Colors.grey,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            );
          },
        );
      },
    );
  }

  Future<void> _uploadSelectedFile({
    required PlatformFile file,
    required String title,
    required String email,
    required String language,
    required String hints,
    required bool saveToCloud,
    required bool transcribeOnly,
  }) async {
    final Uint8List bytes = file.bytes!;
    final filename = file.name;
    final fileSizeMB = bytes.length / (1024 * 1024);
    final progressNotifier = ValueNotifier<double>(0.0);

    print('Uploading file: $filename (${fileSizeMB.toStringAsFixed(2)} MB)');
    print('Mode: ${transcribeOnly ? "transcribe-only" : "transcribe-and-summarize"}');

    if (!mounted) return;

    showDialog(
      context: context,
      barrierDismissible: false,
      barrierColor: Colors.black54,
      builder: (c) => ValueListenableBuilder<double>(
        valueListenable: progressNotifier,
        builder: (context, uploadProgress, child) {
          return Center(
            child: Container(
              margin: const EdgeInsets.all(40),
              padding: const EdgeInsets.all(32),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(16),
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  SizedBox(
                    width: 60,
                    height: 60,
                    child: CircularProgressIndicator(
                      strokeWidth: 5,
                      value: fileSizeMB > 20 && uploadProgress > 0 
                          ? uploadProgress / 100 
                          : null,
                      valueColor: const AlwaysStoppedAnimation<Color>(Color(0xFF667eea)),
                    ),
                  ),
                  const SizedBox(height: 24),
                  Text(
                    fileSizeMB > 20 
                        ? 'Uploading large file...'
                        : 'Uploading...',
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w600,
                      color: Color(0xFF667eea),
                    ),
                  ),
                  if (fileSizeMB > 20) ...[
                    const SizedBox(height: 12),
                    Text(
                      '${uploadProgress.toStringAsFixed(0)}%',
                      style: TextStyle(
                        fontSize: 32,
                        fontWeight: FontWeight.bold,
                        color: Colors.grey.shade700,
                      ),
                    ),
                    const SizedBox(height: 8),
                    SizedBox(
                      width: 200,
                      child: LinearProgressIndicator(
                        value: uploadProgress / 100,
                        backgroundColor: Colors.grey.shade200,
                        valueColor: const AlwaysStoppedAnimation<Color>(Color(0xFF667eea)),
                      ),
                    ),
                  ],
                  const SizedBox(height: 16),
                  Text(
                    'Please wait...',
                    style: TextStyle(
                      fontSize: 14,
                      color: Colors.grey.shade600,
                    ),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );

    try {
      final meetingId = await api.uploadMeeting(
        title: title.isEmpty ? 'Untitled Meeting' : title,
        fileBytes: bytes,
        filename: filename,
        email: email.isEmpty ? null : email,
        language: language == 'auto' ? null : language,
        hints: hints.isEmpty ? null : hints,
        transcribeOnly: transcribeOnly,
        onProgress: (progress) {
          progressNotifier.value = progress;
        },
      );
      
      print('Meeting created with ID: $meetingId');

      if (!mounted) return;
      progressNotifier.dispose();
      Navigator.pop(context);
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(
          builder: (_) => ProgressScreen(meetingId: meetingId),
        ),
      );
    } catch (e) {
      print('Upload error: $e');
      if (!mounted) return;
      progressNotifier.dispose();
      Navigator.pop(context);
      
      String errorMessage = 'Upload failed: ${e.toString().replaceAll('Exception: ', '')}';
      if (e.toString().contains('TimeoutException')) {
        errorMessage = 'Upload timed out. Please try again with a better connection.';
      } else if (e.toString().contains('SocketException') || e.toString().contains('Broken pipe')) {
        errorMessage = 'Connection lost during upload. Please check your internet connection and try again.';
      } else if (e.toString().contains('413') || e.toString().contains('too large')) {
        errorMessage = 'File is too large for your account tier. Please upgrade or use a smaller file.';
      } else if (e.toString().contains('Monthly meeting limit')) {
        errorMessage = 'Monthly meeting limit reached. Please upgrade your plan.';
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

  Future<void> _uploadRecordedVideo({
    required Uint8List videoBytes,
    required String filename,
    required String title,
    required String email,
    required String language,
    required String hints,
    required bool saveToCloud,
    required bool transcribeOnly,
  }) async {
    final fileSizeMB = videoBytes.length / (1024 * 1024);
    final progressNotifier = ValueNotifier<double>(0.0);

    print('Uploading recorded video: $filename (${fileSizeMB.toStringAsFixed(2)} MB)');
    print('Mode: ${transcribeOnly ? "transcribe-only" : "transcribe-and-summarize"}');

    if (!mounted) return;

    showDialog(
      context: context,
      barrierDismissible: false,
      barrierColor: Colors.black54,
      builder: (c) => ValueListenableBuilder<double>(
        valueListenable: progressNotifier,
        builder: (context, uploadProgress, child) {
          return Center(
            child: Container(
              margin: const EdgeInsets.all(40),
              padding: const EdgeInsets.all(32),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(16),
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  SizedBox(
                    width: 60,
                    height: 60,
                    child: CircularProgressIndicator(
                      strokeWidth: 5,
                      value: uploadProgress > 0 ? uploadProgress / 100 : null,
                      valueColor: const AlwaysStoppedAnimation<Color>(Color(0xFF667eea)),
                    ),
                  ),
                  const SizedBox(height: 24),
                  const Text(
                    'Uploading video...',
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w600,
                      color: Color(0xFF667eea),
                    ),
                  ),
                  if (uploadProgress > 0) ...[
                    const SizedBox(height: 12),
                    Text(
                      '${uploadProgress.toStringAsFixed(0)}%',
                      style: TextStyle(
                        fontSize: 32,
                        fontWeight: FontWeight.bold,
                        color: Colors.grey.shade700,
                      ),
                    ),
                    const SizedBox(height: 8),
                    SizedBox(
                      width: 200,
                      child: LinearProgressIndicator(
                        value: uploadProgress / 100,
                        backgroundColor: Colors.grey.shade200,
                        valueColor: const AlwaysStoppedAnimation<Color>(Color(0xFF667eea)),
                      ),
                    ),
                  ],
                  const SizedBox(height: 16),
                  Text(
                    'Please wait...',
                    style: TextStyle(
                      fontSize: 14,
                      color: Colors.grey.shade600,
                    ),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );

    try {
      final meetingId = await api.uploadMeeting(
        title: title.isEmpty ? 'Untitled Video Meeting' : title,
        fileBytes: videoBytes,
        filename: filename,
        email: email.isEmpty ? null : email,
        language: language == 'auto' ? null : language,
        hints: hints.isEmpty ? null : hints,
        transcribeOnly: transcribeOnly,
        onProgress: (progress) {
          progressNotifier.value = progress;
        },
      );
      
      print('Video meeting created with ID: $meetingId');

      if (!mounted) return;
      progressNotifier.dispose();
      Navigator.pop(context);
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(
          builder: (_) => ProgressScreen(meetingId: meetingId),
        ),
      );
    } catch (e) {
      print('Upload error: $e');
      if (!mounted) return;
      progressNotifier.dispose();
      Navigator.pop(context);
      
      String errorMessage = 'Upload failed: ${e.toString().replaceAll('Exception: ', '')}';
      if (e.toString().contains('TimeoutException')) {
        errorMessage = 'Upload timed out. Please try again with a better connection.';
      } else if (e.toString().contains('SocketException') || e.toString().contains('Broken pipe')) {
        errorMessage = 'Connection lost during upload. Please check your internet connection and try again.';
      } else if (e.toString().contains('413') || e.toString().contains('too large')) {
        errorMessage = 'Video is too large for your account tier. Please record a shorter video.';
      } else if (e.toString().contains('Monthly meeting limit')) {
        errorMessage = 'Monthly meeting limit reached. Please upgrade your plan.';
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
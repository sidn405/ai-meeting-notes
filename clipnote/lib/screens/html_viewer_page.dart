// lib/screens/html_viewer_page.dart
import 'dart:io';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:path/path.dart' as p;
import 'package:webview_flutter/webview_flutter.dart';
import 'package:share_plus/share_plus.dart';

class HtmlViewerPage extends StatefulWidget {
  const HtmlViewerPage({
    super.key,
    required this.title,
    required this.filePath,
  });

  final String title;
  final String filePath;

  @override
  State<HtmlViewerPage> createState() => _HtmlViewerPageState();
}

class _HtmlViewerPageState extends State<HtmlViewerPage> {
  WebViewController? _webController;
  bool _loading = true;
  String? _error;
  late final String _ext;
  Future<String>? _textFuture;

  @override
  void initState() {
    super.initState();
    _ext = p.extension(widget.filePath).toLowerCase();

    if (_isHtml) {
      _initWebView();
    } else if (_isText) {
      _textFuture = _readTextFile(File(widget.filePath));
    } else {
      _error = 'Unsupported file type: $_ext';
      _loading = false;
    }
  }

  bool get _isHtml => _ext == '.html' || _ext == '.htm';
  bool get _isText => _ext == '.txt' || _ext == '.log' || _ext == '.md';
  bool get _isSummary => widget.title.toLowerCase().contains('summary');

  Future<void> _initWebView() async {
    try {
      final f = File(widget.filePath);
      if (!await f.exists()) {
        setState(() {
          _error = 'File not found';
          _loading = false;
        });
        return;
      }

      final controller = WebViewController()
        ..setJavaScriptMode(JavaScriptMode.unrestricted)
        ..enableZoom(true)
        ..setBackgroundColor(Colors.white)
        ..setNavigationDelegate(
          NavigationDelegate(
            onPageStarted: (_) => setState(() => _loading = true),
            onPageFinished: (_) => setState(() => _loading = false),
            onWebResourceError: (err) {
              setState(() {
                _error = 'Failed to load page';
                _loading = false;
              });
            },
          ),
        );

      await controller.loadFile(f.path);
      setState(() {
        _webController = controller;
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = 'Failed to load file';
        _loading = false;
      });
    }
  }

  Future<String> _readTextFile(File f) async {
    if (!await f.exists()) {
      setState(() {
        _loading = false;
        _error = 'File not found';
      });
      return '';
    }
    try {
      final s = await f.readAsString();
      setState(() => _loading = false);
      return s;
    } catch (e) {
      setState(() {
        _loading = false;
        _error = 'Failed to read file';
      });
      return '';
    }
  }

  Future<void> _shareFile() async {
    try {
      final file = File(widget.filePath);
      if (await file.exists()) {
        await Share.shareXFiles(
          [XFile(widget.filePath)],
          subject: widget.title,
        );
      } else {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('File not found'),
            backgroundColor: Colors.red,
          ),
        );
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Failed to share: $e'),
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
          onPressed: () => Navigator.pop(context),
        ),
        title: Text(
          widget.title,
          style: const TextStyle(
            color: Colors.white,
            fontWeight: FontWeight.w600,
            fontSize: 18,
          ),
        ),
        centerTitle: true,
        actions: [
          if (!_loading && _error == null) ...[
            if (_isHtml && _webController != null)
              IconButton(
                icon: const Icon(Icons.refresh, color: Colors.white),
                onPressed: () async {
                  setState(() => _loading = true);
                  await _webController!.reload();
                },
                tooltip: 'Refresh',
              ),
            IconButton(
              icon: const Icon(Icons.share, color: Colors.white),
              onPressed: _shareFile,
              tooltip: 'Share',
            ),
          ],
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
          child: Column(
            children: [
              Expanded(
                child: Container(
                  margin: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(16),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withOpacity(0.2),
                        blurRadius: 20,
                        offset: const Offset(0, 4),
                      ),
                    ],
                  ),
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(16),
                    child: Stack(
                      children: [
                        Positioned.fill(child: _buildBody()),
                        if (_loading)
                          Container(
                            color: Colors.white.withOpacity(0.9),
                            child: const Center(
                              child: Column(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  CircularProgressIndicator(
                                    valueColor: AlwaysStoppedAnimation<Color>(Color(0xFF667eea)),
                                  ),
                                  SizedBox(height: 16),
                                  Text(
                                    'Loading...',
                                    style: TextStyle(
                                      color: Color(0xFF667eea),
                                      fontSize: 16,
                                      fontWeight: FontWeight.w600,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                      ],
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildBody() {
    if (_error != null) {
      return Container(
        color: Colors.white,
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(32.0),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  padding: const EdgeInsets.all(24),
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(
                      colors: [Color(0xFF667eea), Color(0xFF764ba2)],
                    ),
                    shape: BoxShape.circle,
                    boxShadow: [
                      BoxShadow(
                        color: const Color(0xFF667eea).withOpacity(0.3),
                        blurRadius: 20,
                        spreadRadius: 5,
                      ),
                    ],
                  ),
                  child: const Icon(
                    Icons.error_outline,
                    color: Colors.white,
                    size: 48,
                  ),
                ),
                const SizedBox(height: 24),
                const Text(
                  'Unable to Open File',
                  style: TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.bold,
                    color: Color(0xFF667eea),
                  ),
                ),
                const SizedBox(height: 12),
                Text(
                  _error!,
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 16,
                    color: Colors.grey.shade600,
                  ),
                ),
                const SizedBox(height: 32),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton.icon(
                    onPressed: () => Navigator.pop(context),
                    icon: const Icon(Icons.arrow_back),
                    label: const Text('Go Back'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF667eea),
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(
                        horizontal: 32,
                        vertical: 16,
                      ),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                      elevation: 2,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      );
    }

    if (_isHtml) {
      if (_webController == null) {
        return const Center(
          child: CircularProgressIndicator(
            valueColor: AlwaysStoppedAnimation<Color>(Color(0xFF667eea)),
          ),
        );
      }
      return WebViewWidget(controller: _webController!);
    }

    if (_isText) {
      return FutureBuilder<String>(
        future: _textFuture,
        builder: (context, snap) {
          if (snap.connectionState == ConnectionState.waiting) {
            return const Center(
              child: CircularProgressIndicator(
                valueColor: AlwaysStoppedAnimation<Color>(Color(0xFF667eea)),
              ),
            );
          }
          
          if (snap.hasError) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(32.0),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      padding: const EdgeInsets.all(24),
                      decoration: BoxDecoration(
                        color: Colors.red.shade50,
                        shape: BoxShape.circle,
                      ),
                      child: Icon(
                        Icons.error_outline,
                        color: Colors.red.shade700,
                        size: 48,
                      ),
                    ),
                    const SizedBox(height: 24),
                    Text(
                      'Error Loading File',
                      style: TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.bold,
                        color: Colors.red.shade700,
                      ),
                    ),
                    const SizedBox(height: 12),
                    Text(
                      '${snap.error}',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: 14,
                        color: Colors.grey.shade600,
                      ),
                    ),
                  ],
                ),
              ),
            );
          }
          
          final text = snap.data ?? '';
          
          // If it's a summary, try to parse and format it
          if (_isSummary) {
            final parsedSummary = _parseSummary(text);
            if (parsedSummary != null) {
              return _FormattedSummaryViewer(summary: parsedSummary);
            }
          }
          
          // Otherwise show as plain text
          return _TextViewer(text: text);
        },
      );
    }

    return Container(
      color: Colors.white,
      child: Center(
        child: Padding(
          padding: const EdgeInsets.all(32.0),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                padding: const EdgeInsets.all(24),
                decoration: BoxDecoration(
                  color: Colors.orange.shade50,
                  shape: BoxShape.circle,
                ),
                child: Icon(
                  Icons.file_present,
                  color: Colors.orange.shade700,
                  size: 48,
                ),
              ),
              const SizedBox(height: 24),
              Text(
                'Unsupported File Type',
                style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                  color: Colors.orange.shade700,
                ),
              ),
              const SizedBox(height: 12),
              Text(
                'This file format ($_ext) is not supported',
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 14,
                  color: Colors.grey.shade600,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  SummaryData? _parseSummary(String text) {
    try {
      // Try to parse as JSON first
      final json = jsonDecode(text);
      
      return SummaryData(
        executiveSummary: json['executive_summary'] ?? json['summary'] ?? '',
        keyDecisions: _parseList(json['key_decisions'] ?? json['decisions']),
        actionItems: _parseList(json['action_items'] ?? json['actions']),
        additionalNotes: json['notes'] ?? json['additional_notes'] ?? '',
      );
    } catch (e) {
      // If JSON parsing fails, try to parse as structured text
      return _parseStructuredText(text);
    }
  }

  List<String> _parseList(dynamic data) {
    if (data == null) return [];
    if (data is List) {
      return data.map((item) => item.toString()).toList();
    }
    if (data is String) {
      // Split by newlines or bullets
      return data
          .split(RegExp(r'\n|•|●|-'))
          .map((s) => s.trim())
          .where((s) => s.isNotEmpty)
          .toList();
    }
    return [];
  }

  SummaryData? _parseStructuredText(String text) {
    // Try to parse text with headers like "Executive Summary:", "Key Decisions:", etc.
    final lines = text.split('\n');
    String? executiveSummary;
    List<String> keyDecisions = [];
    List<String> actionItems = [];
    String? additionalNotes;
    
    String? currentSection;
    StringBuffer currentContent = StringBuffer();
    
    for (var line in lines) {
      final lowerLine = line.toLowerCase().trim();
      
      if (lowerLine.contains('executive summary') || 
          lowerLine.contains('summary:')) {
        if (currentSection != null) {
          _saveSection(currentSection, currentContent.toString(), 
                      executiveSummary, keyDecisions, actionItems, additionalNotes);
        }
        currentSection = 'executive_summary';
        currentContent.clear();
      } else if (lowerLine.contains('key decision') || 
                 lowerLine.contains('decisions:')) {
        if (currentSection != null) {
          executiveSummary = _saveSection(currentSection, currentContent.toString(), 
                      executiveSummary, keyDecisions, actionItems, additionalNotes);
        }
        currentSection = 'key_decisions';
        currentContent.clear();
      } else if (lowerLine.contains('action item') || 
                 lowerLine.contains('actions:')) {
        if (currentSection != null) {
          executiveSummary = _saveSection(currentSection, currentContent.toString(), 
                      executiveSummary, keyDecisions, actionItems, additionalNotes);
        }
        currentSection = 'action_items';
        currentContent.clear();
      } else if (lowerLine.contains('note') || 
                 lowerLine.contains('additional')) {
        if (currentSection != null) {
          executiveSummary = _saveSection(currentSection, currentContent.toString(), 
                      executiveSummary, keyDecisions, actionItems, additionalNotes);
        }
        currentSection = 'notes';
        currentContent.clear();
      } else if (currentSection != null) {
        if (line.trim().isNotEmpty) {
          currentContent.writeln(line);
        }
      }
    }
    
    // Save last section
    if (currentSection != null) {
      executiveSummary = _saveSection(currentSection, currentContent.toString(), 
                  executiveSummary, keyDecisions, actionItems, additionalNotes);
    }
    
    // If we found at least one section, return the data
    if (executiveSummary != null || keyDecisions.isNotEmpty || actionItems.isNotEmpty) {
      return SummaryData(
        executiveSummary: executiveSummary ?? '',
        keyDecisions: keyDecisions,
        actionItems: actionItems,
        additionalNotes: additionalNotes ?? '',
      );
    }
    
    return null;
  }

  String? _saveSection(String section, String content, String? execSum, 
                      List<String> decisions, List<String> actions, String? notes) {
    final trimmed = content.trim();
    if (trimmed.isEmpty) return execSum;
    
    switch (section) {
      case 'executive_summary':
        return trimmed;
      case 'key_decisions':
        decisions.addAll(_parseList(trimmed));
        break;
      case 'action_items':
        actions.addAll(_parseList(trimmed));
        break;
      case 'notes':
        return trimmed;
    }
    return execSum;
  }
}

class SummaryData {
  final String executiveSummary;
  final List<String> keyDecisions;
  final List<String> actionItems;
  final String additionalNotes;

  SummaryData({
    required this.executiveSummary,
    required this.keyDecisions,
    required this.actionItems,
    required this.additionalNotes,
  });
}

class _FormattedSummaryViewer extends StatelessWidget {
  const _FormattedSummaryViewer({required this.summary});
  final SummaryData summary;

  @override
  Widget build(BuildContext context) {
    return Container(
      color: Colors.grey.shade50,
      child: Scrollbar(
        thumbVisibility: true,
        thickness: 6,
        radius: const Radius.circular(3),
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Executive Summary
              if (summary.executiveSummary.isNotEmpty) ...[
                _SectionCard(
                  icon: Icons.summarize,
                  title: 'Executive Summary',
                  color: const Color(0xFF667eea),
                  child: Text(
                    summary.executiveSummary,
                    style: TextStyle(
                      fontSize: 15,
                      height: 1.6,
                      color: Colors.grey.shade800,
                    ),
                  ),
                ),
                const SizedBox(height: 16),
              ],
              
              // Key Decisions
              if (summary.keyDecisions.isNotEmpty) ...[
                _SectionCard(
                  icon: Icons.lightbulb,
                  title: 'Key Decisions',
                  color: Colors.orange,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: summary.keyDecisions.asMap().entries.map((entry) {
                      return Padding(
                        padding: const EdgeInsets.only(bottom: 12),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Container(
                              margin: const EdgeInsets.only(top: 4, right: 12),
                              padding: const EdgeInsets.all(6),
                              decoration: BoxDecoration(
                                color: Colors.orange.shade100,
                                shape: BoxShape.circle,
                              ),
                              child: Text(
                                '${entry.key + 1}',
                                style: TextStyle(
                                  fontSize: 12,
                                  fontWeight: FontWeight.bold,
                                  color: Colors.orange.shade700,
                                ),
                              ),
                            ),
                            Expanded(
                              child: Text(
                                entry.value,
                                style: TextStyle(
                                  fontSize: 14,
                                  height: 1.5,
                                  color: Colors.grey.shade800,
                                ),
                              ),
                            ),
                          ],
                        ),
                      );
                    }).toList(),
                  ),
                ),
                const SizedBox(height: 16),
              ],
              
              // Action Items
              if (summary.actionItems.isNotEmpty) ...[
                _SectionCard(
                  icon: Icons.task_alt,
                  title: 'Action Items',
                  color: Colors.green,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: summary.actionItems.asMap().entries.map((entry) {
                      return Padding(
                        padding: const EdgeInsets.only(bottom: 12),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Container(
                              margin: const EdgeInsets.only(top: 2, right: 12),
                              child: Icon(
                                Icons.check_circle,
                                size: 20,
                                color: Colors.green.shade600,
                              ),
                            ),
                            Expanded(
                              child: Text(
                                entry.value,
                                style: TextStyle(
                                  fontSize: 14,
                                  height: 1.5,
                                  color: Colors.grey.shade800,
                                ),
                              ),
                            ),
                          ],
                        ),
                      );
                    }).toList(),
                  ),
                ),
                const SizedBox(height: 16),
              ],
              
              // Additional Notes
              if (summary.additionalNotes.isNotEmpty) ...[
                _SectionCard(
                  icon: Icons.notes,
                  title: 'Additional Notes',
                  color: Colors.blue,
                  child: Text(
                    summary.additionalNotes,
                    style: TextStyle(
                      fontSize: 14,
                      height: 1.6,
                      color: Colors.grey.shade800,
                    ),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _SectionCard extends StatelessWidget {
  const _SectionCard({
    required this.icon,
    required this.title,
    required this.color,
    required this.child,
  });

  final IconData icon;
  final String title;
  final Color color;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.05),
            blurRadius: 10,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: color.withOpacity(0.1),
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(12),
                topRight: Radius.circular(12),
              ),
            ),
            child: Row(
              children: [
                Icon(icon, color: color, size: 24),
                const SizedBox(width: 12),
                Text(
                  title,
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                    color: color,
                  ),
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(16),
            child: child,
          ),
        ],
      ),
    );
  }
}

class _TextViewer extends StatelessWidget {
  const _TextViewer({required this.text});
  final String text;

  @override
  Widget build(BuildContext context) {
    if (text.isEmpty) {
      return Container(
        color: Colors.white,
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(32.0),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  padding: const EdgeInsets.all(24),
                  decoration: BoxDecoration(
                    color: Colors.grey.shade100,
                    shape: BoxShape.circle,
                  ),
                  child: Icon(
                    Icons.description_outlined,
                    color: Colors.grey.shade400,
                    size: 48,
                  ),
                ),
                const SizedBox(height: 24),
                Text(
                  'Empty File',
                  style: TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.bold,
                    color: Colors.grey.shade700,
                  ),
                ),
                const SizedBox(height: 12),
                Text(
                  'This file contains no text',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 14,
                    color: Colors.grey.shade500,
                  ),
                ),
              ],
            ),
          ),
        ),
      );
    }

    return Container(
      color: Colors.white,
      child: Scrollbar(
        thumbVisibility: true,
        thickness: 6,
        radius: const Radius.circular(3),
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20.0),
          child: SelectableText(
            text,
            style: TextStyle(
              fontFamily: 'monospace',
              fontSize: 14,
              height: 1.6,
              color: Colors.grey.shade800,
            ),
          ),
        ),
      ),
    );
  }
}
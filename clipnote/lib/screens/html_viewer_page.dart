// lib/screens/html_viewer_page.dart
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:path/path.dart' as p;
import 'package:webview_flutter/webview_flutter.dart';

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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.grey[50],
      appBar: AppBar(
        title: Text(
          widget.title,
          style: const TextStyle(
            fontWeight: FontWeight.w600,
            fontSize: 18,
          ),
        ),
        backgroundColor: const Color(0xFF667eea),
        foregroundColor: Colors.white,
        elevation: 0,
        actions: [
          if (_isHtml && _webController != null)
            IconButton(
              icon: const Icon(Icons.refresh),
              onPressed: () async {
                setState(() => _loading = true);
                await _webController!.reload();
              },
              tooltip: 'Refresh',
            ),
        ],
      ),
      body: Stack(
        children: [
          Positioned.fill(child: _buildBody()),
          if (_loading)
            Container(
              color: Colors.black12,
              child: const Center(
                child: CircularProgressIndicator(
                  valueColor: AlwaysStoppedAnimation<Color>(Color(0xFF667eea)),
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildBody() {
    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  color: Colors.red[50],
                  borderRadius: BorderRadius.circular(16),
                ),
                child: const Icon(
                  Icons.error_outline,
                  color: Colors.red,
                  size: 48,
                ),
              ),
              const SizedBox(height: 20),
              Text(
                'Unable to Open File',
                style: Theme.of(context).textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.bold,
                    ),
              ),
              const SizedBox(height: 8),
              Text(
                _error!,
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: Colors.grey[600],
                    ),
              ),
              const SizedBox(height: 24),
              ElevatedButton(
                onPressed: () => Navigator.pop(context),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF667eea),
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(
                    horizontal: 32,
                    vertical: 14,
                  ),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                child: const Text('Close'),
              ),
            ],
          ),
        ),
      );
    }

    if (_isHtml) {
      if (_webController == null) {
        return const Center(child: CircularProgressIndicator());
      }
      return WebViewWidget(controller: _webController!);
    }

    if (_isText) {
      return FutureBuilder<String>(
        future: _textFuture,
        builder: (context, snap) {
          if (snap.hasError) {
            return Center(
              child: Text('Error: ${snap.error}'),
            );
          }
          final text = snap.data ?? '';
          return _TextViewer(text: text);
        },
      );
    }

    return const Center(
      child: Text('Unsupported file type'),
    );
  }
}

class _TextViewer extends StatelessWidget {
  const _TextViewer({required this.text});
  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      color: Colors.white,
      child: Scrollbar(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(16.0),
          child: SelectableText(
            text.isEmpty ? 'Empty file' : text,
            style: TextStyle(
              fontFamily: 'monospace',
              fontSize: 14,
              height: 1.6,
              color: Colors.grey[800],
            ),
          ),
        ),
      ),
    );
  }
}
// lib/screens/html_viewer_page.dart
import 'dart:io';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';
import 'package:path/path.dart' as p;

class HtmlViewerPage extends StatefulWidget {
  const HtmlViewerPage({
    super.key,
    required this.title,
    required this.filePath,
  });

  final String title;
  final String filePath; // Absolute local file path in app Documents

  @override
  State<HtmlViewerPage> createState() => _HtmlViewerPageState();
}

class _HtmlViewerPageState extends State<HtmlViewerPage> {
  WebViewController? _controller;
  bool _isHtml = false;
  bool _loading = true;
  String? _error;

  // For .txt files
  Future<String>? _textFuture;

  @override
  void initState() {
    super.initState();
    _isHtml = _isHtmlFile(widget.filePath);
    if (_isHtml) {
      _initWebView();
    } else if (_isTextFile(widget.filePath)) {
      _textFuture = _readTextFile(File(widget.filePath));
    } else {
      _error =
          'Unsupported file type: ${p.extension(widget.filePath)}\nPath: ${widget.filePath}';
      _loading = false;
    }
  }

  bool _isHtmlFile(String path) {
    final ext = p.extension(path).toLowerCase();
    return ext == '.html' || ext == '.htm';
  }

  bool _isTextFile(String path) {
    final ext = p.extension(path).toLowerCase();
    return ext == '.txt' || ext == '.log' || ext == '.md';
  }

  void _initWebView() async {
    try {
      final f = File(widget.filePath);
      if (!await f.exists()) {
        setState(() {
          _error = 'File not found:\n${widget.filePath}';
          _loading = false;
        });
        return;
      }

      final controller = WebViewController()
        ..setJavaScriptMode(JavaScriptMode.unrestricted)
        ..enableZoom(true)
        ..setBackgroundColor(Colors.transparent)
        ..setNavigationDelegate(
          NavigationDelegate(
            onPageStarted: (_) => setState(() => _loading = true),
            onPageFinished: (_) => setState(() => _loading = false),
            onWebResourceError: (err) {
              setState(() {
                _error =
                    'Web resource error (${err.errorCode}): ${err.description}';
                _loading = false;
              });
            },
          ),
        );

      await controller.loadFile(f.path);

      setState(() {
        _controller = controller;
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = 'Failed to load HTML file:\n$e';
        _loading = false;
      });
    }
  }

  Future<String> _readTextFile(File f) async {
    if (!await f.exists()) {
      setState(() {
        _loading = false;
        _error = 'File not found:\n${f.path}';
      });
      return '';
    }
    try {
      // Try UTF-8 first
      final s = await f.readAsString();
      setState(() => _loading = false);
      return s;
    } catch (_) {
      // Fallback decoding
      try {
        final bytes = await f.readAsBytes();
        final s = const Utf8Decoder(allowMalformed: true).convert(bytes);
        setState(() => _loading = false);
        return s;
      } catch (e) {
        setState(() {
          _loading = false;
          _error = 'Failed to read text file:\n$e';
        });
        return '';
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final actions = <Widget>[
      if (_isHtml && _controller != null)
        IconButton(
          tooltip: 'Reload',
          icon: const Icon(Icons.refresh),
          onPressed: () async {
            setState(() => _loading = true);
            await _controller!.reload();
          },
        ),
      IconButton(
        tooltip: 'Info',
        icon: const Icon(Icons.info_outline),
        onPressed: () {
          final name = p.basename(widget.filePath);
          showAboutDialog(
            context: context,
            applicationName: 'Viewer',
            applicationVersion: '',
            children: [
              SelectableText('File: $name\nPath: ${widget.filePath}'),
            ],
          );
        },
      ),
    ];

    return Scaffold(
      appBar: AppBar(
        title: Text(widget.title, overflow: TextOverflow.ellipsis),
        elevation: 0,
        actions: actions,
      ),
      body: Stack(
        children: [
          // Content
          Positioned.fill(child: _buildBody()),
          // Loading overlay
          if (_loading)
            const Positioned.fill(
              child: IgnorePointer(
                child: Center(child: CircularProgressIndicator()),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildBody() {
    if (_error != null) {
      return _buildError(_error!);
    }

    if (_isHtml) {
      if (_controller == null) {
        return const SizedBox.shrink();
      }
      return SafeArea(child: WebViewWidget(controller: _controller!));
    }

    if (_isTextFile(widget.filePath)) {
      return SafeArea(
        child: FutureBuilder<String>(
          future: _textFuture,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting &&
                _loading) {
              return const SizedBox.shrink();
            }
            if (snapshot.hasError) {
              return _buildError('Failed to load text:\n${snapshot.error}');
            }
            final text = snapshot.data ?? '';
            return _TextViewer(text: text);
          },
        ),
      );
    }

    // Shouldn’t reach here; handled earlier
    return _buildError('Unsupported file type.');
  }

  Widget _buildError(String msg) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline, color: Colors.red, size: 48),
            const SizedBox(height: 12),
            Text(
              'Unable to open file',
              style: Theme.of(context)
                  .textTheme
                  .titleMedium
                  ?.copyWith(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            SelectableText(
              msg,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            const SizedBox(height: 12),
            FilledButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Close'),
            )
          ],
        ),
      ),
    );
  }
}

class _TextViewer extends StatelessWidget {
  const _TextViewer({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    final mono = Theme.of(context).textTheme.bodyMedium?.copyWith(
          fontFamily: 'monospace',
          fontFamilyFallback: const ['Courier New', 'SFMono-Regular'],
          fontSize: 14,
          height: 1.6,
        );

    return Scrollbar(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: SelectableText(text.isEmpty ? '(empty file)' : text, style: mono),
      ),
    );
  }
}

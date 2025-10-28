// lib/screens/html_viewer_page.dart
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:path/path.dart' as p;
import 'package:webview_flutter/webview_flutter.dart';
import 'package:pdfx/pdfx.dart';
import 'package:csv/csv.dart';

class HtmlViewerPage extends StatefulWidget {
  const HtmlViewerPage({
    super.key,
    required this.title,
    required this.filePath,
  });

  final String title;
  final String filePath; // Absolute local path

  @override
  State<HtmlViewerPage> createState() => _HtmlViewerPageState();
}

class _HtmlViewerPageState extends State<HtmlViewerPage> {
  WebViewController? _webController;

  // pdfx 2.9.x: use PdfControllerPinch with Future<PdfDocument>
  PdfControllerPinch? _pdfController;

  bool _loading = true;
  String? _error;

  late final String _ext;
  Future<String>? _textFuture;                 // for .txt/.md/.log
  Future<List<List<dynamic>>>? _csvFuture;     // for .csv/.tsv

  @override
  void initState() {
    super.initState();
    _ext = p.extension(widget.filePath).toLowerCase();

    if (_isHtml) {
      _initWebView();
    } else if (_isText) {
      _textFuture = _readTextFile(File(widget.filePath));
    } else if (_isPdf) {
      _initPdfPinch();
    } else if (_isCsv) {
      _csvFuture = _readCsv(File(widget.filePath));
    } else {
      _error = 'Unsupported file type: $_ext\nPath: ${widget.filePath}';
      _loading = false;
    }
  }

  bool get _isHtml => _ext == '.html' || _ext == '.htm';
  bool get _isText => _ext == '.txt' || _ext == '.log' || _ext == '.md';
  bool get _isPdf  => _ext == '.pdf';
  bool get _isCsv  => _ext == '.csv' || _ext == '.tsv';

  Future<void> _initWebView() async {
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
                _error = 'Web resource error (${err.errorCode}): ${err.description}';
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
        _error = 'Failed to load HTML file:\n$e';
        _loading = false;
      });
    }
  }

  // pdfx 2.9.x way: create controller with Future<PdfDocument>
  Future<void> _initPdfPinch() async {
    try {
      final f = File(widget.filePath);
      if (!await f.exists()) {
        setState(() {
          _error = 'File not found:\n${widget.filePath}';
          _loading = false;
        });
        return;
      }
      final futureDoc = PdfDocument.openFile(widget.filePath); // returns Future<PdfDocument>
      final controller = PdfControllerPinch(document: futureDoc);
      setState(() {
        _pdfController = controller;
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = 'Failed to open PDF:\n$e';
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
      final s = await f.readAsString();
      setState(() => _loading = false);
      return s;
    } catch (_) {
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

  Future<List<List<dynamic>>> _readCsv(File f) async {
    if (!await f.exists()) {
      setState(() {
        _loading = false;
        _error = 'File not found:\n${f.path}';
      });
      return const [];
    }
    try {
      final raw = await f.readAsString();
      final isTsv = _ext == '.tsv';
      final rows = const CsvToListConverter(
        fieldDelimiter: ',', // we'll pre-convert TSV below
        textDelimiter: '"',
        eol: '\n',
        shouldParseNumbers: false,
      ).convert(isTsv ? raw.replaceAll('\t', ',') : raw);
      setState(() => _loading = false);
      return rows;
    } catch (e) {
      setState(() {
        _loading = false;
        _error = 'Failed to read CSV:\n$e';
      });
      return const [];
    }
  }

  @override
  void dispose() {
    // pdfx controller owns the document in this pattern; dispose the controller.
    _pdfController?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final actions = <Widget>[
      if (_isHtml && _webController != null)
        IconButton(
          tooltip: 'Reload',
          icon: const Icon(Icons.refresh),
          onPressed: () async {
            setState(() => _loading = true);
            await _webController!.reload();
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
          Positioned.fill(child: _buildBody()),
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
    if (_error != null) return _buildError(_error!);

    if (_isHtml) {
      if (_webController == null) return const SizedBox.shrink();
      return SafeArea(child: WebViewWidget(controller: _webController!));
    }

    if (_isPdf) {
      if (_pdfController == null) return const SizedBox.shrink();
      return SafeArea(child: PdfViewPinch(controller: _pdfController!));
    }

    if (_isText) {
      return SafeArea(
        child: FutureBuilder<String>(
          future: _textFuture,
          builder: (context, snap) {
            if (snap.hasError) return _buildError('Failed to load text:\n${snap.error}');
            final text = snap.data ?? '';
            return _TextViewer(text: text);
          },
        ),
      );
    }

    if (_isCsv) {
      return SafeArea(
        child: FutureBuilder<List<List<dynamic>>>(
          future: _csvFuture,
          builder: (context, snap) {
            if (snap.hasError) return _buildError('Failed to load CSV:\n${snap.error}');
            final rows = snap.data ?? const [];
            if (rows.isEmpty) return const Center(child: Text('(empty CSV)'));
            return _CsvTable(rows: rows);
          },
        ),
      );
    }

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

// ---------- CSV ----------

class _CsvTable extends StatefulWidget {
  const _CsvTable({required this.rows});
  final List<List<dynamic>> rows;

  @override
  State<_CsvTable> createState() => _CsvTableState();
}

class _CsvTableState extends State<_CsvTable> {
  static const int _rowsPerPage = 25;

  late final List<String> _headers;
  late final List<List<String>> _data;
  late final _CsvDataSource _source;

  @override
  void initState() {
    super.initState();
    final rows = widget.rows.map((r) => r.map((c) => c?.toString() ?? '').toList()).toList();
    if (rows.isEmpty) {
      _headers = const [];
      _data = const [];
    } else {
      _headers = rows.first;
      _data = rows.length > 1 ? rows.sublist(1) : <List<String>>[];
    }
    _source = _CsvDataSource(headers: _headers, data: _data);
  }

  @override
  Widget build(BuildContext context) {
    if (_headers.isEmpty) return const Center(child: Text('(empty CSV)'));
    return Scrollbar(
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: ConstrainedBox(
          constraints: const BoxConstraints(minWidth: 800),
          child: PaginatedDataTable(
            header: const Text('CSV Preview'),
            rowsPerPage: (_data.length < _rowsPerPage) ? _data.length : _rowsPerPage,
            columns: _headers.map((h) => DataColumn(label: Text(h))).toList(),
            source: _source,
          ),
        ),
      ),
    );
  }
}

class _CsvDataSource extends DataTableSource {
  _CsvDataSource({required this.headers, required this.data});
  final List<String> headers;
  final List<List<String>> data;

  @override
  DataRow getRow(int index) {
    final row = data[index];
    return DataRow(
      cells: List.generate(
        headers.length,
        (i) => DataCell(SelectableText(i < row.length ? row[i] : '')),
      ),
    );
  }

  @override
  bool get isRowCountApproximate => false;
  @override
  int get rowCount => data.length;
  @override
  int get selectedRowCount => 0;
}

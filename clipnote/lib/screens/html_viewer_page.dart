// lib/screens/html_viewer_page.dart
import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:pdfx/pdfx.dart';
import 'package:webview_flutter/webview_flutter.dart';

class HtmlViewerPage extends StatefulWidget {
  final String title;
  final String filePath;

  const HtmlViewerPage({
    super.key,
    required this.title,
    required this.filePath,
  });

  @override
  State<HtmlViewerPage> createState() => _HtmlViewerPageState();
}

class _HtmlViewerPageState extends State<HtmlViewerPage> {
  WebViewController? _web;
  PdfControllerPinch? _pdf;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _pdf?.dispose();
    super.dispose();
  }

  String get _ext => widget.filePath.split('.').last.toLowerCase();

  Future<void> _load() async {
    final f = File(widget.filePath);
    if (!await f.exists()) return;

    if (_ext == 'pdf') {
      setState(() {
        _pdf = PdfControllerPinch(
          document: PdfDocument.openFile(widget.filePath),
        );
      });
      return;
    }

    // Build themed HTML string for everything else
    String html;

    switch (_ext) {
      case 'html':
      case 'htm':
        html = await f.readAsString();
        // If the file is just raw content, wrap it; otherwise use as-is
        if (!html.contains('<html')) {
          html = _wrapHtml(title: widget.title, body: '<pre>${_safe(html)}</pre>');
        }
        break;

      case 'txt':
      case 'md':
      case 'log':
        final text = await f.readAsString();
        html = _wrapHtml(
          title: widget.title,
          body: '<div class="section"><h2>${_safe(widget.title)}</h2>'
              '<pre class="mono">${_safe(text)}</pre></div>',
        );
        break;

      case 'csv':
      case 'tsv':
        final raw = await f.readAsString();
        html = _wrapHtml(
          title: widget.title,
          body: _csvToTable(raw, delimiter: _ext == 'tsv' ? '\t' : ','),
        );
        break;

      case 'json':
        final raw = await f.readAsString();
        html = _wrapHtml(
          title: widget.title,
          body: _renderSummaryJson(raw), // pretty cards, no braces shown
        );
        break;

      default:
        final bytes = await f.readAsBytes();
        final preview = bytes.length > 0
            ? await f.openRead(0, bytes.length.clamp(0, 4096)).transform(utf8.decoder).join()
            : '';
        html = _wrapHtml(
          title: widget.title,
          body:
              '<div class="section"><h2>Preview</h2><pre class="mono">${_safe(preview)}</pre>'
              '<div class="muted">Unsupported type “.$_ext”.</div></div>',
        );
    }

    final controller = WebViewController()
      ..setBackgroundColor(Colors.transparent)
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..loadHtmlString(html);

    setState(() => _web = controller);
  }

  // ---------- UI ----------
  @override
  Widget build(BuildContext context) {
    final title = widget.title;
    return Scaffold(
      appBar: AppBar(
        title: Text(title),
        centerTitle: false,
        actions: [
          // (No “View licenses” button here)
        ],
      ),
      body: _pdf != null
          ? PdfViewPinch(controller: _pdf!)
          : _web != null
              ? WebViewWidget(controller: _web!)
              : const Center(child: CircularProgressIndicator()),
    );
  }

  // ---------- Helpers ----------

  String _wrapHtml({required String title, required String body}) {
    // Your home-screen gradient + clean cards
    return '''
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${_safe(title)}</title>
<style>
  *{box-sizing:border-box}
  body{margin:0;background:#f5f5f5;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Inter,system-ui,sans-serif;color:#333;line-height:1.6}
  .header{padding:28px;background:linear-gradient(135deg,#6a82fb 0%,#7f53ac 100%);color:#fff}
  .header h1{margin:0;font-size:22px}
  .badge{display:inline-block;margin-top:10px;font-size:12px;padding:6px 10px;border-radius:14px;background:rgba(255,255,255,.18)}
  .container{max-width:920px;margin:16px auto;padding:16px}
  .card{background:#fff;border-radius:14px;box-shadow:0 8px 24px rgba(0,0,0,.06);padding:20px}
  .section{margin-bottom:22px}
  h2{font-size:18px;color:#6a82fb;margin:0 0 10px 0;padding-bottom:10px;border-bottom:2px solid #eee}
  .mono{white-space:pre-wrap;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;background:#fafafa;border:1px solid #eee;border-radius:10px;padding:14px;font-size:14px;line-height:1.8}
  .muted{color:#888}
  table{width:100%;border-collapse:collapse;border-radius:10px;overflow:hidden}
  thead th{background:#f0f2ff;color:#4e5ef7;font-weight:600}
  th,td{padding:10px;border:1px solid #ececec;text-align:left;font-size:14px}
  .pill{display:inline-block;padding:6px 10px;border-radius:999px;background:#eef2ff;color:#4e5ef7;font-size:12px}
  .item{background:#f9f9ff;border:1px solid #eaeaff;border-left:4px solid #6a82fb;border-radius:10px;padding:12px;margin:10px 0}
</style>
</head>
<body>
  <div class="header">
    <h1>${_safe(title)}</h1>
    <div class="badge">✓ Works Offline</div>
  </div>
  <div class="container">
    <div class="card">
      $body
    </div>
  </div>
</body>
</html>
''';
  }

  String _renderSummaryJson(String raw) {
    Map<String, dynamic>? data;
    try {
      data = json.decode(raw) as Map<String, dynamic>;
    } catch (_) {
      // Not valid JSON — just show as text
      return '<div class="section"><h2>Content</h2><pre class="mono">${_safe(raw)}</pre></div>';
    }

    final exec = (data['executive_summary'] ?? data['summary'] ?? '') as String? ?? '';
    final decisions = (data['key_decisions'] ?? data['decisions'] ?? []) as List?;
    final items = (data['action_items'] ?? data['actions'] ?? []) as List?;
    final points = (data['key_points'] ?? data['highlights'] ?? []) as List?;

    final sb = StringBuffer();

    if (exec.isNotEmpty) {
      sb.writeln('<div class="section"><h2>Executive Summary</h2>');
      sb.writeln('<div class="item">${_safe(exec)}</div></div>');
    }

    if (points != null && points.isNotEmpty) {
      sb.writeln('<div class="section"><h2>Key Points</h2>');
      for (final p in points) {
        sb.writeln('<div class="item">${_safe(p.toString())}</div>');
      }
      sb.writeln('</div>');
    }

    if (decisions != null && decisions.isNotEmpty) {
      sb.writeln('<div class="section"><h2>Key Decisions</h2>');
      for (final d in decisions) {
        sb.writeln('<div class="item">${_safe(d.toString())}</div>');
      }
      sb.writeln('</div>');
    }

    if (items != null && items.isNotEmpty) {
      sb.writeln('<div class="section"><h2>Action Items</h2>');
      for (final it in items) {
        if (it is Map) {
          final owner = (it['owner'] ?? '').toString();
          final task = (it['task'] ?? it['description'] ?? '').toString();
          final due = (it['due_date'] ?? '').toString();
          final pri = (it['priority'] ?? '').toString();
          sb.writeln(
              '<div class="item"><strong>${_safe(owner.isEmpty ? "Owner" : owner)}:</strong> ${_safe(task)}'
              '${due.isNotEmpty ? ' — <span class="pill">Due: ${_safe(due)}</span>' : ''}'
              '${pri.isNotEmpty ? ' — <span class="pill">Priority: ${_safe(pri)}</span>' : ''}'
              '</div>');
        } else {
          sb.writeln('<div class="item">${_safe(it.toString())}</div>');
        }
      }
      sb.writeln('</div>');
    }

    // Fallback if nothing recognized
    if (sb.isEmpty) {
      return '<div class="section"><h2>Summary</h2><pre class="mono">${_safe(raw)}</pre></div>';
    }
    return sb.toString();
  }

  String _csvToTable(String raw, {String delimiter = ','}) {
    final lines = const LineSplitter().convert(raw.trim());
    if (lines.isEmpty) {
      return '<div class="muted">No data</div>';
    }
    List<List<String>> rows = lines
        .map((l) => l.split(delimiter).map((c) => c.trim()).toList())
        .toList();

    final header = rows.first;
    final body = rows.skip(1);

    final headHtml = header.map((h) => '<th>${_safe(h)}</th>').join();
    final bodyHtml = body
        .map((r) => '<tr>${r.map((c) => '<td>${_safe(c)}</td>').join()}</tr>')
        .join();

    return '''
<div class="section">
  <h2>Data</h2>
  <div style="overflow:auto;">
    <table>
      <thead><tr>$headHtml</tr></thead>
      <tbody>$bodyHtml</tbody>
    </table>
  </div>
</div>
''';
  }

  String _safe(String s) => s
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;');
}

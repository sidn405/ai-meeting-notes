// lib/screens/results_screen.dart
import 'package:flutter/material.dart';
import '../services/api_service.dart';

class ResultsScreen extends StatefulWidget {
  final String meetingId;
  const ResultsScreen({super.key, required this.meetingId});

  @override
  State<ResultsScreen> createState() => _ResultsScreenState();
}

class _ResultsScreenState extends State<ResultsScreen> {
  final _api = ApiService();

  Map<String, dynamic>? _result;
  String? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() { _loading = true; _error = null; });
    try {
      final data = await ApiService.I.getMeetingSummary(widget.meetingId);
      if (!mounted) return;
      setState(() {
        _result = data;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = '$e';
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Results')),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: _loading
              ? const Center(child: CircularProgressIndicator())
              : _error != null
                  ? Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Error', style: theme.textTheme.titleLarge),
                        const SizedBox(height: 8),
                        Text(_error!, style: theme.textTheme.bodyMedium),
                        const Spacer(),
                        FilledButton(
                          onPressed: _load,
                          child: const Text('Retry'),
                        )
                      ],
                    )
                  : _buildResult(context),
        ),
      ),
    );
  }

  Widget _buildResult(BuildContext context) {
    final data = _result ?? const {};
    // Adjust keys to whatever your backend returns
    final transcript = data['transcript'] as String? ?? '';
    final summary = data['summary'] as Map<String, dynamic>?;

    final execSummary = summary?['executive_summary'] as String? ?? '';
    final keyDecisions = (summary?['key_decisions'] as List?)?.cast<String>() ?? const [];
    final actionItems  = (summary?['action_items']  as List?)?.cast<Map>() ?? const [];

    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (execSummary.isNotEmpty) ...[
            Text('Executive Summary', style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 8),
            Text(execSummary),
            const SizedBox(height: 16),
          ],
          Text('Key Decisions', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 8),
          if (keyDecisions.isEmpty)
            const Text('None listed.')
          else
            ...keyDecisions.map((e) => ListTile(
                  leading: const Icon(Icons.check_circle_outline),
                  title: Text(e),
                )),
          const SizedBox(height: 16),
          Text('Action Items', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 8),
          if (actionItems.isEmpty)
            const Text('None listed.')
          else
            ...actionItems.map((e) {
              final m = e.cast<String, dynamic>();
              final owner = m['owner'] as String? ?? '';
              final title = m['title'] as String? ?? m['text'] as String? ?? '';
              final due   = m['due']   as String?; // optional
              return ListTile(
                leading: const Icon(Icons.task_alt_outlined),
                title: Text(title),
                subtitle: Text([
                  if (owner.isNotEmpty) 'Owner: $owner',
                  if (due != null && due.isNotEmpty) 'Due: $due',
                ].join('   ')),
              );
            }),
          const SizedBox(height: 16),
          ExpansionTile(
            title: const Text('Full Transcript'),
            children: [
              const SizedBox(height: 8),
              Text(
                transcript.isEmpty ? 'Not available.' : transcript,
                style: Theme.of(context).textTheme.bodyMedium,
              ),
              const SizedBox(height: 8),
            ],
          ),
        ],
      ),
    );
  }
}

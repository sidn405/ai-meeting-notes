import 'flutter/material.dart';
import '../services/api_service.dart';
import '../models/meeting.dart';

class ResultsScreen extends StatefulWidget {
  final int meetingId;

  const ResultsScreen({super.key, required this.meetingId});

  @override
  State<ResultsScreen> createState() => _ResultsScreenState();
}

class _ResultsScreenState extends State<ResultsScreen> {
  final _apiService = ApiService();
  Summary? _summary;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _fetchSummary();
  }

  Future<void> _fetchSummary() async {
    try {
      final data = await _apiService.getMeetingSummary(widget.meetingId);
      setState(() {
        _summary = Summary.fromJson(data);
        _isLoading = false;
      });
    } catch (e) {
      print('Error fetching summary: $e');
      setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Meeting Summary'),
        backgroundColor: const Color(0xFF667eea),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _summary == null
              ? const Center(child: Text('No summary available'))
              : SingleChildScrollView(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      _buildSection(
                        'Executive Summary',
                        _summary!.executiveSummary,
                        Icons.summarize,
                      ),
                      const SizedBox(height: 24),
                      _buildDecisionsSection(),
                      const SizedBox(height: 24),
                      _buildActionItemsSection(),
                    ],
                  ),
                ),
    );
  }

  Widget _buildSection(String title, String content, IconData icon) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(icon, color: const Color(0xFF667eea)),
                const SizedBox(width: 8),
                Text(
                  title,
                  style: const TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              content,
              style: const TextStyle(fontSize: 16, height: 1.5),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDecisionsSection() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Row(
              children: [
                Icon(Icons.check_circle, color: Color(0xFF667eea)),
                SizedBox(width: 8),
                Text(
                  'Key Decisions',
                  style: TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            if (_summary!.keyDecisions.isEmpty)
              const Text('No key decisions recorded')
            else
              ..._summary!.keyDecisions.map(
                (decision) => Padding(
                  padding: const EdgeInsets.symmetric(vertical: 4),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('• ', style: TextStyle(fontSize: 20)),
                      Expanded(
                        child: Text(
                          decision,
                          style: const TextStyle(fontSize: 16),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildActionItemsSection() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Row(
              children: [
                Icon(Icons.assignment, color: Color(0xFF667eea)),
                SizedBox(width: 8),
                Text(
                  'Action Items',
                  style: TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            if (_summary!.actionItems.isEmpty)
              const Text('No action items')
            else
              ..._summary!.actionItems.map(
                (item) => Card(
                  color: Colors.grey.shade100,
                  margin: const EdgeInsets.only(bottom: 8),
                  child: ListTile(
                    title: Text(item.task ?? 'No task'),
                    subtitle: Text(item.owner ?? 'Unassigned'),
                    trailing: item.priority != null
                        ? Chip(
                            label: Text(item.priority!),
                            backgroundColor: _getPriorityColor(item.priority!),
                          )
                        : null,
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Color _getPriorityColor(String priority) {
    switch (priority.toLowerCase()) {
      case 'high':
        return Colors.red.shade200;
      case 'medium':
        return Colors.orange.shade200;
      case 'low':
        return Colors.blue.shade200;
      default:
        return Colors.grey.shade200;
    }
  }
}
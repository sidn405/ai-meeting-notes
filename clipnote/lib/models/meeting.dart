class Meeting {
  final int id;
  final String title;
  final String status;
  final int progress;
  final String? step;
  final String? audioPath;
  final String? transcriptPath;
  final String? summaryPath;
  final DateTime createdAt;

  Meeting({
    required this.id,
    required this.title,
    required this.status,
    required this.progress,
    this.step,
    this.audioPath,
    this.transcriptPath,
    this.summaryPath,
    required this.createdAt,
  });

  factory Meeting.fromJson(Map<String, dynamic> json) {
    return Meeting(
      id: json['id'],
      title: json['title'],
      status: json['status'],
      progress: json['progress'] ?? 0,
      step: json['step'],
      audioPath: json['audio_path'],
      transcriptPath: json['transcript_path'],
      summaryPath: json['summary_path'],
      createdAt: DateTime.parse(json['created_at']),
    );
  }
}

class Summary {
  final String executiveSummary;
  final List<String> keyDecisions;
  final List<ActionItem> actionItems;

  Summary({
    required this.executiveSummary,
    required this.keyDecisions,
    required this.actionItems,
  });

  factory Summary.fromJson(Map<String, dynamic> json) {
    return Summary(
      executiveSummary: json['executive_summary'] ?? '',
      keyDecisions: List<String>.from(json['key_decisions'] ?? []),
      actionItems: (json['action_items'] as List?)
              ?.map((item) => ActionItem.fromJson(item))
              .toList() ??
          [],
    );
  }
}

class ActionItem {
  final String? owner;
  final String? task;
  final String? dueDate;
  final String? priority;

  ActionItem({
    this.owner,
    this.task,
    this.dueDate,
    this.priority,
  });

  factory ActionItem.fromJson(Map<String, dynamic> json) {
    return ActionItem(
      owner: json['owner'],
      task: json['task'],
      dueDate: json['due_date'],
      priority: json['priority'],
    );
  }
}
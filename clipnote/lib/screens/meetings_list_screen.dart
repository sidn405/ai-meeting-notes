import 'package:flutter/material.dart';

class MeetingsListScreen extends StatelessWidget {
  const MeetingsListScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Meetings'),
        backgroundColor: const Color(0xFF667eea),
      ),
      body: const Center(
        child: Text('Meetings list coming soon'),
      ),
    );
  }
}
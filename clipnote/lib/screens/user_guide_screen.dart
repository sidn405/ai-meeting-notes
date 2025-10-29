import 'package:flutter/material.dart';
import 'privacy_policy_screen.dart';

class UserGuideScreen extends StatelessWidget {
  const UserGuideScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('User Guide'),
        backgroundColor: const Color(0xFF667eea),
        foregroundColor: Colors.white,
        elevation: 0,
      ),
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [
              Color(0xFF667eea),
              Color(0xFF764ba2),
            ],
          ),
        ),
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            _guideCard(
              icon: Icons.privacy_tip,
              title: 'Privacy & Data',
              description: 'Learn how we protect your data and manage your privacy.',
              action: TextButton(
                onPressed: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (context) => const PrivacyPolicyScreen(),
                    ),
                  );
                },
                style: TextButton.styleFrom(
                  foregroundColor: const Color(0xFF667eea),
                ),
                child: const Text(
                  'View Privacy Policy →',
                  style: TextStyle(fontWeight: FontWeight.w600),
                ),
              ),
            ),
            const SizedBox(height: 16),

            _guideCard(
              icon: Icons.mic,
              title: 'Recording Meetings',
              description: 'Tap the Record button on the Record Video screen to start capturing audio or video. '
                  'You can also upload existing files or paste transcripts.',
            ),
            const SizedBox(height: 16),
            
            _guideCard(
              icon: Icons.upload_file,
              title: 'Uploading Files',
              description: 'Choose "Audio/Video File" to upload media files. '
                  
            ),
            const SizedBox(height: 16),
            
            _guideCard(
              icon: Icons.description,
              title: 'From Transcript',
              description: 'Already have a transcript? Paste it directly and get an instant summary '
                  'without needing audio or video files.',
            ),
            const SizedBox(height: 16),
            
            _guideCard(
              icon: Icons.auto_awesome,
              title: 'AI Processing',
              description: 'Our AI automatically transcribes your meetings and generates summaries, '
                  'action items, and key insights.',
            ),
            const SizedBox(height: 16),
            
            _guideCard(
              icon: Icons.cloud_upload,
              title: 'Storage Options',
              description: 'Saves to your device\n'
                  'Pro & Business Tiers: Includes cloud storage with unlimited access and faster processing.',
            ),
            const SizedBox(height: 16),
            
            _guideCard(
              icon: Icons.star,
              title: 'Upgrade Benefits',
              description: 'Starter: 50MB upload size, 25 meetings\n'
              'Professional: 200MB uploads, 50 meetings, free cloud storage\n'
                  'Business: 500MB upload size, free cloud storage, record video.',
            ),
            const SizedBox(height: 16),
            
            _guideCard(
              icon: Icons.help_outline,
              title: 'Need Help?',
              description: 'Visit our website for detailed documentation, FAQs, and video tutorials.',
              action: TextButton(
                onPressed: () {
                  // TODO: Open website or support page
                },
                style: TextButton.styleFrom(
                  foregroundColor: const Color(0xFF667eea),
                ),
                child: const Text(
                  'Visit Support Center →',
                  style: TextStyle(fontWeight: FontWeight.w600),
                ),
              ),
            ),
            const SizedBox(height: 16),
            
            // Quick Tips Section
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(16),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Row(
                    children: [
                      Icon(Icons.lightbulb, color: Color(0xFF667eea)),
                      SizedBox(width: 8),
                      Text(
                        'Quick Tips',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  _tipItem('Use clear audio for best transcription results'),
                  _tipItem('Add titles to organize your meetings better'),
                  _tipItem('Cloud storage keeps your data safe and accessible'),
                  _tipItem('Summaries highlight key points and action items'),
                ],
              ),
            ),
            const SizedBox(height: 32),
          ],
        ),
      ),
    );
  }

  Widget _guideCard({
    required IconData icon,
    required String title,
    required String description,
    Widget? action,
  }) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.1),
            blurRadius: 10,
            offset: const Offset(0, 5),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: const Color(0xFF667eea).withOpacity(0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(icon, color: const Color(0xFF667eea), size: 28),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Text(
                  title,
                  style: const TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            description,
            style: TextStyle(
              fontSize: 14,
              color: Colors.grey.shade700,
              height: 1.5,
            ),
          ),
          if (action != null) ...[
            const SizedBox(height: 12),
            action,
          ],
        ],
      ),
    );
  }

  Widget _tipItem(String text) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.check_circle, color: Color(0xFF667eea), size: 20),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              text,
              style: TextStyle(
                fontSize: 14,
                color: Colors.grey.shade700,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
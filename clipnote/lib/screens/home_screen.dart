import 'package:flutter/material.dart';
import '../services/api_service.dart';
import 'activation_screen.dart';
import 'upload_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final _api = ApiService.I;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Clipnote'),
        elevation: 0,
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 32),
        children: [
          _card(
            context,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Welcome 👋',
                    style: theme.textTheme.headlineSmall
                        ?.copyWith(fontWeight: FontWeight.w700)),
                const SizedBox(height: 12),
                Text(
                  'Free tier is active. Upgrade to unlock longer files and faster processing.\n'
                  'Already purchased on the web or via sales? Enter your license.',
                  style: theme.textTheme.bodyLarge,
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          _pillButton(
            context,
            label: 'Upgrade',
            onPressed: () {
              // Show a simple bottom sheet with two SKUs (you’ll wire real IAP later)
              showModalBottomSheet(
                context: context,
                showDragHandle: true,
                builder: (c) => SafeArea(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      ListTile(
                        leading: const Icon(Icons.verified),
                        title: const Text('Professional (monthly)'),
                        subtitle: const Text('Longer uploads, faster processing'),
                        onTap: () {
                          Navigator.pop(c);
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text('IAP: purchase flow will start here'),
                            ),
                          );
                        },
                      ),
                      ListTile(
                        leading: const Icon(Icons.apartment),
                        title: const Text('Business (monthly)'),
                        subtitle: const Text('Seats & admin controls'),
                        onTap: () {
                          Navigator.pop(c);
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text('IAP: purchase flow will start here'),
                            ),
                          );
                        },
                      ),
                      const SizedBox(height: 12),
                    ],
                  ),
                ),
              );
            },
          ),
          const SizedBox(height: 12),
          Center(
            child: TextButton(
              onPressed: () {
                Navigator.of(context).push(
                  MaterialPageRoute(builder: (_) => const ActivationScreen()),
                );
              },
              child: const Text('I already have a license'),
            ),
          ),
          const SizedBox(height: 16),
          _card(
            context,
            child: _pillButton(
              context,
              icon: Icons.upload,
              label: 'Uploads',
              onPressed: () {
                Navigator.of(context).push(
                  MaterialPageRoute(builder: (_) => const UploadScreen()),
                );
              },
              filled: false,
            ),
          ),
        ],
      ),
    );
  }

  Widget _card(BuildContext context, {required Widget child}) {
    return Container(
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(.05),
            blurRadius: 12,
            offset: const Offset(0, 6),
          )
        ],
      ),
      padding: const EdgeInsets.all(16),
      child: child,
    );
  }

  Widget _pillButton(
    BuildContext context, {
    IconData? icon,
    required String label,
    required VoidCallback onPressed,
    bool filled = true,
  }) {
    final scheme = Theme.of(context).colorScheme;
    return SizedBox(
      height: 56,
      child: ElevatedButton.icon(
        onPressed: onPressed,
        icon: icon != null ? Icon(icon) : const SizedBox.shrink(),
        label: Text(label),
        style: ElevatedButton.styleFrom(
          backgroundColor: filled ? scheme.primary : scheme.surfaceVariant,
          foregroundColor: filled ? scheme.onPrimary : scheme.onSurfaceVariant,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(28),
          ),
          textStyle: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
        ),
      ),
    );
  }
}

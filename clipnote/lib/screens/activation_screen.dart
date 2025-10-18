// lib/screens/activation_screen.dart
import 'package:flutter/material.dart';
import '../services/api_service.dart';

class ActivationScreen extends StatefulWidget {
  const ActivationScreen({super.key});
  @override
  State<ActivationScreen> createState() => _ActivationScreenState();
}

class _ActivationScreenState extends State<ActivationScreen> {
  final _controller = TextEditingController();
  final _api = ApiService();
  bool _busy = false;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _activate() async {
    final key = _controller.text.trim();
    if (key.isEmpty) {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('Please enter a license key')));
      return;
    }
    setState(() => _busy = true);
    try {
      _api.setLicenseKey(key);
      final info = await _api.getLicenseInfo();

      final status = '${info['status'] ?? info['plan'] ?? info['tier']}'.toLowerCase();
      if (status.isNotEmpty && status != 'invalid') {
        if (!mounted) return;
        Navigator.of(context).pushNamedAndRemoveUntil('/home', (r) => false);
      } else {
        ScaffoldMessenger.of(context)
            .showSnackBar(const SnackBar(content: Text('Invalid license key')));
      }
    } catch (e) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('Activation failed: $e')));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Enter License')),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            children: [
              TextField(
                controller: _controller,
                decoration: const InputDecoration(
                  labelText: 'License Key',
                  prefixIcon: Icon(Icons.vpn_key_rounded),
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: _busy ? null : _activate,
                style: ElevatedButton.styleFrom(minimumSize: const Size.fromHeight(52)),
                child: _busy
                    ? const SizedBox(
                        width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Text('Activate License'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

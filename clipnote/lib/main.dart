import 'package:flutter/material.dart';
import 'screens/activation_screen.dart';
import 'screens/home_screen.dart';
import 'services/storage_service.dart';
import 'services/api_service.dart';

//void main() {
//  runApp(const MaterialApp(
//    debugShowCheckedModeBanner: false,
//    home: UploadScreen(),
//  ));
//}
void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const ClipnoteApp());
}

class ClipnoteApp extends StatelessWidget {
  const ClipnoteApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Clipnote',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF667eea),
        ),
        useMaterial3: true,
      ),
      home: const SplashScreen(),
      debugShowCheckedModeBanner: false,
    );
  }
}

class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> {
  @override
  void initState() {
    super.initState();
    _checkLicense();
  }

  Future<void> _checkLicense() async {
    await Future.delayed(const Duration(seconds: 2));
    
    final licenseKey = await StorageService.getLicenseKey();
    
    if (mounted) {
      if (licenseKey != null) {
        // Initialize API with license key
        final apiService = ApiService();
        apiService.setLicenseKey(licenseKey);
        
        Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => const HomeScreen()),
        );
      } else {
        Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => const ActivationScreen()),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFF667eea), Color(0xFF764ba2)],
          ),
        ),
        child: const Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(
                '🎙️',
                style: TextStyle(fontSize: 100),
              ),
              SizedBox(height: 24),
              Text(
                'Clipnote',
                style: TextStyle(
                  fontSize: 48,
                  fontWeight: FontWeight.bold,
                  color: Colors.white,
                ),
              ),
              SizedBox(height: 8),
              Text(
                'AI-powered meeting notes',
                style: TextStyle(
                  fontSize: 18,
                  color: Colors.white70,
                ),
              ),
              SizedBox(height: 40),
              CircularProgressIndicator(
                valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
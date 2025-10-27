// lib/main.dart
import 'package:flutter/material.dart';
import 'utils/route_observer.dart';
import 'screens/home_screen.dart';
import 'screens/activation_screen.dart';
import 'screens/upload_screen.dart';
import 'package:clipnote/services/api_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  
  // Initialize API service to load license key
  await ApiService.I.init();
  
  // Ensure user has a license
  await ApiService.I.ensureUserHasLicense();
  runApp(const ClipnoteApp());
}

class ClipnoteApp extends StatelessWidget {
  const ClipnoteApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Clipnote',
      theme: ThemeData(useMaterial3: true, colorSchemeSeed: Colors.indigo),
      initialRoute: '/home',
      routes: {
        '/home'     : (_) => const HomeScreen(),
        '/activate' : (_) => const ActivationScreen(),
        '/upload'   : (_) => const UploadScreen(),
      },
      // routes that need arguments can use onGenerateRoute if you like
      navigatorObservers: [routeObserver],
      home: const HomeScreen(),
    );
  }
}

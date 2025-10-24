// lib/services/api_service.dart
import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:device_info_plus/device_info_plus.dart';

class ApiService {
  static final ApiService I = ApiService._();
  ApiService._();

  // Base URL - update this to your backend URL
  final String baseUrl = 'https://ai-meeting-notes-production-81d7.up.railway.app';
  
  String? _licenseKey;
  String? _currentTier;

  /// Public getter for current tier
  String? get currentTier => _currentTier;

  /// Initialize and load saved license key
  Future<void> init() async {
    await loadLicenseKey();
  }

  /// Load license key from local storage
  Future<void> loadLicenseKey() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      _licenseKey = prefs.getString('license_key');
      if (_licenseKey != null) {
        print('[ApiService] Loaded license key: ${_licenseKey!.substring(0, 8)}...');
      } else {
        print('[ApiService] No license key found');
      }
    } catch (e) {
      print('[ApiService] Error loading license key: $e');
    }
  }

  /// Save license key to local storage
  Future<void> saveLicenseKey(String key) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('license_key', key);
      _licenseKey = key;
      print('[ApiService] Saved license key');
    } catch (e) {
      print('[ApiService] Error saving license key: $e');
    }
  }

  /// Get headers with license key if available
  Map<String, String> _getHeaders() {
    final headers = <String, String>{
      'Content-Type': 'application/json',
    };
    if (_licenseKey != null) {
      headers['X-License-Key'] = _licenseKey!;
    }
    return headers;
  }

  /// Get license info from backend
  Future<Map<String, dynamic>> getLicenseInfo() async {
    if (_licenseKey == null) {
      print('[ApiService] No license key available, returning free tier');
      return {
        'tier': 'free',
        'tier_name': 'Free',
        'meetings_per_month': 5,
        'max_file_size_mb': 25,
        'meetings_used': 0,
      };
    }

    try {
      final uri = Uri.parse('$baseUrl/license/info');
      print('[ApiService] Fetching license info from: $uri');
      print('[ApiService] Using license key: ${_licenseKey!.substring(0, 8)}...');
      
      final response = await http.get(
        uri,
        headers: _getHeaders(),
      );

      print('[ApiService] License info response status: ${response.statusCode}');
      print('[ApiService] License info response body: ${response.body}');

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        _currentTier = data['tier'] ?? 'free';
        print('[ApiService] ✅ License verified! Tier: ${_currentTier}');
        return data;
      } else {
        print('[ApiService] ❌ Error getting license info: ${response.statusCode} - ${response.body}');
        return {
          'tier': 'free',
          'tier_name': 'Free',
          'meetings_per_month': 5,
          'max_file_size_mb': 25,
          'meetings_used': 0,
        };
      }
    } catch (e) {
      print('[ApiService] ❌ Exception getting license info: $e');
      return {
        'tier': 'free',
        'tier_name': 'Free',
        'meetings_per_month': 5,
        'max_file_size_mb': 25,
        'meetings_used': 0,
      };
    }
  }

  Future<void> ensureUserHasLicense() async {
  try {
    // Check if license key already exists
    await loadLicenseKey();
    
    if (_licenseKey != null) {
      print('[ApiService] ✅ License key already exists: ${_licenseKey!.substring(0, 8)}...');
      return;
    }
    
    print('[ApiService] 📱 No license key found. Generating free tier license...');
    
    // Generate a device ID
    final deviceId = await _getDeviceId();
    
    // Request free tier license from backend
    final licenseKey = await _generateFreeTierLicense(deviceId);
    
    if (licenseKey != null) {
      await saveLicenseKey(licenseKey);
      print('[ApiService] ✅ Free tier license generated and saved!');
    } else {
      print('[ApiService] ⚠️ Failed to generate license, user will see free tier');
    }
  } catch (e) {
    print('[ApiService] ⚠️ Error ensuring license: $e');
    // Continue anyway - user gets free tier as fallback
  }
}

/// Get unique device identifier
Future<String> _getDeviceId() async {
  try {
    final deviceInfo = DeviceInfoPlugin();
    
    if (Platform.isAndroid) {
      final androidInfo = await deviceInfo.androidInfo;
      return androidInfo.id; // Android device ID
    } else if (Platform.isIOS) {
      final iosInfo = await deviceInfo.iosInfo;
      return iosInfo.identifierForVendor ?? 'ios-unknown';
    }
    
    return 'unknown-device';
  } catch (e) {
    print('[ApiService] Error getting device ID: $e');
    return 'error-device-id';
  }
}

/// Request free tier license from backend
Future<String?> _generateFreeTierLicense(String deviceId) async {
  try {
    final uri = Uri.parse('$baseUrl/license/generate-free-tier');
    
    print('[ApiService] 🔍 Attempting free tier request...');
    print('[ApiService] Base URL: $baseUrl');
    print('[ApiService] Full URI: $uri');
    print('[ApiService] Device ID: $deviceId');
    
    final request = http.Request('POST', uri);
    request.headers.addAll({
      'Content-Type': 'application/json',
      'User-Agent': 'Clipnote-App/1.0',
    });
    request.body = jsonEncode({'device_id': deviceId});
    
    print('[ApiService] Request headers: ${request.headers}');
    print('[ApiService] Request body: ${request.body}');
    
    // Set timeout and send (30 seconds for slow Railway)
    final streamedResponse = await request.send().timeout(
      const Duration(seconds: 30),
      onTimeout: () {
        throw Exception('Request timeout after 30 seconds');
      },
    );
    
    final response = await http.Response.fromStream(streamedResponse);
    
    print('[ApiService] Response status: ${response.statusCode}');
    print('[ApiService] Response headers: ${response.headers}');
    print('[ApiService] Response body: ${response.body}');

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      final licenseKey = data['license_key'];
      print('[ApiService] ✅ Free tier license received: ${licenseKey.substring(0, 8)}...');
      return licenseKey;
    } else {
      print('[ApiService] ❌ Error generating license: ${response.statusCode} - ${response.body}');
      return null;
    }
  } catch (e) {
    print('[ApiService] ❌ Network error generating license: $e');
    print('[ApiService] Error type: ${e.runtimeType}');
    return null;
  }
}

  /// Check backend health
  Future<bool> checkHealth() async {
    try {
      final uri = Uri.parse('$baseUrl/healthz');
      final response = await http.get(uri);
      return response.statusCode == 200;
    } catch (e) {
      print('[ApiService] Health check failed: $e');
      return false;
    }
  }

  /// Verify IAP receipt and get license key
  Future<String> verifyIapAndGetLicense({
    String? receipt,
    String? receiptData,
    required String productId,
    String? userId,
    String? store,
    String? email,
  }) async {
    try {
      final receiptString = receipt ?? receiptData;
      
      if (receiptString == null) {
        throw Exception('Receipt data is required');
      }
      
      final uri = Uri.parse('$baseUrl/iap/verify');
      final body = {
        'receipt_data': receiptString,
        'store': store,
        'product_id': productId,
      };
      
      if (userId != null) {
        body['user_id'] = userId;
      }
      
      final response = await http.post(
        uri,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(body),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final licenseKey = data['license_key'];
        
        await saveLicenseKey(licenseKey);
        _currentTier = data['tier'] ?? 'free';
        
        return licenseKey;
      } else {
        throw Exception('Failed to verify purchase: ${response.body}');
      }
    } catch (e) {
      print('[ApiService] Error verifying IAP: $e');
      rethrow;
    }
  }

  /// Upload meeting (multipart upload)
  Future<int> uploadMeeting({
    File? file,
    List<int>? fileBytes,
    String? filename,
    required String title,
    String? email,
    String? emailTo,
    String? language,
    String? hints,
    bool transcribeOnly = false,
    void Function(double)? onProgress,
  }) async {
    try {
      if (file == null && fileBytes == null) {
        throw Exception('Either file or fileBytes must be provided');
      }
      
      final emailAddress = email ?? emailTo;
      
      final uri = Uri.parse('$baseUrl/meetings/${transcribeOnly ? 'upload-transcribe-only' : 'upload-transcribe-summarize'}');
      
      var request = http.MultipartRequest('POST', uri);
      
      if (_licenseKey != null) {
        request.headers['X-License-Key'] = _licenseKey!;
      }
      
      request.fields['title'] = title;
      if (emailAddress != null) request.fields['email_to'] = emailAddress;
      if (language != null) request.fields['language'] = language;
      if (hints != null) request.fields['hints'] = hints;
      
      if (file != null) {
        request.files.add(await http.MultipartFile.fromPath('file', file.path));
      } else if (fileBytes != null) {
        final fileName = filename ?? 'upload.${_getExtensionFromBytes(fileBytes)}';
        request.files.add(http.MultipartFile.fromBytes(
          'file',
          fileBytes,
          filename: fileName,
        ));
      }
      
      final streamedResponse = await request.send();
      final response = await http.Response.fromStream(streamedResponse);
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return data['id'];
      } else {
        throw Exception('Upload failed: ${response.body}');
      }
    } catch (e) {
      print('[ApiService] Error uploading meeting: $e');
      rethrow;
    }
  }

  String _getExtensionFromBytes(List<int> bytes) {
    if (bytes.isEmpty) return 'bin';
    
    if (bytes.length >= 4) {
      if (bytes[0] == 0xFF && bytes[1] == 0xFB) return 'mp3';
      if (bytes[0] == 0x49 && bytes[1] == 0x44 && bytes[2] == 0x33) return 'mp3';
      
      if (bytes[4] == 0x66 && bytes[5] == 0x74 && bytes[6] == 0x79 && bytes[7] == 0x70) {
        return 'm4a';
      }
      
      if (bytes[0] == 0x52 && bytes[1] == 0x49 && bytes[2] == 0x46 && bytes[3] == 0x46) {
        return 'wav';
      }
    }
    
    return 'mp3';
  }

  /// Submit transcript (text only, no audio)
  Future<int> submitTranscript({
    required String title,
    required String transcript,
    String? email,
    String? emailTo,
  }) async {
    try {
      final uri = Uri.parse('$baseUrl/meetings/from-text');
      var request = http.MultipartRequest('POST', uri);
      
      if (_licenseKey != null) {
        request.headers['X-License-Key'] = _licenseKey!;
      }
      
      request.fields['title'] = title;
      request.fields['transcript'] = transcript;
      if (emailTo != null) request.fields['email_to'] = emailTo;
      
      final streamedResponse = await request.send();
      final response = await http.Response.fromStream(streamedResponse);
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return data['id'];
      } else {
        throw Exception('Submit failed: ${response.body}');
      }
    } catch (e) {
      print('[ApiService] Error submitting transcript: $e');
      rethrow;
    }
  }

  /// Get meeting status
  Future<Map<String, dynamic>> getMeetingStatus(int meetingId) async {
    try {
      final uri = Uri.parse('$baseUrl/meetings/$meetingId/status');
      final response = await http.get(
        uri,
        headers: _getHeaders(),  // ✅ Added license key
      );
      
      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      }
      throw Exception('Failed to get status: ${response.statusCode}');
    } catch (e) {
      print('[ApiService] Error getting meeting status: $e');
      rethrow;
    }
  }

  /// Get all meetings
  Future<List<Map<String, dynamic>>> getMeetings() async {
    try {
      final uri = Uri.parse('$baseUrl/meetings/list');
      final response = await http.get(
        uri,
        headers: _getHeaders(),  // ✅ Added license key
      );
      
      if (response.statusCode == 200) {
        final List<dynamic> data = jsonDecode(response.body);
        return data.map((item) => item as Map<String, dynamic>).toList();
      }
      throw Exception('Failed to get meetings: ${response.statusCode}');
    } catch (e) {
      print('[ApiService] Error getting meetings: $e');
      rethrow;
    }
  }

  /// Get meeting summary
  Future<Map<String, dynamic>> getMeetingSummary(int meetingId) async {
    try {
      final uri = Uri.parse('$baseUrl/meetings/$meetingId/summary');
      final response = await http.get(
        uri,
        headers: _getHeaders(),  // ✅ Added license key
      );
      
      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      }
      throw Exception('Summary not found: ${response.statusCode}');
    } catch (e) {
      print('[ApiService] Error getting summary: $e');
      rethrow;
    }
  }

  /// Get meeting transcript
  Future<Map<String, dynamic>> getMeetingTranscript(int meetingId) async {
    try {
      final uri = Uri.parse('$baseUrl/meetings/$meetingId/transcript');
      final response = await http.get(
        uri,
        headers: _getHeaders(),  // ✅ Added license key
      );
      
      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      }
      throw Exception('Transcript not found: ${response.statusCode}');
    } catch (e) {
      print('[ApiService] Error getting transcript: $e');
      rethrow;
    }
  }

  /// Send meeting email (simplified - backend fetches content)
  Future<void> sendMeetingEmail(int meetingId, String email) async {
    try {
      print('[ApiService] 📧 Sending email for meeting $meetingId to $email');
      
      final uri = Uri.parse('$baseUrl/meetings/email');
      print('[ApiService] 📧 POST endpoint: $uri');
      
      final payload = {
        'meeting_id': meetingId,
        'email': email,
        'include_transcript': true,
        'include_summary': true,
      };
      
      print('[ApiService] 📧 Request payload: ${jsonEncode(payload)}');
      
      final response = await http.post(
        uri,
        headers: {
          'Content-Type': 'application/json',
          ..._getHeaders(),  // ✅ Include license key if available
        },
        body: jsonEncode(payload),
      );
      
      print('[ApiService] 📧 Response status: ${response.statusCode}');
      print('[ApiService] 📧 Response body: ${response.body}');
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        print('[ApiService] ✅ Email queued successfully: ${data['message']}');
        return;
      } else if (response.statusCode == 404) {
        throw Exception('Meeting not found or summary not available');
      } else if (response.statusCode == 400) {
        final error = jsonDecode(response.body);
        throw Exception(error['detail'] ?? 'Invalid request');
      } else {
        throw Exception('Failed to send email: ${response.statusCode} - ${response.body}');
      }
    } catch (e) {
      print('[ApiService] ❌ Error sending email: $e');
      rethrow;
    }
  }

  /// Download meeting file
  Future<Map<String, dynamic>> downloadMeetingFile(
    int meetingId,
    String type,
  ) async {
    try {
      print('[ApiService] ⬇️ Preparing download for meeting $meetingId, type: $type');
      
      // Construct the download URL with type as query parameter
      final downloadUrl = '$baseUrl/meetings/$meetingId/download?type=$type';
      print('[ApiService] ⬇️ Download URL: $downloadUrl');
      
      // Don't verify with HEAD - just return the URL
      // The browser will handle 404s when the user tries to open it
      
      return {
        'filename': _getFilenameForType(type, meetingId),
        'download_url': downloadUrl,
        'success': true,
        'type': type,
      };
    } catch (e) {
      print('[ApiService] ❌ Error preparing download: $e');
      rethrow;
    }
  }

/// Helper to generate appropriate filename based on type
String _getFilenameForType(String type, int meetingId) {
  switch (type.toLowerCase()) {
    case 'transcript':
      return 'meeting_${meetingId}_transcript.txt';
    case 'summary':
      return 'meeting_${meetingId}_summary.txt';
    case 'pdf':
      return 'meeting_${meetingId}_report.pdf';
    case 'all':
      return 'meeting_${meetingId}_files.zip';
    default:
      return 'meeting_${meetingId}_download.txt';
  }
}

  /// Get meeting statistics
  Future<Map<String, dynamic>> getMeetingStats() async {
    try {
      final uri = Uri.parse('$baseUrl/meetings/stats');
      final response = await http.get(
        uri,
        headers: _getHeaders(),  // ✅ Added license key
      );
      
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        print('[ApiService] Meeting stats loaded: $data');
        return data;
      } else {
        print('[ApiService] Failed to get stats: ${response.statusCode} - ${response.body}');
        throw Exception('Failed to get meeting stats: ${response.statusCode}');
      }
    } catch (e) {
      print('[ApiService] Error getting stats: $e');
      rethrow;
    }
  }

  /// Delete meeting
  Future<void> deleteMeeting(int meetingId) async {
    try {
      final uri = Uri.parse('$baseUrl/meetings/$meetingId');
      final response = await http.delete(
        uri,
        headers: _getHeaders(),  // ✅ Added license key
      );
      
      if (response.statusCode != 200) {
        throw Exception('Failed to delete meeting: ${response.statusCode}');
      }
    } catch (e) {
      print('[ApiService] Error deleting meeting: $e');
      rethrow;
    }
  }
}
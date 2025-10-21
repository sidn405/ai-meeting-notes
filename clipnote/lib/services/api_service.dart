// lib/services/api_service.dart
import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

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
      final response = await http.get(
        uri,
        headers: _getHeaders(),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        _currentTier = data['tier'] ?? 'free';
        return data;
      } else {
        print('[ApiService] Error getting license info: ${response.statusCode}');
        return {
          'tier': 'free',
          'tier_name': 'Free',
          'meetings_per_month': 5,
          'max_file_size_mb': 25,
          'meetings_used': 0,
        };
      }
    } catch (e) {
      print('[ApiService] Error getting license info: $e');
      return {
        'tier': 'free',
        'tier_name': 'Free',
        'meetings_per_month': 5,
        'max_file_size_mb': 25,
        'meetings_used': 0,
      };
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
      final uri = Uri.parse('$baseUrl/meetings/email');
      final response = await http.post(
        uri,
        headers: _getHeaders(),  // ✅ Added license key
        body: jsonEncode({
          'meeting_id': meetingId,
          'email': email,
          'include_transcript': true,
          'include_summary': true,
        }),
      );
      
      if (response.statusCode != 200) {
        throw Exception('Failed to send email: ${response.body}');
      }
    } catch (e) {
      print('[ApiService] Error sending email: $e');
      rethrow;
    }
  }

  /// Download meeting file
  Future<Map<String, dynamic>> downloadMeetingFile(
    int meetingId,
    String type,
  ) async {
    try {
      final downloadUrl = '$baseUrl/meetings/$meetingId/download?type=$type';
      
      return {
        'filename': '${type}_$meetingId.txt',
        'download_url': downloadUrl,
      };
    } catch (e) {
      print('[ApiService] Error downloading file: $e');
      rethrow;
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
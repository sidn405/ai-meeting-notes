import 'dart:convert';
import 'dart:io' show Platform;
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutter/foundation.dart';

class ApiService {
  static final ApiService I = ApiService._();
  ApiService._();
  
  final String baseUrl = 'https://ai-meeting-notes-production-81d7.up.railway.app';
  String? _licenseKey;
  
  // Timeout duration for all requests
  static const Duration timeoutDuration = Duration(seconds: 30);
  
  void _log(String message) {
    if (kDebugMode) {
      print('[ApiService] $message');
    }
  }
  
  // Save license key after IAP verification
  void setLicenseKey(String key) {
    _licenseKey = key;
    _saveLicenseKeyToStorage(key);
  }
  
  Future<void> _saveLicenseKeyToStorage(String key) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('license_key', key);
  }
  
  Future<void> loadLicenseKey() async {
    final prefs = await SharedPreferences.getInstance();
    _licenseKey = prefs.getString('license_key');
  }
  
  // Add license key to all API calls
  Map<String, String> _getHeaders() {
    final headers = {'Content-Type': 'application/json'};
    if (_licenseKey != null) {
      headers['X-License-Key'] = _licenseKey!;
    }
    return headers;
  }
  
  // Submit transcript directly (uses backend's /meetings/from-text endpoint)
  Future<String> submitTranscript({
    required String title,
    required String transcript,
    String? email,
  }) async {
    _log('Submitting transcript directly: $title');
    
    try {
      final request = http.MultipartRequest(
        'POST',
        Uri.parse('$baseUrl/meetings/from-text'),
      );
      
      // Add license header if available
      if (_licenseKey != null) {
        request.headers['X-License-Key'] = _licenseKey!;
      }
      
      // Add form fields
      request.fields['title'] = title;
      request.fields['transcript'] = transcript;
      if (email != null && email.isNotEmpty) {
        request.fields['email_to'] = email;
      }
      
      _log('Sending transcript submission...');
      
      final streamedResponse = await request.send().timeout(timeoutDuration);
      final response = await http.Response.fromStream(streamedResponse);
      
      _log('Submit transcript response: ${response.statusCode}');
      
      if (response.statusCode != 200 && response.statusCode != 201) {
        throw Exception('Failed to submit transcript: ${response.body}');
      }
      
      final data = jsonDecode(response.body);
      final meetingId = data['id'].toString();
      _log('Transcript submitted, meeting ID: $meetingId');
      return meetingId;
    } catch (e) {
      _log('Error submitting transcript: $e');
      rethrow;
    }
  }
  
  // Upload file to backend (uses /meetings/upload endpoint)
  Future<String> uploadMeeting({
    required String title,
    required List<int> fileBytes,
    required String filename,
    String? email,
    String? language,
    String? hints,
  }) async {
    _log('Uploading meeting: $title, file: $filename');
    
    try {
      final request = http.MultipartRequest(
        'POST',
        Uri.parse('$baseUrl/meetings/upload'),
      );
      
      // Add license header if available
      if (_licenseKey != null) {
        request.headers['X-License-Key'] = _licenseKey!;
      }
      
      // Add form fields
      request.fields['title'] = title;
      if (email != null && email.isNotEmpty) {
        request.fields['email_to'] = email;
      }
      if (language != null && language != 'auto') {
        request.fields['language'] = language;
      }
      if (hints != null && hints.isNotEmpty) {
        request.fields['hints'] = hints;
      }
      
      // Add file
      request.files.add(
        http.MultipartFile.fromBytes(
          'file',
          fileBytes,
          filename: filename,
        ),
      );
      
      _log('Sending multipart request...');
      
      // Calculate timeout based on file size
      final sizeInMB = fileBytes.length / (1024 * 1024);
      final estimatedMinutes = 2 + (sizeInMB / 10).ceil();
      final timeout = Duration(minutes: estimatedMinutes.clamp(2, 15));
      
      _log('Upload timeout: ${timeout.inMinutes} minutes for ${sizeInMB.toStringAsFixed(2)}MB');
      
      final streamedResponse = await request.send().timeout(timeout);
      final response = await http.Response.fromStream(streamedResponse);
      
      _log('Upload response: ${response.statusCode}');
      
      if (response.statusCode != 200 && response.statusCode != 201) {
        throw Exception('Failed to upload meeting: ${response.body}');
      }
      
      final data = jsonDecode(response.body);
      final meetingId = data['id'].toString();
      _log('Meeting uploaded successfully: $meetingId');
      return meetingId;
    } catch (e) {
      _log('Error uploading meeting: $e');
      rethrow;
    }
  }
  
  // Verify IAP and get license key
  Future<String> verifyIapAndGetLicense({
    required String userId,
    required String receipt,
    required String productId,
    required String store,
    String? email,
  }) async {
    _log('Verifying IAP for user: $userId');
    
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/iap/verify'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'user_id': userId,
          'email': email,
          'receipt': receipt,
          'product_id': productId,
          'store': store,
        }),
      ).timeout(timeoutDuration);
      
      _log('IAP verification response: ${response.statusCode}');
      
      if (response.statusCode != 200) {
        throw Exception('IAP verification failed: ${response.body}');
      }
      
      final data = jsonDecode(response.body);
      final licenseKey = data['license_key'] as String;
      
      setLicenseKey(licenseKey);
      
      return licenseKey;
    } catch (e) {
      _log('Error verifying IAP: $e');
      rethrow;
    }
  }
  
  // Get license info
  Future<Map<String, dynamic>> getLicenseInfo() async {
    if (_licenseKey == null) {
      throw Exception('No license key available');
    }
    
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/iap/subscription-status/$_licenseKey'),
      ).timeout(timeoutDuration);
      
      if (response.statusCode != 200) {
        throw Exception('Failed to get license info: ${response.body}');
      }
      
      return jsonDecode(response.body);
    } catch (e) {
      _log('Error getting license info: $e');
      rethrow;
    }
  }
  
  // Get meeting processing status
  Future<Map<String, dynamic>> getMeetingStatus(String meetingId) async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/meetings/$meetingId/status'),
        headers: _getHeaders(),
      ).timeout(timeoutDuration);
      
      if (response.statusCode != 200) {
        throw Exception('Failed to get status: ${response.body}');
      }
      
      return jsonDecode(response.body);
    } catch (e) {
      _log('Error getting meeting status: $e');
      rethrow;
    }
  }
  
  // Get meeting summary
  Future<Map<String, dynamic>> getMeetingSummary(int meetingId) async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/meetings/$meetingId/summary'),
        headers: _getHeaders(),
      ).timeout(timeoutDuration);
      
      if (response.statusCode != 200) {
        throw Exception('Failed to get summary: ${response.body}');
      }
      
      return jsonDecode(response.body);
    } catch (e) {
      _log('Error getting meeting summary: $e');
      rethrow;
    }
  }
  
  // Get user info (tier, usage, limits)
  Future<Map<String, dynamic>> getUserInfo(String userId) async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/users/$userId/info'),
        headers: _getHeaders(),
      ).timeout(timeoutDuration);
      
      if (response.statusCode != 200) {
        throw Exception('Failed to get user info: ${response.body}');
      }
      
      return jsonDecode(response.body);
    } catch (e) {
      _log('Error getting user info: $e');
      rethrow;
    }
  }
  
  // Increment user's monthly usage
  Future<void> incrementUserUsage(String userId) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/users/$userId/usage/increment'),
        headers: _getHeaders(),
      ).timeout(timeoutDuration);
      
      if (response.statusCode != 200) {
        throw Exception('Failed to increment usage: ${response.body}');
      }
    } catch (e) {
      _log('Error incrementing usage: $e');
      rethrow;
    }
  }
  
  // Health check - test if backend is reachable
  Future<bool> checkHealth() async {
    try {
      _log('Checking backend health...');
      final response = await http.get(
        Uri.parse('$baseUrl/health'),
      ).timeout(const Duration(seconds: 10));
      
      _log('Health check response: ${response.statusCode}');
      return response.statusCode == 200;
    } catch (e) {
      _log('Backend health check failed: $e');
      return false;
    }
  }
}
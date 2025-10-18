import 'dart:convert';
import 'dart:io' show Platform;
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class ApiService {
  static final ApiService I = ApiService._();
  ApiService._();
  
  final String baseUrl = 'https://ai-meeting-notes-production-81d7.up.railway.app';
  String? _licenseKey;
  
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
  
  // Create a new meeting
  Future<String> createMeeting({
    required String title,
    String? audioKey,
    String? email,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/meetings'),
      headers: _getHeaders(),
      body: jsonEncode({
        'title': title,
        if (audioKey != null) 'audio_key': audioKey,
        if (email != null) 'email_to': email,
      }),
    );
    
    if (response.statusCode != 200 && response.statusCode != 201) {
      throw Exception('Failed to create meeting: ${response.body}');
    }
    
    final data = jsonDecode(response.body);
    return data['id'].toString();
  }
  
  // Verify IAP and get license key
  Future<String> verifyIapAndGetLicense({
    required String userId,
    required String receipt,
    required String productId,
    required String store,
    String? email,
  }) async {
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
    );
    
    if (response.statusCode != 200) {
      throw Exception('IAP verification failed: ${response.body}');
    }
    
    final data = jsonDecode(response.body);
    final licenseKey = data['license_key'] as String;
    
    setLicenseKey(licenseKey);
    
    return licenseKey;
  }
  
  // Get license info
  Future<Map<String, dynamic>> getLicenseInfo() async {
    if (_licenseKey == null) {
      throw Exception('No license key available');
    }
    
    final response = await http.get(
      Uri.parse('$baseUrl/iap/subscription-status/$_licenseKey'),
    );
    
    if (response.statusCode != 200) {
      throw Exception('Failed to get license info: ${response.body}');
    }
    
    return jsonDecode(response.body);
  }
  
  // Submit transcript to existing meeting and trigger summarization
  Future<void> submitTranscriptToMeeting({
    required String meetingId,
    required String transcript,
  }) async {
    await http.put(
      Uri.parse('$baseUrl/meetings/$meetingId'),
      headers: _getHeaders(),
      body: jsonEncode({
        'transcript_text': transcript,
      }),
    );
    
    final response = await http.post(
      Uri.parse('$baseUrl/meetings/$meetingId/summarize'),
      headers: _getHeaders(),
    );
    
    if (response.statusCode != 200 && response.statusCode != 202) {
      throw Exception('Failed to start summarization: ${response.body}');
    }
  }
  
  // Start processing (transcription and/or summarization)
  Future<void> startProcessing({
    required String meetingId,
    required String s3key,
    required String mode,
    String? language,
    String? hints,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/meetings/$meetingId/process'),
      headers: _getHeaders(),
      body: jsonEncode({
        's3_key': s3key,
        'mode': mode,
        if (language != null) 'language': language,
        if (hints != null) 'hints': hints,
      }),
    );
    
    if (response.statusCode != 200 && response.statusCode != 202) {
      throw Exception('Failed to start processing: ${response.body}');
    }
  }
  
  // Get meeting processing status
  Future<Map<String, dynamic>> getMeetingStatus(String meetingId) async {
    final response = await http.get(
      Uri.parse('$baseUrl/meetings/$meetingId/status'),
      headers: _getHeaders(),
    );
    
    if (response.statusCode != 200) {
      throw Exception('Failed to get status: ${response.body}');
    }
    
    return jsonDecode(response.body);
  }
  
  // Get meeting summary
  Future<Map<String, dynamic>> getMeetingSummary(int meetingId) async {
    final response = await http.get(
      Uri.parse('$baseUrl/meetings/$meetingId/summary'),
      headers: _getHeaders(),
    );
    
    if (response.statusCode != 200) {
      throw Exception('Failed to get summary: ${response.body}');
    }
    
    return jsonDecode(response.body);
  }
  
  // Presign upload
  Future<PresignResponse> presignUpload({
    required String filename,
    required String contentType,
    required String folder,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/uploads/presign'),
      headers: _getHeaders(),
      body: jsonEncode({
        'filename': filename,
        'content_type': contentType,
        'folder': folder,
      }),
    );
    
    if (response.statusCode != 200) {
      throw Exception('Failed to get presigned URL: ${response.body}');
    }
    
    final data = jsonDecode(response.body);
    return PresignResponse(
      url: data['url'],
      key: data['key'],
      headers: Map<String, String>.from(data['headers'] ?? {}),
      method: data['method'] ?? 'PUT',
      publicUrl: data['public_url'],
    );
  }
  
  // Upload bytes to presigned URL
  Future<void> putBytes({
    required String url,
    required List<int> bytes,
    required Map<String, String> headers,
    required String method,
  }) async {
    final request = http.Request(method, Uri.parse(url));
    request.headers.addAll(headers);
    request.bodyBytes = bytes;
    
    final streamedResponse = await request.send();
    
    if (streamedResponse.statusCode != 200) {
      final body = await streamedResponse.stream.bytesToString();
      throw Exception('Upload failed: ${streamedResponse.statusCode} $body');
    }
  }
  
  // Get user info (tier, usage, limits)
  Future<Map<String, dynamic>> getUserInfo(String userId) async {
    final response = await http.get(
      Uri.parse('$baseUrl/users/$userId/info'),
      headers: _getHeaders(),
    );
    
    if (response.statusCode != 200) {
      throw Exception('Failed to get user info: ${response.body}');
    }
    
    return jsonDecode(response.body);
  }
  
  // Increment user's monthly usage
  Future<void> incrementUserUsage(String userId) async {
    final response = await http.post(
      Uri.parse('$baseUrl/users/$userId/usage/increment'),
      headers: _getHeaders(),
    );
    
    if (response.statusCode != 200) {
      throw Exception('Failed to increment usage: ${response.body}');
    }
  }
}

class PresignResponse {
  final String url;
  final String key;
  final Map<String, String> headers;
  final String method;
  final String? publicUrl;
  
  PresignResponse({
    required this.url,
    required this.key,
    required this.headers,
    required this.method,
    this.publicUrl,
  });
}
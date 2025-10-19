import 'dart:convert';
import 'dart:typed_data';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class ApiService {
  static final ApiService I = ApiService._();
  ApiService._();

  final String baseUrl = 'https://ai-meeting-notes-production-81d7.up.railway.app';
  
  String? _licenseKey;
  String? _currentTier = 'free';

  void setLicenseKey(String? key) {
    _licenseKey = key;
  }

  String get currentTier => _currentTier ?? 'free';

  /// Load license key from storage
  Future<void> loadLicenseKey() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      _licenseKey = prefs.getString('license_key');
      if (_licenseKey != null) {
        print('[ApiService] Loaded license key: ${_licenseKey!.substring(0, 8)}...');
      }
    } catch (e) {
      print('[ApiService] Error loading license key: $e');
    }
  }

  /// Save license key to storage
  Future<void> saveLicenseKey(String key) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('license_key', key);
      _licenseKey = key;
      print('[ApiService] License key saved');
    } catch (e) {
      print('[ApiService] Error saving license key: $e');
    }
  }

  /// Get license info from backend
  Future<Map<String, dynamic>> getLicenseInfo() async {
    if (_licenseKey == null) {
      return {
        'tier': 'free',
        'max_file_size_mb': 25,
        'meetings_per_month': 5,
        'meetings_used': 0,
      };
    }

    try {
      final uri = Uri.parse('$baseUrl/license/info');
      final response = await http.get(
        uri,
        headers: {
          'X-License-Key': _licenseKey!,
        },
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        _currentTier = data['tier'] ?? 'free';
        return data;
      } else {
        // Fallback to free tier
        return {
          'tier': 'free',
          'max_file_size_mb': 25,
          'meetings_per_month': 5,
          'meetings_used': 0,
        };
      }
    } catch (e) {
      print('[ApiService] Error getting license info: $e');
      return {
        'tier': 'free',
        'max_file_size_mb': 25,
        'meetings_per_month': 5,
        'meetings_used': 0,
      };
    }
  }

  /// Check backend health
  Future<bool> checkHealth() async {
    try {
      final uri = Uri.parse('$baseUrl/health');
      final response = await http.get(uri).timeout(const Duration(seconds: 5));
      return response.statusCode == 200;
    } catch (e) {
      print('[ApiService] Health check failed: $e');
      return false;
    }
  }

  /// Verify IAP purchase and get license key
  Future<String> verifyIapAndGetLicense({
    required String purchaseToken,
    required String productId,
    required String store, // 'google_play' or 'app_store'
  }) async {
    final uri = Uri.parse('$baseUrl/iap/verify');
    
    final response = await http.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'purchase_token': purchaseToken,
        'product_id': productId,
        'store': store,
      }),
    ).timeout(const Duration(seconds: 30));

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      final licenseKey = data['license_key'] as String;
      
      // Save the license key
      await saveLicenseKey(licenseKey);
      
      return licenseKey;
    } else {
      throw Exception('IAP verification failed: ${response.body}');
    }
  }

  /// Main upload method - automatically chooses multipart for large files
  Future<int> uploadMeeting({
    required String title,
    required Uint8List fileBytes,
    required String filename,
    String? email,
    String? language,
    String? hints,
    bool transcribeOnly = false,
    Function(double)? onProgress,
  }) async {
    final fileSizeMB = fileBytes.length / (1024 * 1024);
    
    // Use multipart upload for files > 20MB
    if (fileSizeMB > 20) {
      print('[ApiService] Large file detected (${fileSizeMB.toStringAsFixed(2)}MB), using multipart upload');
      return await _uploadLargeFile(
        title: title,
        fileBytes: fileBytes,
        filename: filename,
        email: email,
        language: language,
        hints: hints,
        transcribeOnly: transcribeOnly,
        onProgress: onProgress,
      );
    } else {
      print('[ApiService] Small file (${fileSizeMB.toStringAsFixed(2)}MB), using direct upload');
      return await _uploadDirectly(
        title: title,
        fileBytes: fileBytes,
        filename: filename,
        email: email,
        language: language,
        hints: hints,
        transcribeOnly: transcribeOnly,
      );
    }
  }

  /// Direct upload for smaller files (< 20MB)
  Future<int> _uploadDirectly({
    required String title,
    required Uint8List fileBytes,
    required String filename,
    String? email,
    String? language,
    String? hints,
    required bool transcribeOnly,
  }) async {
    print('[ApiService] Direct upload: $title, file: $filename');

    final endpoint = transcribeOnly 
        ? '/meetings/upload-transcribe-only'
        : '/meetings/upload-transcribe-summarize';

    final uri = Uri.parse('$baseUrl$endpoint');
    final request = http.MultipartRequest('POST', uri);

    if (_licenseKey != null) {
      request.headers['X-License-Key'] = _licenseKey!;
    }

    request.fields['title'] = title;
    if (email != null && email.isNotEmpty) {
      request.fields['email_to'] = email;
    }
    if (language != null && language.isNotEmpty) {
      request.fields['language'] = language;
    }
    if (hints != null && hints.isNotEmpty) {
      request.fields['hints'] = hints;
    }

    request.files.add(http.MultipartFile.fromBytes(
      'file',
      fileBytes,
      filename: filename,
    ));

    final fileSizeMB = fileBytes.length / (1024 * 1024);
    final timeoutMinutes = fileSizeMB > 10 ? 5 : 3;

    try {
      final streamedResponse = await request.send()
          .timeout(Duration(minutes: timeoutMinutes));
      final response = await http.Response.fromStream(streamedResponse);

      print('[ApiService] Response: ${response.statusCode}');

      if (response.statusCode == 200 || response.statusCode == 201) {
        final data = jsonDecode(response.body);
        return data['id'] as int;
      } else if (response.statusCode == 413) {
        throw Exception('File too large for your account tier');
      } else if (response.statusCode == 429) {
        throw Exception('Monthly meeting limit reached');
      } else {
        throw Exception('Upload failed: ${response.body}');
      }
    } catch (e) {
      print('[ApiService] Error: $e');
      rethrow;
    }
  }

  /// Multipart upload for large files (> 20MB)
  Future<int> _uploadLargeFile({
    required String title,
    required Uint8List fileBytes,
    required String filename,
    String? email,
    String? language,
    String? hints,
    required bool transcribeOnly,
    Function(double)? onProgress,
  }) async {
    print('[ApiService] Starting multipart upload for: $filename');

    try {
      // Step 1: Upload file to S3 using multipart
      final fileUrl = await _uploadToS3Multipart(
        fileBytes: fileBytes,
        filename: filename,
        onProgress: (progress) {
          // Report 0-80% for upload phase
          onProgress?.call(progress * 0.8);
        },
      );

      print('[ApiService] File uploaded to S3: $fileUrl');
      onProgress?.call(85.0);

      // Step 2: Create meeting record with S3 URL
      final meetingId = await _createMeetingFromUrl(
        title: title,
        fileUrl: fileUrl,
        filename: filename,
        email: email,
        language: language,
        hints: hints,
        transcribeOnly: transcribeOnly,
      );

      onProgress?.call(100.0);
      print('[ApiService] Meeting created with ID: $meetingId');
      
      return meetingId;
    } catch (e) {
      print('[ApiService] Multipart upload failed: $e');
      rethrow;
    }
  }

  /// Upload file to S3 using multipart
  Future<String> _uploadToS3Multipart({
    required Uint8List fileBytes,
    required String filename,
    required Function(double) onProgress,
  }) async {
    // Step 1: Start multipart upload
    final startResponse = await http.post(
      Uri.parse('$baseUrl/uploads/multipart/start'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'filename': filename,
        'folder': 'raw',
      }),
    );

    if (startResponse.statusCode != 200) {
      throw Exception('Failed to start upload: ${startResponse.body}');
    }

    final startData = jsonDecode(startResponse.body);
    final String key = startData['key'];
    final String uploadId = startData['upload_id'];
    final int partSize = startData['part_size'];

    print('[Multipart] Started. Parts: ${(fileBytes.length / partSize).ceil()}');

    // Step 2: Upload parts
    final List<Map<String, dynamic>> uploadedParts = [];
    final int totalParts = (fileBytes.length / partSize).ceil();
    
    for (int i = 0; i < totalParts; i++) {
      final partNumber = i + 1;
      final start = i * partSize;
      final end = (start + partSize > fileBytes.length) ? fileBytes.length : start + partSize;
      final partBytes = fileBytes.sublist(start, end);

      print('[Multipart] Uploading part $partNumber/$totalParts');

      // Get presigned URL for this part
      final partUrlResponse = await http.post(
        Uri.parse('$baseUrl/uploads/multipart/part-url'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'key': key,
          'upload_id': uploadId,
          'part_number': partNumber,
          'ttl_seconds': 7200, // 2 hours
        }),
      );

      if (partUrlResponse.statusCode != 200) {
        throw Exception('Failed to get part URL: ${partUrlResponse.body}');
      }

      final partUrlData = jsonDecode(partUrlResponse.body);
      final String partUrl = partUrlData['url'];

      // Upload the part with retry logic
      String? etag;
      int retries = 3;
      while (retries > 0) {
        try {
          final uploadResponse = await http.put(
            Uri.parse(partUrl),
            body: partBytes,
          ).timeout(const Duration(minutes: 5));

          if (uploadResponse.statusCode == 200) {
            etag = uploadResponse.headers['etag'] ?? uploadResponse.headers['ETag'];
            if (etag != null) {
              etag = etag.replaceAll('"', ''); // Remove quotes
            }
            break;
          } else {
            throw Exception('Upload returned ${uploadResponse.statusCode}');
          }
        } catch (e) {
          retries--;
          if (retries == 0) rethrow;
          print('[Multipart] Retry part $partNumber (${retries} left): $e');
          await Future.delayed(Duration(seconds: 2));
        }
      }

      if (etag == null || etag.isEmpty) {
        throw Exception('Failed to get ETag for part $partNumber');
      }

      uploadedParts.add({
        'PartNumber': partNumber,
        'ETag': etag,
      });

      // Update progress
      onProgress((partNumber / totalParts) * 100);
    }

    print('[Multipart] All parts uploaded. Completing...');

    // Step 3: Complete multipart upload
    final completeResponse = await http.post(
      Uri.parse('$baseUrl/uploads/multipart/complete'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'key': key,
        'upload_id': uploadId,
        'parts': uploadedParts,
      }),
    );

    if (completeResponse.statusCode != 200) {
      throw Exception('Failed to complete upload: ${completeResponse.body}');
    }

    final completeData = jsonDecode(completeResponse.body);
    final String publicUrl = completeData['public_url'];

    print('[Multipart] Complete! URL: $publicUrl');
    return publicUrl;
  }

  /// Create meeting from S3 URL (you'll need to add this endpoint to your backend)
  Future<int> _createMeetingFromUrl({
    required String title,
    required String fileUrl,
    required String filename,
    String? email,
    String? language,
    String? hints,
    required bool transcribeOnly,
  }) async {
    final endpoint = transcribeOnly 
        ? '/meetings/create-from-url-transcribe-only'
        : '/meetings/create-from-url';

    final uri = Uri.parse('$baseUrl$endpoint');

    final headers = <String, String>{
      'Content-Type': 'application/json',
    };
    
    if (_licenseKey != null) {
      headers['X-License-Key'] = _licenseKey!;
    }

    final body = jsonEncode({
      'title': title,
      'file_url': fileUrl,
      'filename': filename,
      if (email != null && email.isNotEmpty) 'email_to': email,
      if (language != null && language.isNotEmpty) 'language': language,
      if (hints != null && hints.isNotEmpty) 'hints': hints,
    });

    final response = await http.post(
      uri,
      headers: headers,
      body: body,
    ).timeout(const Duration(seconds: 30));

    if (response.statusCode == 200 || response.statusCode == 201) {
      final data = jsonDecode(response.body);
      return data['id'] as int;
    } else if (response.statusCode == 429) {
      throw Exception('Monthly meeting limit reached');
    } else {
      throw Exception('Failed to create meeting: ${response.body}');
    }
  }

  Future<int> submitTranscript({
    required String title,
    required String transcript,
    String? email,
  }) async {
    print('[ApiService] Submitting transcript for: $title');

    final uri = Uri.parse('$baseUrl/meetings/from-text');
    final request = http.MultipartRequest('POST', uri);

    if (_licenseKey != null) {
      request.headers['X-License-Key'] = _licenseKey!;
    }

    request.fields['title'] = title;
    request.fields['transcript'] = transcript;
    if (email != null && email.isNotEmpty) {
      request.fields['email_to'] = email;
    }

    try {
      final streamedResponse = await request.send()
          .timeout(const Duration(minutes: 2));
      final response = await http.Response.fromStream(streamedResponse);

      if (response.statusCode == 200 || response.statusCode == 201) {
        final data = jsonDecode(response.body);
        return data['id'] as int;
      } else if (response.statusCode == 429) {
        throw Exception('Monthly meeting limit reached');
      } else {
        throw Exception('Submission failed: ${response.body}');
      }
    } catch (e) {
      print('[ApiService] Error: $e');
      rethrow;
    }
  }

  Future<Map<String, dynamic>> getMeetingStatus(int meetingId) async {
    final uri = Uri.parse('$baseUrl/meetings/$meetingId/status');
    final response = await http.get(uri).timeout(const Duration(seconds: 10));

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to fetch status');
    }
  }

  Future<List<Map<String, dynamic>>> getMeetings() async {
    final uri = Uri.parse('$baseUrl/meetings/list');
    final response = await http.get(uri).timeout(const Duration(seconds: 10));

    if (response.statusCode == 200) {
      final List data = jsonDecode(response.body);
      return data.cast<Map<String, dynamic>>();
    } else {
      throw Exception('Failed to fetch meetings');
    }
  }

  Future<Map<String, dynamic>> getSummary(int meetingId) async {
    final uri = Uri.parse('$baseUrl/meetings/$meetingId/summary');
    final response = await http.get(uri).timeout(const Duration(seconds: 10));

    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Summary not available');
    }
  }
}
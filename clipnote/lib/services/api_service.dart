// lib/services/api_service.dart
import 'dart:convert';
import 'package:flutter/material.dart';
import 'dart:io';
import 'dart:typed_data';
import 'package:path_provider/path_provider.dart' as pp;
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

Future<int> uploadMedia({
  required File file,
  required String title,
  required String fileType, // "audio" or "video"
  String? email,
  String? language,
  String? hints,
}) async {
  try {
    // Get license info to determine tier
    final licenseInfo = await getLicenseInfo();
    final tier = licenseInfo['tier'] as String? ?? 'free';
    
    print('[ApiService] 📤 Uploading $fileType for tier: $tier');
    
    // Check if video is allowed
    if (fileType == 'video' && tier != 'business') {
      throw Exception(
        'Video processing requires Business plan. '
        'Professional plan supports audio only.'
      );
    }
    
    // Professional/Business: Use presigned URL workflow
    if (tier == 'professional' || tier == 'business') {
      return await _uploadToB2(
        file: file,
        title: title,
        fileType: fileType,
        email: email,
        language: language,
        hints: hints,
      );
    } 
    // Free/Starter: Direct server upload
    else {
      return await _uploadToServer(
        file: file,
        title: title,
        fileType: fileType,
        email: email,
        language: language,
        hints: hints,
      );
    }
  } catch (e) {
    print('[ApiService] ❌ Upload error: $e');
    rethrow;
  }
}

/// Upload directly to server (Free/Starter tiers)
/// Files are processed then deleted - content saved to device
Future<int> _uploadToServer({
  required File file,
  required String title,
  required String fileType,
  String? email,
  String? language,
  String? hints,
}) async {
  print('[ApiService] 📤 Uploading $fileType to server (Free/Starter)...');
  
  final uri = Uri.parse('$baseUrl/meetings/upload');
  var request = http.MultipartRequest('POST', uri);
  
  // Add license key header if available
  if (_licenseKey != null) {
    request.headers['X-License-Key'] = _licenseKey!;
  }
  
  // Add fields
  request.fields['title'] = title;
  request.fields['file_type'] = fileType;
  if (email != null) request.fields['email_to'] = email;
  if (language != null) request.fields['language'] = language;
  if (hints != null) request.fields['hints'] = hints;
  
  // Add file
  final fileBytes = await file.readAsBytes();
  final filename = file.path.split('/').last;
  request.files.add(
    http.MultipartFile.fromBytes(
      'file',
      fileBytes,
      filename: filename,
    ),
  );
  
  final streamedResponse = await request.send();
  final response = await http.Response.fromStream(streamedResponse);
  
  if (response.statusCode == 200) {
    final data = jsonDecode(response.body);
    final meetingId = data['id'] as int;
    print('[ApiService] ✅ Server upload complete: Meeting ID $meetingId');
    print('[ApiService] ℹ️  ${data['note']}');
    
    // Start polling for completion (Free/Starter needs to download to device)
    _startPollingForCompletion(meetingId);
    
    return meetingId;
  } else {
    throw Exception('Upload failed: ${response.body}');
  }
}

/// Poll for meeting completion and auto-download (Free/Starter only)
Future<void> _startPollingForCompletion(int meetingId) async {
  final licenseInfo = await getLicenseInfo();
  final tier = licenseInfo['tier'] as String? ?? 'free';
  
  // Only auto-download for Free/Starter
  if (tier != 'free' && tier != 'starter') return;
  
  print('[ApiService] 🔄 Starting auto-download polling for meeting $meetingId');
  
  // Poll every 5 seconds for up to 10 minutes
  for (int i = 0; i < 120; i++) {
    await Future.delayed(Duration(seconds: 5));
    
    try {
      final status = await getMeetingStatus(meetingId);
      
      if (status['status'] == 'delivered') {
        print('[ApiService] ✅ Meeting completed, downloading to device...');
        await downloadAndSaveToDevice(meetingId);
        break;
      } else if (status['status'] == 'failed') {
        print('[ApiService] ❌ Meeting processing failed');
        break;
      }
    } catch (e) {
      print('[ApiService] ⚠️ Polling error: $e');
    }
  }
}

/// Download meeting content and save to device (Free/Starter)
/// Also works for Pro/Business but they're already in cloud
Future<void> downloadAndSaveToDevice(int meetingId) async {
  try {
    final licenseInfo = await getLicenseInfo();
    final tier = licenseInfo['tier'] as String? ?? 'free';
    
    print('[ApiService] 💾 Downloading meeting $meetingId content to device...');
    
    // Get meeting details
    final meeting = await getMeetingSummary(meetingId);
    final title = meeting['title'] ?? 'Meeting $meetingId';
    
    // Download transcript
    try {
      final transcriptUri = Uri.parse('$baseUrl/meetings/$meetingId/download?type=transcript');
      final transcriptResponse = await http.get(
        transcriptUri,
        headers: _getHeaders(),
      );
      
      if (transcriptResponse.statusCode == 200) {
        await _saveToDevice(
          'transcript_$meetingId.txt',
          transcriptResponse.bodyBytes,
          title,
        );
        print('[ApiService] ✅ Transcript saved to device');
      }
    } catch (e) {
      print('[ApiService] ⚠️ Transcript download failed: $e');
    }
    
    // Download summary
    try {
      final summaryUri = Uri.parse('$baseUrl/meetings/$meetingId/download?type=summary');
      final summaryResponse = await http.get(
        summaryUri,
        headers: _getHeaders(),
      );
      
      if (summaryResponse.statusCode == 200) {
        await _saveToDevice(
          'summary_$meetingId.txt',
          summaryResponse.bodyBytes,
          title,
        );
        print('[ApiService] ✅ Summary saved to device');
      }
    } catch (e) {
      print('[ApiService] ⚠️ Summary download failed: $e');
    }
    
    if (tier == 'free' || tier == 'starter') {
      print('[ApiService] ℹ️  Content saved to device. Server copies will be deleted after 48 hours.');
    }
    
  } catch (e) {
    print('[ApiService] ❌ Failed to download to device: $e');
    rethrow;
  }
}

/// Save content to device storage
Future<void> _saveToDevice(String filename, List<int> bytes, String title) async {
  try {
    // Get app documents directory
    Future<Directory> getApplicationDocumentsDirectory() => pp.getApplicationDocumentsDirectory();

    
    // Create meetings folder
    final meetingsDir = Directory('${directory.path}/meetings');
    if (!await meetingsDir.exists()) {
      await meetingsDir.create(recursive: true);
    }
    
    // Save file
    final file = File('${meetingsDir.path}/$filename');
    await file.writeAsBytes(bytes);
    
    print('[ApiService] 💾 Saved to device: ${file.path}');
  } catch (e) {
    print('[ApiService] ❌ Failed to save to device: $e');
    rethrow;
  }
}

/// Load meetings from device storage (Free/Starter)
Future<List<File>> getLocalMeetingFiles() async {
  try {
    final directory = await getApplicationDocumentsDirectory();
    final meetingsDir = Directory('${directory.path}/meetings');
    
    if (!await meetingsDir.exists()) {
      return [];
    }
    
    final files = await meetingsDir.list().toList();
    return files.whereType<File>().toList();
  } catch (e) {
    print('[ApiService] ❌ Failed to load local files: $e');
    return [];
  }
}

/// Upload to Backblaze B2 (Professional/Business tiers)
/// Files are uploaded to cloud, then deleted after processing
/// Transcripts and summaries retained in cloud permanently
Future<int> _uploadToB2({
  required File file,
  required String title,
  required String fileType,
  String? email,
  String? language,
  String? hints,
}) async {
  print('[ApiService] ☁️ Starting B2 upload workflow for $fileType...');
  
  try {
    // Step 1: Get presigned upload URL
    final filename = file.path.split('/').last;
    final contentType = _getContentType(filename);
    
    print('[ApiService] 📝 Requesting presigned URL for: $filename');
    
    final presignUri = Uri.parse('$baseUrl/storage/presign-upload');
    final presignResponse = await http.post(
      presignUri,
      headers: {
        'Content-Type': 'application/json',
        if (_licenseKey != null) 'X-License-Key': _licenseKey!,
      },
      body: jsonEncode({
        'filename': filename,
        'content_type': contentType,
        'file_type': fileType,
      }),
    );
    
    if (presignResponse.statusCode != 200) {
      throw Exception('Failed to get upload URL: ${presignResponse.body}');
    }
    
    final presignData = jsonDecode(presignResponse.body);
    final uploadUrl = presignData['upload_url'] as String;
    final key = presignData['key'] as String;
    
    print('[ApiService] ✅ Got presigned URL, uploading to B2...');
    
    // Step 2: Upload file directly to B2
    final fileBytes = await file.readAsBytes();
    final uploadResponse = await http.put(
      Uri.parse(uploadUrl),
      headers: {
        'Content-Type': contentType,
      },
      body: fileBytes,
    );
    
    if (uploadResponse.statusCode != 200 && uploadResponse.statusCode != 204) {
      throw Exception('B2 upload failed: ${uploadResponse.statusCode}');
    }
    
    print('[ApiService] ✅ B2 upload complete, confirming with server...');
    
    // Step 3: Confirm upload with backend
    final confirmUri = Uri.parse('$baseUrl/storage/confirm-upload');
    final confirmResponse = await http.post(
      confirmUri,
      headers: {
        'Content-Type': 'application/json',
        if (_licenseKey != null) 'X-License-Key': _licenseKey!,
      },
      body: jsonEncode({
        'key': key,
        'size_bytes': fileBytes.length,
        'title': title,
        'email_to': email,
        'language': language,
        'hints': hints,
        'file_type': fileType,
      }),
    );
    
    if (confirmResponse.statusCode != 200) {
      throw Exception('Failed to confirm upload: ${confirmResponse.body}');
    }
    
    final confirmData = jsonDecode(confirmResponse.body);
    final meetingId = confirmData['meeting_id'] as int;
    
    print('[ApiService] ✅ B2 upload workflow complete: Meeting ID $meetingId');
    print('[ApiService] ℹ️  ${confirmData['note']}');
    return meetingId;
    
  } catch (e) {
    print('[ApiService] ❌ B2 upload failed: $e');
    rethrow;
  }
}

/// Helper to determine content type from filename
String _getContentType(String filename) {
  final ext = filename.split('.').last.toLowerCase();
  switch (ext) {
    // Audio types
    case 'm4a':
      return 'audio/m4a';
    case 'mp3':
      return 'audio/mpeg';
    case 'wav':
      return 'audio/wav';
    case 'aac':
      return 'audio/aac';
    case 'ogg':
      return 'audio/ogg';
    case 'flac':
      return 'audio/flac';
    
    // Video types
    case 'mp4':
      return 'video/mp4';
    case 'mov':
      return 'video/quicktime';
    case 'mkv':
      return 'video/x-matroska';
    case 'webm':
      return 'video/webm';
    case 'avi':
      return 'video/x-msvideo';
    case 'm4v':
      return 'video/x-m4v';
    
    default:
      return 'application/octet-stream';
  }
}

/// Download meeting file
/// Free/Starter: Download from server (available 48h)
/// Pro/Business: Download from B2 cloud (always available)
Future<Map<String, dynamic>> downloadMeetingFile(
  int meetingId,
  String type,
) async {
  try {
    print('[ApiService] ⬇️ Preparing download for meeting $meetingId, type: $type');
    
    // Media downloads are not available for anyone
    if (type == 'audio' || type == 'video') {
      throw Exception(
        'Media files are not available for download. '
        'All audio and video files are automatically deleted after processing. '
        'Transcripts and summaries are retained.'
      );
    }
    
    // Valid types: transcript, summary, all
    if (!['transcript', 'summary', 'all'].contains(type)) {
      throw Exception('Invalid download type. Use: transcript, summary, or all');
    }
    
    // Construct the download URL
    final downloadUrl = '$baseUrl/meetings/$meetingId/download?type=$type';
    
    print('[ApiService] ⬇️ Download URL: $downloadUrl');
    
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
    case 'all':
      return 'meeting_${meetingId}_files.zip';
    default:
      return 'meeting_${meetingId}_download.txt';
  }
}

/// Check if user's tier supports video
Future<bool> canUploadVideo() async {
  final licenseInfo = await getLicenseInfo();
  final tier = licenseInfo['tier'] as String? ?? 'free';
  return tier == 'business';
}

/// Get user's current storage tier info
Future<Map<String, dynamic>> getStorageInfo() async {
  final licenseInfo = await getLicenseInfo();
  final tier = licenseInfo['tier'] as String? ?? 'free';
  
  bool hasCloudStorage = tier == 'professional' || tier == 'business';
  bool canRecordVideo = tier == 'business';
  bool saveToDevice = tier == 'free' || tier == 'starter';
  
  return {
    'tier': tier,
    'has_cloud_storage': hasCloudStorage,
    'can_record_video': canRecordVideo,
    'save_to_device': saveToDevice,
    'storage_location': hasCloudStorage 
        ? 'Cloud (Backblaze B2)' 
        : 'Your Device',
    'media_retention': 'Media files deleted after processing (all tiers)',
    'content_retention': hasCloudStorage 
        ? 'Transcripts & summaries stored permanently in cloud' 
        : 'Transcripts & summaries saved to your device',
    'supported_media': canRecordVideo ? 'Audio & Video' : 'Audio only',
    'server_retention': saveToDevice 
        ? 'Available on server for 48 hours, then deleted' 
        : 'Not applicable',
  };
}

/// Show storage info to user
Future<void> showStorageInfoDialog(BuildContext context) async {
  final storageInfo = await getStorageInfo();
  
  showDialog(
    context: context,
    builder: (context) => AlertDialog(
      title: Text('Storage: ${storageInfo['tier']}'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _infoRow('📁 Storage', storageInfo['storage_location']),
            SizedBox(height: 8),
            _infoRow('🎙️ Media Support', storageInfo['supported_media']),
            SizedBox(height: 8),
            _infoRow('📝 Content', storageInfo['content_retention']),
            SizedBox(height: 8),
            _infoRow('🗑️ Media Files', storageInfo['media_retention']),
            if (storageInfo['server_retention'] != 'Not applicable') ...[
              SizedBox(height: 8),
              _infoRow('⏱️ Server', storageInfo['server_retention']),
            ],
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: Text('Got it'),
        ),
        if (storageInfo['tier'] == 'free' || storageInfo['tier'] == 'starter')
          ElevatedButton(
            onPressed: () {
              Navigator.pop(context);
              // Navigate to upgrade
            },
            child: Text('Upgrade'),
          ),
      ],
    ),
  );
}

Widget _infoRow(String label, String value) {
  return Row(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(
        '$label: ',
        style: TextStyle(fontWeight: FontWeight.bold),
      ),
      Expanded(
        child: Text(value),
      ),
    ],
  );
}

/// Show upload options based on tier
Future<void> showUploadOptions(BuildContext context) async {
  final storageInfo = await getStorageInfo();
  final canVideo = storageInfo['can_record_video'] as bool;
  final saveToDevice = storageInfo['save_to_device'] as bool;
  
  showModalBottomSheet(
    context: context,
    builder: (context) => SafeArea(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Padding(
            padding: EdgeInsets.all(16),
            child: Text(
              'Record Meeting',
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
            ),
          ),
          if (saveToDevice)
            Padding(
              padding: EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Container(
                padding: EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.blue.shade50,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  children: [
                    Icon(Icons.info_outline, color: Colors.blue),
                    SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'Content auto-saved to your device after processing',
                        style: TextStyle(fontSize: 12),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ListTile(
            leading: Icon(Icons.mic, color: Colors.blue),
            title: Text('Record Audio'),
            subtitle: Text('Available for all plans'),
            onTap: () {
              Navigator.pop(context);
              // Navigate to audio recording
            },
          ),
          if (canVideo)
            ListTile(
              leading: Icon(Icons.videocam, color: Colors.red),
              title: Text('Record Video'),
              subtitle: Text('Business plan feature'),
              onTap: () {
                Navigator.pop(context);
                // Navigate to video recording
              },
            )
          else
            ListTile(
              leading: Icon(Icons.videocam, color: Colors.grey),
              title: Text('Record Video'),
              subtitle: Text('Requires Business plan'),
              trailing: ElevatedButton(
                onPressed: () {
                  Navigator.pop(context);
                  // Navigate to upgrade page
                },
                child: Text('Upgrade'),
              ),
              enabled: false,
            ),
          SizedBox(height: 16),
        ],
      ),
    ),
  );
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
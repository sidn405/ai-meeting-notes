import 'dart:io';
import 'dart:typed_data';
import 'package:dio/dio.dart';
import '../utils/constants.dart';

class PresignedUpload {
  final String putUrl;
  final String key;
  final String publicUrl;
  final Map<String, String> headers;

  PresignedUpload({
    required this.putUrl,
    required this.key,
    required this.publicUrl,
    required this.headers,
  });

  factory PresignedUpload.fromJson(Map<String, dynamic> json) {
    return PresignedUpload(
      putUrl: json['put_url'] as String,
      key: json['key'] as String,
      publicUrl: json['public_url'] as String,
      headers: Map<String, String>.from(json['headers'] ?? {}),
    );
  }
}

class ApiService {
  // Singleton pattern
  ApiService._();
  static final ApiService instance = ApiService._();

  final Dio _dio = Dio();
  String? _licenseKey;

  // Constructor-like initialization
  void initialize() {
    _dio.options.baseUrl = AppConstants.baseUrl;
    _dio.options.connectTimeout = const Duration(seconds: 30);
    _dio.options.receiveTimeout = const Duration(seconds: 30);
  }

  void setLicenseKey(String key) {
    _licenseKey = key;
  }

  Map<String, String> _getHeaders() {
    return {
      if (_licenseKey != null) 'X-API-Key': _licenseKey!,
      'Content-Type': 'application/json',
    };
  }

  // ========== NEW METHODS FOR UPLOAD_SCREEN ==========

  // Request presigned upload URL
  Future<PresignedUpload> presignUpload({
    required String filename,
    required String contentType,
  }) async {
    try {
      final response = await _dio.post(
        '/api/presign', // Adjust this endpoint to match your backend
        data: {
          'filename': filename,
          'content_type': contentType,
        },
        options: Options(headers: _getHeaders()),
      );
      return PresignedUpload.fromJson(response.data);
    } catch (e) {
      throw _handleError(e);
    }
  }

  // Upload bytes to presigned URL
  Future<void> putBytes({
    required String putUrl,
    required Uint8List bytes,
    required Map<String, String> headers,
  }) async {
    try {
      await _dio.put(
        putUrl,
        data: bytes,
        options: Options(
          headers: headers,
          contentType: headers['Content-Type'],
        ),
      );
    } catch (e) {
      throw _handleError(e);
    }
  }

  // Record asset in database
  Future<void> recordAsset({
    required String meetingId,
    required String s3Key,
    required String filename,
    required String type,
    required String contentType,
    required int sizeBytes,
  }) async {
    try {
      await _dio.post(
        '/api/record-asset', // Adjust this endpoint to match your backend
        data: {
          'meeting_id': meetingId,
          's3_key': s3Key,
          'filename': filename,
          'type': type,
          'content_type': contentType,
          'size_bytes': sizeBytes,
        },
        options: Options(headers: _getHeaders()),
      );
    } catch (e) {
      throw _handleError(e);
    }
  }

  // Start processing (transcribe/summarize)
  Future<void> startProcessing({
    required String meetingId,
    required String s3Key,
    required bool summarize,
  }) async {
    try {
      await _dio.post(
        '/api/process', // Adjust this endpoint to match your backend
        data: {
          'meeting_id': meetingId,
          's3_key': s3Key,
          'summarize': summarize,
        },
        options: Options(headers: _getHeaders()),
      );
    } catch (e) {
      throw _handleError(e);
    }
  }

  // Submit transcript directly (no audio)
  Future<void> submitTranscript({
    required String meetingId,
    required String transcript,
    required bool summarize,
  }) async {
    try {
      await _dio.post(
        '/api/submit-transcript', // Adjust this endpoint to match your backend
        data: {
          'meeting_id': meetingId,
          'transcript': transcript,
          'summarize': summarize,
        },
        options: Options(headers: _getHeaders()),
      );
    } catch (e) {
      throw _handleError(e);
    }
  }

  // ========== EXISTING METHODS ==========

  // Activate License
  Future<Map<String, dynamic>> activateLicense(String licenseKey) async {
    try {
      final response = await _dio.post(
        AppConstants.licenseActivateEndpoint,
        data: {'license_key': licenseKey},
      );
      return response.data;
    } catch (e) {
      throw _handleError(e);
    }
  }

  // Get License Info
  Future<Map<String, dynamic>> getLicenseInfo() async {
    try {
      final response = await _dio.get(
        AppConstants.licenseInfoEndpoint,
        options: Options(headers: _getHeaders()),
      );
      return response.data;
    } catch (e) {
      throw _handleError(e);
    }
  }

  // Upload Audio File
  Future<Map<String, dynamic>> uploadAudio({
    required File audioFile,
    required String title,
    String language = 'en',
    String? hints,
  }) async {
    try {
      final formData = FormData.fromMap({
        'file': await MultipartFile.fromFile(
          audioFile.path,
          filename: audioFile.path.split('/').last,
        ),
        'title': title,
        'language': language,
        if (hints != null) 'hints': hints,
      });

      final response = await _dio.post(
        AppConstants.uploadEndpoint,
        data: formData,
        options: Options(headers: _getHeaders()),
        onSendProgress: (sent, total) {
          print('Upload progress: ${(sent / total * 100).toStringAsFixed(0)}%');
        },
      );

      return response.data;
    } catch (e) {
      throw _handleError(e);
    }
  }

  // Get Meeting Status
  Future<Map<String, dynamic>> getMeetingStatus(int meetingId) async {
    try {
      final response = await _dio.get(
        '${AppConstants.meetingEndpoint}/$meetingId',
        options: Options(headers: _getHeaders()),
      );
      return response.data;
    } catch (e) {
      throw _handleError(e);
    }
  }

  // Get Meeting Summary
  Future<Map<String, dynamic>> getMeetingSummary(int meetingId) async {
    try {
      final response = await _dio.get(
        '${AppConstants.meetingEndpoint}/$meetingId/summary',
        options: Options(headers: _getHeaders()),
      );
      return response.data;
    } catch (e) {
      throw _handleError(e);
    }
  }

  // Get Meeting List
  Future<List<dynamic>> getMeetingsList() async {
    try {
      final response = await _dio.get(
        '${AppConstants.meetingEndpoint}/list',
        options: Options(headers: _getHeaders()),
      );
      return response.data;
    } catch (e) {
      throw _handleError(e);
    }
  }

  String _handleError(dynamic error) {
    if (error is DioException) {
      if (error.response != null) {
        final data = error.response?.data;
        if (data is Map && data.containsKey('detail')) {
          return data['detail'].toString();
        }
        return 'Server error: ${error.response?.statusCode}';
      }
      return 'Network error: ${error.message}';
    }
    return error.toString();
  }
}
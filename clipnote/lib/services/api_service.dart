import 'dart:io';
import 'dio/dio.dart';
import '../utils/constants.dart';

class ApiService {
  final Dio _dio = Dio();
  String? _licenseKey;

  ApiService() {
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
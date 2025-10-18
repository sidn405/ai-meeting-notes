// lib/services/api_service.dart
import 'dart:typed_data';
import 'package:dio/dio.dart';

/// TODO: update if your base changes
const API_BASE = 'https://ai-meeting-notes-production-81d7.up.railway.app';

class PresignResponse {
  final String url;                        // PUT URL to B2/S3
  final String key;                        // object key, e.g. raw/...m4a
  final String? publicUrl;                 // optional public URL
  final String method;                     // usually 'PUT'
  final Map<String, String> headers;       // exact headers required by the PUT

  PresignResponse({
    required this.url,
    required this.key,
    required this.method,
    required this.headers,
    this.publicUrl,
  });
}

class ApiService {
  final Dio _dio = Dio(BaseOptions(
    baseUrl: API_BASE,
    connectTimeout: const Duration(seconds: 20),
    receiveTimeout: const Duration(minutes: 2),
  ));

  String? _apiKey; // X-API-Key (license)

  // Called by Activation screen or after web purchase
  void setLicenseKey(String key) {
    _apiKey = key;
  }

  Map<String, String> _authHeaders() {
    final key = _apiKey; // snapshot for promotion
    return (key != null && key.isNotEmpty) ? {'X-API-Key': key} : const {};
  }

  /// ----- LICENSE / IAP -----

  Future<Map<String, dynamic>> getLicenseInfo() async {
    final res = await _dio.get(
      '/license/info',
      options: Options(headers: _authHeaders()),
    );
    return (res.data as Map).cast<String, dynamic>();
  }

  Future<void> activateLicense(String licenseKey) async {
    await _dio.post(
      '/license/activate',
      data: {'license_key': licenseKey},
      options: Options(headers: _authHeaders()),
    );
    _apiKey = licenseKey;
  }

  Future<void> verifyIapReceipt({
    required String store, // 'google_play' | 'app_store'
    required String receipt,
  }) async {
    await _dio.post(
      '/iap/verify',
      data: {'store': store, 'receipt': receipt},
      options: Options(headers: _authHeaders()),
    );
  }

  /// ----- UPLOAD FLOW -----

  Future<PresignResponse> presignUpload({
    required String filename,
    required String contentType,
    required String folder, // e.g., 'raw'
  }) async {
    final res = await _dio.post(
      '/uploads/presign',
      data: {
        'filename': filename,
        'content_type': contentType,
        'folder': folder,
      },
      options: Options(headers: _authHeaders()),
    );

    final m = (res.data as Map).cast<String, dynamic>();
    final headersAny = (m['headers'] as Map?) ?? const {};
    final headers = headersAny.map(
      (k, v) => MapEntry(k.toString(), v.toString()),
    );

    return PresignResponse(
      url: m['url'] as String,
      key: m['key'] as String,
      publicUrl: m['public_url'] as String?,
      method: (m['method'] as String?) ?? 'PUT',
      headers: headers,
    );
  }

  Future<void> recordAsset({
    required String meetingId,
    required String key,  // Changed from s3Key to key
    String? publicUrl,
  }) async {
    await _dio.post(
      '/uploads/record',
      data: {
        'meeting_id': meetingId,
        's3key': key,
        'public_url': publicUrl,
      },
      options: Options(headers: _authHeaders()),
    );
  }

  /// Start transcription/summarization for an uploaded object
  Future<void> startProcessing({
    required String meetingId,
    required String s3key,  // Changed from s3Key to s3key to match caller
    required String mode,   // Changed from bool summarize to String mode
  }) async {
    await _dio.post(
      '/process/start',
      data: {
        'meeting_id': meetingId,
        's3key': s3key,
        'mode': mode,
      },
      options: Options(headers: _authHeaders()),
    );
  }

  /// Direct transcript submission (no audio)
  Future<void> submitTranscript({
    required String meetingId,
    String? title,  // Added title parameter
    required String transcript,
    required bool summarize,
  }) async {
    await _dio.post(
      '/process/from_transcript',
      data: {
        'meeting_id': meetingId,
        if (title != null) 'title': title,
        'transcript': transcript,
        'summarize': summarize,
      },
      options: Options(headers: _authHeaders()),
    );
  }

  /// PUT bytes to presigned storage URL (NO auth headers here!)
  Future<Response> putBytes({
    required String url,
    required Uint8List bytes,
    Map<String, String>? headers,
    String method = 'PUT',
  }) {
    final client = Dio();
    return client.request(
      url,
      data: bytes,
      options: Options(method: method, headers: headers),
    );
  }

  // --- Singleton convenience (keep both to satisfy older calls) ---
  static final ApiService I = ApiService();
  static ApiService get instance => I;

  // --- Meeting status + summary used by Progress/Results screens ---
  Future<Map<String, dynamic>> getMeetingStatus(String meetingId) async {
    final r = await _dio.get(
      '/meetings/$meetingId/status',
      options: Options(headers: _authHeaders()),
    );
    return (r.data as Map).cast<String, dynamic>();
  }

  Future<Map<String, dynamic>> getMeetingSummary(String meetingId) async {
    final r = await _dio.get(
      '/meetings/$meetingId/summary',
      options: Options(headers: _authHeaders()),
    );
    return (r.data as Map).cast<String, dynamic>();
  }
}
// lib/services/api_service.dart
import 'dart:convert';
import 'dart:typed_data';
import 'package:dio/dio.dart';

/// Top-level type for presign responses (can't live inside a class in Dart)
class PresignResponse {
  PresignResponse({
    required this.putUrl,
    required this.key,
    required this.headers,
    this.publicUrl,
  });

  final String putUrl;
  final String key;
  final Map<String, String> headers;
  final String? publicUrl;
}

class ApiService {
  ApiService() {
    // Add auth header only for OUR API host (not for presigned URLs).
    _dio.interceptors.add(
      InterceptorsWrapper(onRequest: (options, handler) {
        if (_shouldAuth(options.uri)) {
          if (_apiKey != null && _apiKey!.isNotEmpty) {
            options.headers['X-API-Key'] = _apiKey!;
          }
          // If your backend expects license as a header (instead of body), uncomment:
          // if (_licenseKey?.isNotEmpty == true) {
          //   options.headers['X-License-Key'] = _licenseKey!;
          // }
        }
        handler.next(options);
      }),
    );
  }

  // ========= Config =========
  static const String baseUrl =
      "https://ai-meeting-notes-production-81d7.up.railway.app";

  final Dio _dio = Dio(
    BaseOptions(
      connectTimeout: const Duration(seconds: 30),
      receiveTimeout: const Duration(seconds: 60),
    ),
  );

  String? _apiKey;     // for X-API-Key
  String? _licenseKey; // optional (we pass in POST body by default)

  /// Optional convenience to set both in one call.
  void configureAuth({String? apiKey, String? licenseKey}) {
    if (apiKey != null) _apiKey = apiKey;
    if (licenseKey != null) _licenseKey = licenseKey;
  }

  /// Matches existing app usage: set license only.
  void setLicenseKey(String? licenseKey) {
    _licenseKey = licenseKey;
  }

  bool _shouldAuth(Uri uri) => uri.host == Uri.parse(baseUrl).host;

  // ========= API Calls =========

  /// (1) Ask server for a presigned URL
  Future<PresignResponse> presignUpload({
    required String filename,
    required String contentType,
    String folder = "raw",
  }) async {
    final r = await _dio.post(
      "$baseUrl/uploads/presign",
      data: {
        "filename": filename,
        "content_type": contentType,
        "folder": folder,
      },
      options: Options(headers: {"Content-Type": "application/json"}),
    );

    final data = r.data is Map ? r.data : jsonDecode(r.data as String);
    final headersDynamic = Map<String, dynamic>.from(data["headers"] ?? const {});
    final headers = headersDynamic.map((k, v) => MapEntry(k, "$v"));

    return PresignResponse(
      putUrl: data["url"] as String,
      key: data["key"] as String,
      publicUrl: data["public_url"] as String?,
      headers: headers,
    );
    // NOTE: Do NOT attach X-API-Key to the returned PUT URL; that's for S3/B2 only.
  }

  /// (2) Upload bytes to the presigned URL (no custom auth headers here)
  Future<void> putBytes({
    required String putUrl,
    required Uint8List bytes,
    required Map<String, String> headers,
  }) async {
    final hdrs = Map<String, String>.from(headers);
    hdrs.putIfAbsent('Content-Length', () => bytes.length.toString());

    await _dio.put(
      putUrl,
      data: bytes, // fixed-length body (Backblaze-friendly)
      options: Options(
        headers: hdrs,
        contentType: headers['Content-Type'],
      ),
    );
  }

  /// (3) Record asset (DB) after upload
  Future<void> recordAsset({
    required String meetingId,
    required String s3Key,
    required String filename,
    required String type, // "audio" | "video"
    String? contentType,
    int? sizeBytes,
    int? durationMs,
  }) async {
    await _dio.post(
      "$baseUrl/meetings/$meetingId/assets",
      data: {
        "s3_key": s3Key,
        "filename": filename,
        "type": type,
        "content_type": contentType,
        "size_bytes": sizeBytes,
        "duration_ms": durationMs,
        // If your backend expects the license in BODY, keep this:
        if (_licenseKey?.isNotEmpty == true) "license_key": _licenseKey,
      },
      options: Options(headers: {"Content-Type": "application/json"}),
    );
  }

  /// (4) Start processing (transcribe / transcribe+summarize)
  /// If your real route is `/meetings/{id}/upload_sync`, change the path below.
  Future<void> startProcessing({
    required String meetingId,
    required String s3Key,
    required bool summarize,
  }) async {
    await _dio.post(
      "$baseUrl/meetings/$meetingId/process",
      data: {
        "s3_key": s3Key,
        "mode": summarize ? "transcribe_summarize" : "transcribe_only",
        if (_licenseKey?.isNotEmpty == true) "license_key": _licenseKey,
      },
      options: Options(headers: {"Content-Type": "application/json"}),
    );
  }

  /// (5) Transcript-only path (no audio file)
  Future<void> submitTranscript({
    required String meetingId,
    required String transcript,
    required bool summarize,
  }) async {
    await _dio.post(
      "$baseUrl/meetings/$meetingId/transcripts",
      data: {
        "transcript": transcript,
        "mode": summarize ? "transcribe_summarize" : "transcribe_only",
        if (_licenseKey?.isNotEmpty == true) "license_key": _licenseKey,
      },
      options: Options(headers: {"Content-Type": "application/json"}),
    );
  }

  /// (6) License info helper to satisfy existing calls in main/home/activation.
  /// We don't know your exact endpoint; try a couple common ones gracefully.
  Future<Map<String, dynamic>> getLicenseInfo() async {
    Response r;
    try {
      r = await _dio.get("$baseUrl/license",
          options: Options(headers: {"Accept": "application/json"}));
    } on DioException catch (_) {
      // fallback route name
      r = await _dio.get("$baseUrl/licenses/me",
          options: Options(headers: {"Accept": "application/json"}));
    }
    final data = r.data;
    if (data is Map<String, dynamic>) return data;
    if (data is String && data.isNotEmpty) {
      try {
        return jsonDecode(data) as Map<String, dynamic>;
      } catch (_) {/* ignore */}
    }
    return <String, dynamic>{};
  }
}

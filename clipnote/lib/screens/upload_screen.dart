// lib/services/api_service.dart
import 'dart:convert';
import 'dart:typed_data';
import 'package:dio/dio.dart';

class ApiService {
  ApiService._() {
    // Attach an interceptor that only adds auth headers to OUR API, not S3/B2.
    _dio.interceptors.add(
      InterceptorsWrapper(onRequest: (options, handler) {
        if (_shouldAuth(options.uri)) {
          if (_apiKey != null && _apiKey!.isNotEmpty) {
            options.headers['X-API-Key'] = _apiKey!;
          }
          // If your backend wants license in a HEADER instead, uncomment:
          // if (_licenseKey != null && _licenseKey!.isNotEmpty) {
          //   options.headers['X-License-Key'] = _licenseKey!;
          // }
        }
        handler.next(options);
      }),
    );
  }

  static final ApiService instance = ApiService._();

  /// Your API base (same as the app uses everywhere)
  static const String baseUrl =
      "https://ai-meeting-notes-production-81d7.up.railway.app";

  final Dio _dio = Dio(
    BaseOptions(
      connectTimeout: const Duration(seconds: 30),
      receiveTimeout: const Duration(seconds: 60),
    ),
  );

  String? _apiKey;     // value for X-API-Key
  String? _licenseKey; // optional

  /// Call this once (e.g., on app start or after user enters keys)
  void configureAuth({required String apiKey, String? licenseKey}) {
    _apiKey = apiKey;
    _licenseKey = licenseKey;
  }

  bool _shouldAuth(Uri uri) {
    // Only attach X-API-Key to requests going to YOUR API host.
    // S3/B2 presigned URLs MUST NOT receive your custom headers.
    return uri.host == Uri.parse(baseUrl).host;
  }

  // ---------- Upload presign ----------
  Future<({String putUrl, String key, String? publicUrl, Map<String, String> headers})>
      presignUpload({
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
    return (
      putUrl: data["url"] as String,
      key: data["key"] as String,
      publicUrl: data["public_url"] as String?,
      headers: Map<String, dynamic>.from(data["headers"] ?? {})
          .map((k, v) => MapEntry(k, "$v")),
    );
  }

  // ---------- Upload actual bytes to S3/B2 ----------
  Future<void> putBytes({
    required String putUrl,
    required Uint8List bytes,
    required Map<String, String> headers,
  }) async {
    // DO NOT add X-API-Key here; this is a presigned S3/B2 URL.
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

  // ---------- Record asset in DB (protected) ----------
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
        // If your backend requires license in BODY, keep this:
        if (_licenseKey != null && _licenseKey!.isNotEmpty) "license_key": _licenseKey,
      },
      options: Options(headers: {"Content-Type": "application/json"}),
    );
  }

  // ---------- Start processing (protected) ----------
  // If your real route is /meetings/{id}/upload_sync, change it here.
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
        if (_licenseKey != null && _licenseKey!.isNotEmpty) "license_key": _licenseKey,
      },
      options: Options(headers: {"Content-Type": "application/json"}),
    );
  }

  // ---------- Transcript-only (protected) ----------
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
        if (_licenseKey != null && _licenseKey!.isNotEmpty) "license_key": _licenseKey,
      },
      options: Options(headers: {"Content-Type": "application/json"}),
    );
  }
}

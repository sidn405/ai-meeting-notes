import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class BannerService {
  static final BannerService _instance = BannerService._internal();
  factory BannerService() => _instance;
  BannerService._internal();
  
  static BannerService get I => _instance;
  
  List<BannerAd> _banners = [];
  DateTime? _lastFetch;
  static const _cacheDuration = Duration(hours: 1); // Cache banners for 1 hour
  
  // CHANGE THIS to your actual API endpoint
  static const String _apiBaseUrl = 'https://ai-meeting-notes-production-81d7.up.railway.app';
  
  Future<void> init() async {
    await _loadBanners();
  }
  
  Future<void> _loadBanners() async {
    // Try to load from cache first
    await _loadCachedBanners();
    
    // If cache is expired or empty, fetch from server
    if (_shouldFetchFromServer()) {
      try {
        await _fetchBannersFromServer();
      } catch (e) {
        print('⚠️ Failed to fetch banners from server: $e');
        // Fall back to hardcoded banners if server fails
        if (_banners.isEmpty) {
          _loadHardcodedBanners();
        }
      }
    }
    
    // If still no banners, load hardcoded ones
    if (_banners.isEmpty) {
      _loadHardcodedBanners();
    }
  }
  
  bool _shouldFetchFromServer() {
    if (_lastFetch == null) return true;
    return DateTime.now().difference(_lastFetch!) > _cacheDuration;
  }
  
  Future<void> _fetchBannersFromServer() async {
    print('🌐 Fetching banners from server...');
    
    final response = await http.get(
      Uri.parse('$_apiBaseUrl/api/banners'),
      headers: {'Content-Type': 'application/json'},
    ).timeout(const Duration(seconds: 10));
    
    if (response.statusCode == 200) {
      final List<dynamic> data = jsonDecode(response.body);
      _banners = data.map((json) => BannerAd.fromJson(json)).toList();
      _lastFetch = DateTime.now();
      
      // Cache the banners locally
      await _cacheBanners();
      
      print('✅ Loaded ${_banners.length} banners from server');
    } else {
      throw Exception('Failed to load banners: ${response.statusCode}');
    }
  }
  
  Future<void> _cacheBanners() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final bannersJson = _banners.map((b) => b.toJson()).toList();
      await prefs.setString('cached_banners', jsonEncode(bannersJson));
      await prefs.setString('banners_last_fetch', DateTime.now().toIso8601String());
    } catch (e) {
      print('Error caching banners: $e');
    }
  }
  
  Future<void> _loadCachedBanners() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final cachedBannersJson = prefs.getString('cached_banners');
      final lastFetchStr = prefs.getString('banners_last_fetch');
      
      if (cachedBannersJson != null && lastFetchStr != null) {
        final List<dynamic> data = jsonDecode(cachedBannersJson);
        _banners = data.map((json) => BannerAd.fromJson(json)).toList();
        _lastFetch = DateTime.parse(lastFetchStr);
        print('📦 Loaded ${_banners.length} banners from cache');
      }
    } catch (e) {
      print('Error loading cached banners: $e');
    }
  }
  
  void _loadHardcodedBanners() {
    print('📱 Loading hardcoded banners as fallback');
    // Hardcoded banners from assets folder (fallback)
    _banners = [
      BannerAd(
        id: 'banner_001',
        imageUrl: 'assets/banners/banner1.png',
        clickUrl: 'https://villiersjetcom/?id=7275',
        title: 'Product 1',
        weight: 10,
        isLocal: true,
      ),
      BannerAd(
        id: 'banner_002',
        imageUrl: 'assets/banners/banner2.png',
        clickUrl: 'https://villiersjetcom/?id=7275',
        title: 'Product 2',
        weight: 5,
        isLocal: true,
      ),
      BannerAd(
        id: 'banner_003',
        imageUrl: 'assets/banners/banner3.png',
        clickUrl: 'https://villiersjetcom/?id=7275',
        title: 'Product 3',
        weight: 15,
        isLocal: true,
      ),
      BannerAd(
        id: 'banner_004',
        imageUrl: 'assets/banners/banner4.png',
        clickUrl: 'https://villiersjetcom/?id=7275',
        title: 'Product 4',
        weight: 8,
        isLocal: true,
      ),
      BannerAd(
        id: 'banner_005',
        imageUrl: 'assets/banners/banner5.png',
        clickUrl: 'https://villiersjetcom/?id=7275',
        title: 'Product 5',
        weight: 8,
        isLocal: true,
      ),
      BannerAd(
        id: 'banner_006',
        imageUrl: 'assets/banners/banner6.png',
        clickUrl: 'https://villiersjetcom/?id=7275',
        title: 'Product 6',
        weight: 15,
        isLocal: true,
      ),
    ];
  }
  
  BannerAd? getRandomBanner() {
    if (_banners.isEmpty) return null;
    
    // Weighted random selection
    final totalWeight = _banners.fold<int>(0, (sum, banner) => sum + banner.weight);
    var random = (DateTime.now().millisecondsSinceEpoch % totalWeight);
    
    for (final banner in _banners) {
      if (random < banner.weight) {
        return banner;
      }
      random -= banner.weight;
    }
    
    return _banners.first;
  }
  
  List<BannerAd> getAllBanners() => List.unmodifiable(_banners);
  
  // Force refresh from server
  Future<void> refresh() async {
    _lastFetch = null;
    await _loadBanners();
  }
  
  Future<void> recordClick(String bannerId) async {
    print('🖱️ Banner clicked: $bannerId');
    
    try {
      await http.post(
        Uri.parse('$_apiBaseUrl/api/banners/click'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'banner_id': bannerId}),
      ).timeout(const Duration(seconds: 5));
    } catch (e) {
      print('Error recording click: $e');
    }
  }
  
  Future<void> recordImpression(String bannerId) async {
    print('👁️ Banner impression: $bannerId');
    
    try {
      await http.post(
        Uri.parse('$_apiBaseUrl/api/banners/impression'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'banner_id': bannerId}),
      ).timeout(const Duration(seconds: 5));
    } catch (e) {
      print('Error recording impression: $e');
    }
  }
}

class BannerAd {
  final String id;
  final String imageUrl;
  final String clickUrl;
  final String title;
  final int weight;
  final bool isLocal; // true if using local asset, false if network image
  
  BannerAd({
    required this.id,
    required this.imageUrl,
    required this.clickUrl,
    required this.title,
    this.weight = 1,
    this.isLocal = false,
  });
  
  factory BannerAd.fromJson(Map<String, dynamic> json) {
    return BannerAd(
      id: json['id'] as String,
      imageUrl: json['image_url'] as String,
      clickUrl: json['click_url'] as String,
      title: json['title'] as String? ?? '',
      weight: json['weight'] as int? ?? 1,
      isLocal: json['is_local'] as bool? ?? false,
    );
  }
  
  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'image_url': imageUrl,
      'click_url': clickUrl,
      'title': title,
      'weight': weight,
      'is_local': isLocal,
    };
  }
}
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'dart:math';

// Keep UI-agnostic: define our own enum instead of Flutter's Orientation
enum BannerOrientation { portrait, landscape }

class BannerService {
  static final BannerService _instance = BannerService._internal();
  factory BannerService() => _instance;
  BannerService._internal();
  
  static BannerService get I => _instance;
  
  List<BannerAd> _banners = [];
  
  // Your Railway API URL - used only for analytics
  static const String _apiBaseUrl = 'https://ai-meeting-notes-production-81d7.up.railway.app';
  
  Future<void> init() async {
    _loadLocalBanners();
  }
  
  void _loadLocalBanners() {
    _banners = [
      BannerAd(
        id: 'banner_001',
        imageUrl: 'assets/banners/banner1.png',
        clickUrl: 'https://villiersjets.com/?id=7275',
        title: 'Product 1',
        weight: 10,
        isLocal: true,
      ),
      BannerAd(
        id: 'banner_002',
        imageUrl: 'assets/banners/banner2.png',
        clickUrl: 'https://villiersjets.com/?id=7275',
        title: 'Product 2',
        weight: 5,
        isLocal: true,
      ),
      BannerAd(
        id: 'banner_003',
        imageUrl: 'assets/banners/banner3.png',
        clickUrl: 'https://villiersjets.com/?id=7275',
        title: 'Product 3',
        weight: 15,
        isLocal: true,
      ),
      BannerAd(
        id: 'banner_004',
        imageUrl: 'assets/banners/banner4.png',
        clickUrl: 'https://villiersjets.com/?id=7275',
        title: 'Product 4',
        weight: 8,
        isLocal: true,
      ),
      BannerAd(
        id: 'banner_005',
        imageUrl: 'assets/banners/banner5.png',
        clickUrl: 'https://villiersjets.com/?id=7275',
        title: 'Product 5',
        weight: 8,
        isLocal: true,
      ),
      BannerAd(
        id: 'banner_006',
        imageUrl: 'assets/banners/banner6.png',
        clickUrl: 'https://villiersjets.com/?id=7275',
        title: 'Product 6',
        weight: 15,
        isLocal: true,
      ),
      BannerAd(
        id: 'banner_0p1',
        imageUrl: 'assets/banners/p1.png',
        clickUrl: 'https://villiersjets.com/?id=7275',
        title: 'Product p1',
        weight: 10,
        isLocal: true,
      ),
      BannerAd(
        id: 'banner_0p2',
        imageUrl: 'assets/banners/p2.png',
        clickUrl: 'https://villiersjets.com/?id=7275',
        title: 'Product p2',
        weight: 5,
        isLocal: true,
      ),
      BannerAd(
        id: 'banner_0p3',
        imageUrl: 'assets/banners/p3.png',
        clickUrl: 'https://villiersjets.com/?id=7275',
        title: 'Product p3',
        weight: 15,
        isLocal: true,
      ),
      BannerAd(
        id: 'banner_0p4',
        imageUrl: 'assets/banners/p4.png',
        clickUrl: 'https://villiersjets.com/?id=7275',
        title: 'Product p4',
        weight: 8,
        isLocal: true,
      ),
      BannerAd(
        id: 'banner_0p5',
        imageUrl: 'assets/banners/p5.png',
        clickUrl: 'https://villiersjets.com/?id=7275',
        title: 'Product p5',
        weight: 8,
        isLocal: true,
      ),
      BannerAd(
        id: 'banner_0p6',
        imageUrl: 'assets/banners/p6.png',
        clickUrl: 'https://villiersjets.com/?id=7275',
        title: 'Product p6',
        weight: 15,
        isLocal: true,
      ),
    ];
  }

  // Filter by our naming convention: ids with '0p' pattern are portrait
  List<BannerAd> _filterByOrientation(BannerOrientation o) {
    return _banners.where((b) {
      final isPortrait = b.id.contains('0p');
      return o == BannerOrientation.portrait ? isPortrait : !isPortrait;
    }).toList();
  }

  // Weighted random from a list
  BannerAd? _weightedPick(List<BannerAd> list) {
    if (list.isEmpty) return null;
    final total = list.fold<int>(0, (sum, b) => sum + (b.weight ?? 1));
    var roll = Random().nextInt(total);
    for (final b in list) {
      roll -= (b.weight ?? 1);
      if (roll < 0) return b;
    }
    return list.first;
  }

  // Public: random by orientation
  BannerAd? getRandomByOrientation(BannerOrientation o) {
    final list = _filterByOrientation(o);
    return _weightedPick(list) ?? getRandomBanner();
  }

  // Public: all by orientation
  List<BannerAd> getAllByOrientation(BannerOrientation o) {
    return _filterByOrientation(o);
  }
  
  BannerAd? getRandomBanner() {
    if (_banners.isEmpty) return null;
    
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
  
  Future<void> refresh() async {
    _loadLocalBanners();
  }
  
  Future<void> recordClick(String bannerId) async {
    try {
      await http.post(
        Uri.parse('$_apiBaseUrl/api/banners/click'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'banner_id': bannerId}),
      ).timeout(const Duration(seconds: 5));
    } catch (e) {
      // Fail silently - don't impact user experience
    }
  }
  
  Future<void> recordImpression(String bannerId) async {
    try {
      await http.post(
        Uri.parse('$_apiBaseUrl/api/banners/impression'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'banner_id': bannerId}),
      ).timeout(const Duration(seconds: 5));
    } catch (e) {
      // Fail silently - don't impact user experience
    }
  }
}

class BannerAd {
  final String id;
  final String imageUrl;
  final String clickUrl;
  final String title;
  final int weight;
  final bool isLocal;
  
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
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class BannerService {
  static final BannerService _instance = BannerService._internal();
  factory BannerService() => _instance;
  BannerService._internal();
  
  static BannerService get I => _instance;
  
  List<BannerAd> _banners = [];
  
  Future<void> init() async {
    _loadHardcodedBanners();
  }
  
  void _loadHardcodedBanners() {
    // Hardcoded banners from assets folder
    _banners = [
      BannerAd(
        id: 'banner_001',
        imageUrl: 'assets/banners/banner1.png',
        clickUrl: 'https://villiersjetcom?id=7275',
        title: 'Product 1',
        weight: 10,
        isLocal: true,
      ),
      BannerAd(
        id: 'banner_002',
        imageUrl: 'assets/banners/banner2.png',
        clickUrl: 'https://villiersjetcom?id=7275',
        title: 'Product 2',
        weight: 5,
        isLocal: true,
      ),
      BannerAd(
        id: 'banner_003',
        imageUrl: 'assets/banners/banner3.png',
        clickUrl: 'https://villiersjetcom?id=7275',
        title: 'Product 3',
        weight: 15,
        isLocal: true,
      ),
      BannerAd(
        id: 'banner_004',
        imageUrl: 'assets/banners/banner4.png',
        clickUrl: 'https://villiersjetcom?id=7275',
        title: 'Product 4',
        weight: 8,
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
  
  Future<void> recordClick(String bannerId) async {
    // Track banner click locally or send to analytics
    print('Banner clicked: $bannerId');
    
    // Optional: Send to your backend for analytics
    // try {
    //   await http.post(
    //     Uri.parse('https://your-api.com/api/banners/click'),
    //     headers: {'Content-Type': 'application/json'},
    //     body: jsonEncode({'banner_id': bannerId}),
    //   );
    // } catch (e) {
    //   print('Error recording click: $e');
    // }
  }
  
  Future<void> recordImpression(String bannerId) async {
    // Track banner impression locally or send to analytics
    print('Banner impression: $bannerId');
    
    // Optional: Send to your backend for analytics
    // try {
    //   await http.post(
    //     Uri.parse('https://your-api.com/api/banners/impression'),
    //     headers: {'Content-Type': 'application/json'},
    //     body: jsonEncode({'banner_id': bannerId}),
    //   );
    // } catch (e) {
    //   print('Error recording impression: $e');
    // }
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
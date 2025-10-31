import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../services/banner_service.dart';

class AffiliateBannerWidget extends StatefulWidget {
  final EdgeInsets padding;
  final double height;
  
  const AffiliateBannerWidget({
    super.key,
    this.padding = const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
    this.height = 80,
  });

  @override
  State<AffiliateBannerWidget> createState() => _AffiliateBannerWidgetState();
}

class _AffiliateBannerWidgetState extends State<AffiliateBannerWidget> {
  final _bannerService = BannerService.I;
  BannerAd? _currentBanner;
  bool _impressionRecorded = false;

  @override
  void initState() {
    super.initState();
    _loadBanner();
  }

  void _loadBanner() {
    final banner = _bannerService.getRandomBanner();
    if (banner != null && mounted) {
      setState(() => _currentBanner = banner);
      
      // Record impression after a short delay to ensure visibility
      Future.delayed(const Duration(milliseconds: 500), () {
        if (mounted && !_impressionRecorded) {
          _bannerService.recordImpression(banner.id);
          _impressionRecorded = true;
        }
      });
    }
  }

  Future<void> _handleBannerTap() async {
    if (_currentBanner == null) return;
    
    await _bannerService.recordClick(_currentBanner!.id);
    
    final url = Uri.parse(_currentBanner!.clickUrl);
    if (await canLaunchUrl(url)) {
      await launchUrl(url, mode: LaunchMode.externalApplication);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_currentBanner == null) return const SizedBox.shrink();

    final size = MediaQuery.of(context).size;
    final isLandscape = size.width > size.height;
    final isTablet = size.shortestSide >= 600;

    final EdgeInsets adaptivePadding = isTablet
        ? const EdgeInsets.symmetric(horizontal: 40, vertical: 16)
        : widget.padding;

    const double bannerAspect = 1024 / 500;

    return Padding(
      padding: adaptivePadding,
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: _handleBannerTap,
          borderRadius: BorderRadius.circular(12),
          child: LayoutBuilder(
            builder: (context, constraints) {
              final ideal = constraints.maxWidth / bannerAspect;
              
              // Increased height limits for better text readability in landscape
              final maxLandscape = isTablet && isLandscape 
                  ? size.height * 0.32  // Tablets in landscape
                  : size.height * 0.38; // Phones in landscape
              final maxPortrait = size.height * 0.22;
              const minH = 72.0;

              final targetHeight = (isLandscape
                      ? ideal.clamp(minH, maxLandscape)
                      : ideal.clamp(minH, maxPortrait))
                  .toDouble();

              return AnimatedSwitcher(
                duration: const Duration(milliseconds: 500),
                child: Container(
                  key: ValueKey(_currentBanner!.id),
                  height: targetHeight,
                  decoration: BoxDecoration(
                    color: Colors.white.withOpacity(0.12),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: Colors.white.withOpacity(0.25)),
                  ),
                  clipBehavior: Clip.antiAlias,
                  child: AspectRatio(
                    aspectRatio: bannerAspect,
                    child: Stack(
                      fit: StackFit.expand,
                      children: [
                        _currentBanner!.isLocal
                            ? Image.asset(_currentBanner!.imageUrl, fit: BoxFit.cover)
                            : Image.network(
                                _currentBanner!.imageUrl,
                                fit: BoxFit.cover,
                                errorBuilder: (c, e, s) =>
                                    const Center(child: Icon(Icons.image_not_supported, color: Colors.white54)),
                              ),
                      ],
                    ),
                  ),
                ),
              );
            },
          ),
        ),
      ),
    );
  }


}
// Alternative: Rotating Banner Widget that changes every few seconds
class RotatingBannerWidget extends StatefulWidget {
  final Duration rotationInterval;
  final EdgeInsets padding;
  final double height;
  
  const RotatingBannerWidget({
    super.key,
    this.rotationInterval = const Duration(seconds: 10),
    this.padding = const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
    this.height = 80,
  });

  @override
  State<RotatingBannerWidget> createState() => _RotatingBannerWidgetState();
}

class _RotatingBannerWidgetState extends State<RotatingBannerWidget> {
  final _bannerService = BannerService.I;
  List<BannerAd> _banners = [];
  int _currentIndex = 0;

  @override
  void initState() {
    super.initState();
    _loadBanners();
    _startRotation();
  }

  void _loadBanners() {
    setState(() {
      _banners = _bannerService.getAllBanners();
      if (_banners.isNotEmpty) {
        _bannerService.recordImpression(_banners[_currentIndex].id);
      }
    });
  }

  void _startRotation() {
    Future.delayed(widget.rotationInterval, () {
      if (mounted && _banners.isNotEmpty) {
        setState(() {
          _currentIndex = (_currentIndex + 1) % _banners.length;
        });
        _bannerService.recordImpression(_banners[_currentIndex].id);
        _startRotation();
      }
    });
  }

  Future<void> _handleBannerTap() async {
    if (_banners.isEmpty) return;
    
    final banner = _banners[_currentIndex];
    await _bannerService.recordClick(banner.id);
    
    final url = Uri.parse(banner.clickUrl);
    if (await canLaunchUrl(url)) {
      await launchUrl(url, mode: LaunchMode.externalApplication);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_banners.isEmpty) return const SizedBox.shrink();

    final size = MediaQuery.of(context).size;
    final isLandscape = size.width > size.height;
    final isTablet = size.shortestSide >= 600;

    final EdgeInsets adaptivePadding = isTablet
        ? const EdgeInsets.symmetric(horizontal: 40, vertical: 16)
        : widget.padding;

    const double bannerAspect = 1024 / 500;

    return Padding(
      padding: adaptivePadding,
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: _handleBannerTap,
          borderRadius: BorderRadius.circular(12),
          child: LayoutBuilder(
            builder: (context, constraints) {
              final ideal = constraints.maxWidth / bannerAspect;
              
              // Increased height limits for better text readability in landscape
              final maxLandscape = isTablet && isLandscape 
                  ? size.height * 0.32  // Tablets in landscape
                  : size.height * 0.38; // Phones in landscape
              final maxPortrait = size.height * 0.22;
              const minH = 72.0;

              final targetHeight = (isLandscape
                      ? ideal.clamp(minH, maxLandscape)
                      : ideal.clamp(minH, maxPortrait))
                  .toDouble();

              return Container(
                height: targetHeight,
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.12),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: Colors.white.withOpacity(0.25)),
                ),
                clipBehavior: Clip.antiAlias,
                child: AspectRatio(
                  aspectRatio: bannerAspect,
                  child: Stack(
                    fit: StackFit.expand,
                    children: [
                      _banners[_currentIndex].isLocal
                          ? Image.asset(_banners[_currentIndex].imageUrl, fit: BoxFit.cover)
                          : Image.network(
                              _banners[_currentIndex].imageUrl,
                              fit: BoxFit.cover,
                              errorBuilder: (c, e, s) =>
                                  const Center(child: Icon(Icons.image_not_supported, color: Colors.white54)),
                            ),
                      Positioned(
                        top: 4,
                        right: 4,
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(
                            color: Colors.black54,
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: const Text(
                            'Ad',
                            style: TextStyle(color: Colors.white, fontSize: 9, fontWeight: FontWeight.w600),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              );
            },
          ),
        ),
      ),
    );
  }

}
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
    if (_currentBanner == null) {
      return const SizedBox.shrink();
    }

    // Detect tablet size
    final screenWidth = MediaQuery.of(context).size.width;
    final isTablet = screenWidth >= 600; // Standard tablet breakpoint
    final bannerHeight = isTablet ? 120.0 : widget.height; // Larger for tablets

    return Padding(
      padding: widget.padding,
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: _handleBannerTap,
          borderRadius: BorderRadius.circular(12),
          child: Container(
            height: bannerHeight, // Use dynamic height
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.15),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                color: Colors.white.withOpacity(0.3),
                width: 1,
              ),
            ),
            child: Stack(
              children: [
                ClipRRect(
                  borderRadius: BorderRadius.circular(12),
                  child: _currentBanner!.isLocal
                      ? Image.asset(
                          _currentBanner!.imageUrl,
                          width: double.infinity,
                          height: widget.height,
                          fit: BoxFit.cover,
                          errorBuilder: (context, error, stackTrace) {
                            return Container(
                              alignment: Alignment.center,
                              child: const Icon(
                                Icons.image_not_supported,
                                color: Colors.white54,
                              ),
                            );
                          },
                        )
                      : Image.network(
                          _currentBanner!.imageUrl,
                          width: double.infinity,
                          height: widget.height,
                          fit: BoxFit.cover,
                          errorBuilder: (context, error, stackTrace) {
                            return Container(
                              alignment: Alignment.center,
                              child: const Icon(
                                Icons.image_not_supported,
                                color: Colors.white54,
                              ),
                            );
                          },
                          loadingBuilder: (context, child, loadingProgress) {
                            if (loadingProgress == null) return child;
                            return Center(
                              child: CircularProgressIndicator(
                                value: loadingProgress.expectedTotalBytes != null
                                    ? loadingProgress.cumulativeBytesLoaded /
                                        loadingProgress.expectedTotalBytes!
                                    : null,
                                valueColor: const AlwaysStoppedAnimation<Color>(Colors.white),
                              ),
                            );
                          },
                        ),
                ),
                // Optional: Add a "Ad" label
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
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 9,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                ),
              ],
            ),
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
    if (_banners.isEmpty) {
      return const SizedBox.shrink();
    }

    final currentBanner = _banners[_currentIndex];

    return Padding(
      padding: widget.padding,
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: _handleBannerTap,
          borderRadius: BorderRadius.circular(12),
          child: AnimatedSwitcher(
            duration: const Duration(milliseconds: 500),
            child: Container(
              key: ValueKey(currentBanner.id),
              height: widget.height,
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.15),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(
                  color: Colors.white.withOpacity(0.3),
                  width: 1,
                ),
              ),
              child: Stack(
                children: [
                  ClipRRect(
                    borderRadius: BorderRadius.circular(12),
                    child: currentBanner.isLocal
                        ? Image.asset(
                            currentBanner.imageUrl,
                            width: double.infinity,
                            height: widget.height,
                            fit: BoxFit.cover,
                            errorBuilder: (context, error, stackTrace) {
                              return Container(
                                alignment: Alignment.center,
                                child: const Icon(
                                  Icons.image_not_supported,
                                  color: Colors.white54,
                                ),
                              );
                            },
                          )
                        : Image.network(
                            currentBanner.imageUrl,
                            width: double.infinity,
                            height: widget.height,
                            fit: BoxFit.cover,
                            errorBuilder: (context, error, stackTrace) {
                              return Container(
                                alignment: Alignment.center,
                                child: const Icon(
                                  Icons.image_not_supported,
                                  color: Colors.white54,
                                ),
                              );
                            },
                          ),
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
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 9,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ),
                  ),
                  // Page indicator
                  if (_banners.length > 1)
                    Positioned(
                      bottom: 8,
                      left: 0,
                      right: 0,
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: List.generate(_banners.length, (index) {
                          return Container(
                            margin: const EdgeInsets.symmetric(horizontal: 2),
                            width: 6,
                            height: 6,
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              color: index == _currentIndex
                                  ? Colors.white
                                  : Colors.white.withOpacity(0.4),
                            ),
                          );
                        }),
                      ),
                    ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
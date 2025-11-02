import 'dart:async';
import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../services/banner_service.dart';

class AffiliateBannerWidget extends StatefulWidget {
  final EdgeInsets padding;
  final double height;
  final String? forceBannerId;
  
  const AffiliateBannerWidget({
    super.key,
    this.padding = const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
    this.height = 80,
    this.forceBannerId,
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

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _loadBannerForOrientation();
  }

  void _loadBanner() {
    _currentBanner = BannerService.I.getRandomBanner();
  }

  void _loadBannerForOrientation() {
    final flutterOrientation = MediaQuery.of(context).orientation;
    final svcOrientation = flutterOrientation == Orientation.portrait
        ? BannerOrientation.portrait
        : BannerOrientation.landscape;

    if (widget.forceBannerId != null) {
      final allBanners = BannerService.I.getAllByOrientation(svcOrientation);
      final forced = allBanners.where((b) => b.id == widget.forceBannerId).toList();
      final chosen = forced.isNotEmpty 
          ? forced.first 
          : (BannerService.I.getRandomByOrientation(svcOrientation) ?? BannerService.I.getRandomBanner());
      if (mounted) setState(() => _currentBanner = chosen);
    } else {
      final chosen = BannerService.I.getRandomByOrientation(svcOrientation) ?? BannerService.I.getRandomBanner();
      if (mounted) setState(() => _currentBanner = chosen);
    }

    if (_currentBanner != null && !_impressionRecorded) {
      _bannerService.recordImpression(_currentBanner!.id);
      _impressionRecorded = true;
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

    final screenWidth = MediaQuery.of(context).size.width;
    final isTablet = screenWidth >= 600;
    final adaptiveHeight = isTablet ? widget.height * 1.5 : widget.height;
    final adaptivePadding = isTablet 
        ? const EdgeInsets.symmetric(horizontal: 40, vertical: 16)
        : widget.padding;

    return Padding(
      padding: adaptivePadding,
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: _handleBannerTap,
          borderRadius: BorderRadius.circular(12),
          child: Container(
            height: adaptiveHeight,
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
                          height: adaptiveHeight,
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
                          height: adaptiveHeight,
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
  final String? forceBannerId;
  
  const RotatingBannerWidget({
    super.key,
    this.rotationInterval = const Duration(seconds: 10),
    this.padding = const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
    this.height = 80,
    this.forceBannerId,
  });

  @override
  State<RotatingBannerWidget> createState() => _RotatingBannerWidgetState();
}

class _RotatingBannerWidgetState extends State<RotatingBannerWidget> {
  final _bannerService = BannerService.I;
  List<BannerAd> _banners = [];
  int _currentIndex = 0;
  Timer? _rotationTimer;

  @override
  void initState() {
    super.initState();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _loadBannerForOrientation();
  }

  void _loadBannerForOrientation() {
    final flutterOrientation = MediaQuery.of(context).orientation;
    final svcOrientation = flutterOrientation == Orientation.portrait
        ? BannerOrientation.portrait
        : BannerOrientation.landscape;

    List<BannerAd> availableBanners;

    if (widget.forceBannerId != null) {
      final list = BannerService.I.getAllByOrientation(svcOrientation);
      final forced = list.where((b) => b.id == widget.forceBannerId).toList();
      availableBanners = forced.isNotEmpty 
          ? forced 
          : (BannerService.I.getAllByOrientation(svcOrientation).isNotEmpty
              ? BannerService.I.getAllByOrientation(svcOrientation)
              : [BannerService.I.getRandomBanner()].whereType<BannerAd>().toList());
    } else {
      availableBanners = BannerService.I.getAllByOrientation(svcOrientation);
      if (availableBanners.isEmpty) {
        final randomBanner = BannerService.I.getRandomBanner();
        if (randomBanner != null) {
          availableBanners = [randomBanner];
        }
      }
    }

    if (mounted && availableBanners.isNotEmpty) {
      setState(() {
        _banners = availableBanners;
        _currentIndex = 0;
      });
      _bannerService.recordImpression(availableBanners[0].id);
      _startRotationTimer();
    }
  }

  void _startRotationTimer() {
    _rotationTimer?.cancel();
    
    if (_banners.length > 1) {
      _rotationTimer = Timer.periodic(widget.rotationInterval, (timer) {
        if (mounted) {
          setState(() {
            _currentIndex = (_currentIndex + 1) % _banners.length;
          });
          _bannerService.recordImpression(_banners[_currentIndex].id);
        }
      });
    }
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
  void dispose() {
    _rotationTimer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_banners.isEmpty) {
      return const SizedBox.shrink();
    }

    final currentBanner = _banners[_currentIndex];
    final screenWidth = MediaQuery.of(context).size.width;
    final isTablet = screenWidth >= 600;
    final adaptiveHeight = isTablet ? widget.height * 3.0 : widget.height;
    final adaptivePadding = isTablet 
        ? const EdgeInsets.symmetric(horizontal: 40, vertical: 16)
        : widget.padding;

    return Padding(
      padding: adaptivePadding,
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: _handleBannerTap,
          borderRadius: BorderRadius.circular(12),
          child: AnimatedSwitcher(
            duration: const Duration(milliseconds: 500),
            child: Container(
              key: ValueKey(currentBanner.id),
              height: adaptiveHeight,
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
                            height: adaptiveHeight,
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
                            height: adaptiveHeight,
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
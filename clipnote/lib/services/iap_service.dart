// lib/services/iap_service.dart
import 'dart:async';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:in_app_purchase/in_app_purchase.dart';
import 'package:device_info_plus/device_info_plus.dart';

import 'api_service.dart';

/// Store product IDs
const kStarterMonthlyId  = 'com.clipnote.starter.monthly';
const kProMonthlyId      = 'clipnote.pro.monthly';
const kBusinessMonthlyId = 'clipnote.business.monthly';

class IapService {
  IapService._internal();
  static final IapService _inst = IapService._internal();
  factory IapService() => _inst;

  final InAppPurchase _iap = InAppPurchase.instance;
  final ApiService _api = ApiService.I;

  // Availability and init
  bool _available = false;
  bool get isAvailable => _available;

  bool _initialized = false;

  // Prevent duplicate purchase attempts
  bool _purchaseInFlight = false;
  bool get isBusy => _purchaseInFlight;

  // Single subscription to purchase updates (nullable to allow dispose)
  StreamSubscription<List<PurchaseDetails>>? _sub;

  // Cache product details
  final Map<String, ProductDetails> _products = {};
  ProductDetails? get starterProduct  => _products[kStarterMonthlyId];
  ProductDetails? get proProduct      => _products[kProMonthlyId];
  ProductDetails? get businessProduct => _products[kBusinessMonthlyId];

  /// Initialize IAP once per app lifecycle.
  Future<void> init() async {
    if (_initialized) return;
    _initialized = true;

    _available = await _iap.isAvailable();
    if (!_available) return;

    // Attach exactly one listener
    _sub ??= _iap.purchaseStream.listen(
      _onPurchaseUpdates,
      onError: (e, s) => debugPrint('IAP stream error: $e'),
    );

    // Warm up product cache (ignore notFoundIDs here; we fetch on demand, too)
    final resp = await _iap.queryProductDetails({
      kStarterMonthlyId, kProMonthlyId, kBusinessMonthlyId
    });
    for (final p in resp.productDetails) {
      _products[p.id] = p;
    }
  }

  Future<void> dispose() async {
    await _sub?.cancel();
    _sub = null;
    _initialized = false;
  }

  /// Public helpers to kick off purchases
  Future<String> purchaseStarter()  => _purchaseProduct(kStarterMonthlyId);
  Future<String> purchasePro()      => _purchaseProduct(kProMonthlyId);
  Future<String> purchaseBusiness() => _purchaseProduct(kBusinessMonthlyId);

  Future<String> _purchaseProduct(String productId) async {
    await init();
    if (!_available) throw Exception('IAP not available on this device/store.');

    if (_purchaseInFlight) return 'busy';
    _purchaseInFlight = true;

    try {
      var product = _products[productId];
      if (product == null) {
        final resp = await _iap.queryProductDetails({
          kStarterMonthlyId, kProMonthlyId, kBusinessMonthlyId
        });
        if (resp.notFoundIDs.contains(productId)) {
          throw Exception('Product $productId not found. Check store configuration.');
        }
        if (resp.productDetails.isNotEmpty) {
          product = resp.productDetails.firstWhere(
            (p) => p.id == productId,
            orElse: () => resp.productDetails.first,
          );
          _products[product.id] = product;
        }
      }

      if (product == null) {
        throw Exception('Product not found: $productId');
      }

      final param = PurchaseParam(productDetails: product);
      final ok = await _iap.buyNonConsumable(purchaseParam: param);
      if (!ok) return 'failed_to_start';
      return 'pending';
    } catch (_) {
      // Let UI surface specific messages if desired
      rethrow;
    }
    // NOTE: we clear _purchaseInFlight in _onPurchaseUpdates after the stream event arrives
  }

  Future<void> restorePurchases() async {
    await init();
    if (!_available) throw Exception('IAP not available on this device/store.');
    await _iap.restorePurchases();
  }

  /// Handle purchase updates from store
  Future<void> _onPurchaseUpdates(List<PurchaseDetails> list) async {
    try {
      for (final p in list) {
        switch (p.status) {
          case PurchaseStatus.pending:
            break;

          case PurchaseStatus.purchased:
          case PurchaseStatus.restored:
            try {
              await _verifyWithBackend(p);
            } finally {
              if (p.pendingCompletePurchase) {
                await _iap.completePurchase(p);
              }
            }
            break;

          case PurchaseStatus.error:
            if (p.pendingCompletePurchase) {
              await _iap.completePurchase(p);
            }
            break;

          case PurchaseStatus.canceled:
            break;
        }
      }
    } finally {
      // Clear the busy flag once we’ve processed the batch
      _purchaseInFlight = false;
    }
  }

  /// Send receipt/token to backend to verify and issue/update license
  Future<void> _verifyWithBackend(PurchaseDetails p) async {
    final receipt = p.verificationData.serverVerificationData.isNotEmpty
        ? p.verificationData.serverVerificationData
        : p.verificationData.localVerificationData;

    final store = Platform.isAndroid ? 'google_play' : 'app_store';
    final userId = await _getDeviceId();

    // Uses your existing ApiService instance method
    final _ = await _api.verifyIapAndGetLicense(
      userId: userId,
      receipt: receipt,
      productId: p.productID,
      store: store,
      email: null,
    );

    // Optionally: persist license / trigger UI refresh elsewhere
  }

  Future<String> _getDeviceId() async {
    final deviceInfo = DeviceInfoPlugin();
    if (Platform.isAndroid) {
      final androidInfo = await deviceInfo.androidInfo;
      return androidInfo.id;
    } else {
      final iosInfo = await deviceInfo.iosInfo;
      return iosInfo.identifierForVendor ?? 'unknown';
    }
  }
}

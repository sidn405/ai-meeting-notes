// lib/services/iap_service.dart
import 'dart:async';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:in_app_purchase/in_app_purchase.dart';

import 'api_service.dart';

/// Replace these with the exact product IDs you configure in Play Console / App Store Connect.
const kProMonthlyId = 'com.clipnote.pro.monthly';
const kBusinessMonthlyId = 'com.clipnote.business.monthly';

class IapService {
  IapService._internal();
  static final IapService _inst = IapService._internal();
  factory IapService() => _inst;

  final InAppPurchase _iap = InAppPurchase.instance;
  final ApiService _api = ApiService();

  late final StreamSubscription<List<PurchaseDetails>> _sub;

  bool _available = false;
  bool get isAvailable => _available;

  /// Cache products so UI can render price text if needed
  final Map<String, ProductDetails> _products = {};

  Future<void> init() async {
    _available = await _iap.isAvailable();
    if (!_available) return;

    // Listen to purchase updates
    _sub = _iap.purchaseStream.listen(_onPurchaseUpdates, onDone: () {
      // ignore
    }, onError: (Object e, StackTrace s) {
      // ignore — errors surface individually in _onPurchaseUpdates
    });

    // Query products
    final resp = await _iap.queryProductDetails({kProMonthlyId, kBusinessMonthlyId});
    if (resp.error != null) {
      // You can log resp.error
    }
    for (final p in resp.productDetails) {
      _products[p.id] = p;
    }
  }

  Future<void> dispose() async {
    if (_available) {
      await _sub.cancel();
    }
  }


  ProductDetails? get proProduct => _products[kProMonthlyId];
  ProductDetails? get businessProduct => _products[kBusinessMonthlyId];

  /// Public entry points used by the UI
  Future<String> purchasePro() async {
    final p = proProduct;
    if (p == null) {
      // Lazy-load if not present (first run)
      await init();
    }
    return _purchaseProduct(kProMonthlyId);
  }

  Future<String> purchaseBusiness() async {
    final p = businessProduct;
    if (p == null) {
      await init();
    }
    return _purchaseProduct(kBusinessMonthlyId);
  }

  Future<String> _purchaseProduct(String productId) async {
    if (!_available) {
      await init();
      if (!_available) {
        throw 'IAP not available on this device/store.';
      }
    }

    final details = _products[productId];
    if (details == null) {
      // Try query again (products may not be cached yet)
      final resp = await _iap.queryProductDetails({productId});
      if (resp.notFoundIDs.contains(productId)) {
        throw 'Product $productId not found. Check store configuration.';
      }
      _products[productId] = resp.productDetails.first;
    }

    final product = _products[productId];
    if (product == null) {
      throw Exception('Product not found: $productId');
    }
    final purchaseParam = PurchaseParam(productDetails: product);

    final ok = await _iap.buyNonConsumable(purchaseParam: purchaseParam);
    if (!ok) throw 'Failed to start purchase flow.';

    // We will complete the flow via the purchaseStream.
    // Return a placeholder; UI will be notified via verification (optional).
    return 'pending';
  }

  Future<void> _onPurchaseUpdates(List<PurchaseDetails> list) async {
    for (final p in list) {
      switch (p.status) {
        case PurchaseStatus.pending:
          // UI could show a loading indicator if you propagate this.
          break;

        case PurchaseStatus.purchased:
        case PurchaseStatus.restored:
          // 1) Verify with your backend
          await _verifyWithBackend(p);

          // 2) Complete the purchase so Google/Apple considers it finished
          if (p.pendingCompletePurchase) {
            await _iap.completePurchase(p);
          }
          break;

        case PurchaseStatus.error:
          // You could surface p.error to the UI
          if (p.pendingCompletePurchase) {
            await _iap.completePurchase(p);
          }
          break;

        case PurchaseStatus.canceled:
          // User canceled — nothing to do.
          break;
      }
    }
  }

  Future<void> _verifyWithBackend(PurchaseDetails p) async {
    // serverVerificationData is recommended for Android & iOS for server-side verification
    final receipt = p.verificationData.serverVerificationData;

    final store = Platform.isAndroid
        ? 'google_play'
        : Platform.isIOS
            ? 'app_store'
            : 'unknown';

    try {
      await _api.verifyIapReceipt(store: store, receipt: receipt);
      // Optionally call _api.getLicenseInfo() here and notify app state.
    } catch (e) {
      // If verification fails, consider consuming/refunding depending on your policy.
      // For subscriptions, you usually just deny entitlement in your backend.
      if (kDebugMode) {
        // ignore: avoid_print
        print('IAP verification failed: $e');
      }
      rethrow;
    }
  }
}

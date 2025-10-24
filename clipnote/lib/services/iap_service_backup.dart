import 'dart:async';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:in_app_purchase/in_app_purchase.dart';
import 'package:device_info_plus/device_info_plus.dart';

import 'api_service.dart';

const kProMonthlyId = 'clipnote.pro.monthly';
const kBusinessMonthlyId = 'clipnote.business.monthly';
const kStarterMonthlyId = 'com.clipnote.starter.monthly'; // Add this

class IapService {
  IapService._internal();
  static final IapService _inst = IapService._internal();
  factory IapService() => _inst;

  final InAppPurchase _iap = InAppPurchase.instance;
  final ApiService _api = ApiService.I;

  late final StreamSubscription<List<PurchaseDetails>> _sub;

  bool _available = false;
  bool get isAvailable => _available;

  final Map<String, ProductDetails> _products = {};

  Future<void> init() async {
    _available = await _iap.isAvailable();
    if (!_available) return;

    _sub = _iap.purchaseStream.listen(_onPurchaseUpdates, onDone: () {
      // ignore
    }, onError: (Object e, StackTrace s) {
      // ignore
    });

    final resp = await _iap.queryProductDetails({kStarterMonthlyId, kProMonthlyId, kBusinessMonthlyId});
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

  ProductDetails? get starterProduct => _products[kStarterMonthlyId];
  ProductDetails? get proProduct => _products[kProMonthlyId];
  ProductDetails? get businessProduct => _products[kBusinessMonthlyId];

  final kStarterMonthlyId = 'com.clipnote.starter.monthly';
  final kProMonthlyId = 'clipnote.pro.monthly';
  final kBusinessMonthlyId = 'clipnote.business.monthly';

  Future<String> purchasePro() async {
    final p = proProduct;
    if (p == null) {
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
        throw Exception('IAP not available on this device/store.');
      }
    }

    final details = _products[productId];
    if (details == null) {
      final resp = await _iap.queryProductDetails({
        kStarterMonthlyId,
        kProMonthlyId,
        kBusinessMonthlyId,
      });
      if (resp.notFoundIDs.contains(productId)) {
        throw Exception('Product $productId not found. Check store configuration.');
      }
      if (resp.productDetails.isNotEmpty) {
        _products[productId] = resp.productDetails.first;
      }
    }

    final product = _products[productId];
    if (product == null) {
      throw Exception('Product not found: $productId');
    }
    final purchaseParam = PurchaseParam(productDetails: product);

    final ok = await _iap.buyNonConsumable(purchaseParam: purchaseParam);
    if (!ok) throw Exception('Failed to start purchase flow.');

    return 'pending';
  }

  Future<void> _onPurchaseUpdates(List<PurchaseDetails> list) async {
    for (final p in list) {
      switch (p.status) {
        case PurchaseStatus.pending:
          break;

        case PurchaseStatus.purchased:
        case PurchaseStatus.restored:
          await _verifyWithBackend(p);

          if (p.pendingCompletePurchase) {
            await _iap.completePurchase(p);
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
  }

  Future<void> _verifyWithBackend(PurchaseDetails p) async {
    final receipt = p.verificationData.serverVerificationData;
    final store = Platform.isAndroid ? 'google_play' : 'app_store';
    
    final userId = await _getDeviceId();
    
    try {
      final licenseKey = await _api.verifyIapAndGetLicense(
        userId: userId,
        receipt: receipt,
        productId: p.productID,
        store: store,
        email: null,
      );
      
      print('✅ IAP verified! License key: $licenseKey');
      
    } catch (e) {
      print('❌ IAP verification failed: $e');
      rethrow;
    }
  }

  Future<String> _getDeviceId() async {
    final deviceInfo = DeviceInfoPlugin();
    if (Platform.isAndroid) {
      final androidInfo = await deviceInfo.androidInfo;
      return androidInfo.id;
    } else {
      final iosInfo = await deviceInfo.iosInfo;
      return iosInfo.identifierForVendor ?? '';
    }
  }

  Future<void> restorePurchases() async {
    if (!_available) {
      await init();
      if (!_available) {
        throw Exception('IAP not available on this device/store.');
      }
    }
    
    try {
      await _iap.restorePurchases();
    } catch (e) {
      if (kDebugMode) {
        print('Failed to restore purchases: $e');
      }
      rethrow;
    }
  }
}
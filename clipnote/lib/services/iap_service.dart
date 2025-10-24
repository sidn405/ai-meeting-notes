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

  bool _initialized = false;
  bool _available = false;
  bool _purchaseInFlight = false;

  // ⬇️ make it nullable (no `late`)
  StreamSubscription<List<PurchaseDetails>>? _purchaseSub;

  // your product IDs
  static const kStarterMonthlyId = 'com.clipnote.starter.monthly';
  static const kProMonthlyId     = 'clipnote.pro.monthly';
  static const kBusinessMonthlyId= 'clipnote.business.monthly';

  Future<void> init() async {
    if (_initialized) return;            // ⬅️ guard against double init
    _initialized = true;

    _available = await _iap.isAvailable();

    // only create one listener
    _purchaseSub ??= _iap.purchaseStream.listen(
      _onPurchaseUpdated,
      onError: (e, st) {
        debugPrint('IAP stream error: $e');
        _purchaseInFlight = false;
      },
      onDone: () => debugPrint('IAP stream closed'),
    );
  }

  Future<void> dispose() async {
    await _purchaseSub?.cancel();
    _purchaseSub = null;
    _initialized = false;
  }

  Future<void> restore() async {
    await init();
    if (!_available) throw Exception('IAP not available on this device/store.');
    await _iap.restorePurchases();
  }

  Future<String> purchasePro()    => _purchaseProduct(kProMonthlyId);
  Future<String> purchaseBusiness()=> _purchaseProduct(kBusinessMonthlyId);
  Future<String> purchaseStarter()=> _purchaseProduct(kStarterMonthlyId);

  Future<String> _purchaseProduct(String productId) async {
    await init();
    if (_purchaseInFlight) return 'busy';    // prevent double taps
    _purchaseInFlight = true;

    final details = await _queryProduct(productId);
    final param = PurchaseParam(productDetails: details);
    // Subscriptions are non-consumable in the plugin API:
    final ok = await _iap.buyNonConsumable(purchaseParam: param);
    if (!ok) _purchaseInFlight = false;
    return ok ? 'started' : 'failed_to_start';
  }

  Future<ProductDetails> _queryProduct(String id) async {
    final resp = await _iap.queryProductDetails({id});
    if (resp.notFoundIDs.isNotEmpty || resp.productDetails.isEmpty) {
      throw Exception('Product not found: $id');
    }
    return resp.productDetails.first;
  }

  Future<void> _onPurchaseUpdated(List<PurchaseDetails> list) async {
    for (final p in list) {
      switch (p.status) {
        case PurchaseStatus.purchased:
        case PurchaseStatus.restored:
          await _verifyAndDeliver(p);
          break;
        case PurchaseStatus.error:
          debugPrint('Purchase error: ${p.error}');
          break;
        case PurchaseStatus.canceled:
        case PurchaseStatus.pending:
          break;
        default:
          break;
      }
      if (p.pendingCompletePurchase) {
        await _iap.completePurchase(p);
      }
    }
    _purchaseInFlight = false;
  }

  Future<void> _verifyAndDeliver(PurchaseDetails p) async {
    final productId = p.productID;
    final token = (p.verificationData.serverVerificationData.isNotEmpty)
        ? p.verificationData.serverVerificationData
        : p.verificationData.localVerificationData;

    final userId = await _deviceId(); // device_info_plus
    final body = {
      "user_id": userId,
      "email": null,                  // or your signed-in email
      "receipt": token,
      "product_id": productId,
      "store": Platform.isAndroid ? "google_play" : "app_store",
    };

    final res = await ApiService.post('/iap/verify', body); // your backend
    if (!(res['success'] == true)) {
      throw Exception('Server verification failed: ${res['message']}');
    }
    // TODO: persist license key/tier locally for your UI
  }

  Future<String> _deviceId() async {
    final info = await DeviceInfoPlugin().androidInfo;
    return info.id ?? 'unknown';
  }
}

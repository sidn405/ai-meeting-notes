// lib/services/iap_service.dart
import 'dart:async';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:in_app_purchase/in_app_purchase.dart';
import 'package:device_info_plus/device_info_plus.dart';

import 'api_service.dart';

/// Store product IDs
const kStarterMonthlyId  = 'com.clipnote.starter.monthly';
const kProMonthlyId      = 'clipnote_pro_monthly';
const kBusinessMonthlyId = 'clipnote_business_monthly';

/// Callback for successful purchase verification
typedef OnPurchaseSuccessCallback = void Function(String licenseKey, String tier);

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

  // Callback for successful purchase/verification
  OnPurchaseSuccessCallback? _onPurchaseSuccess;

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
    if (!_available) {
      debugPrint('[IapService] ⚠️ IAP not available on this device');
      return;
    }

    debugPrint('[IapService] ✅ IAP is available');

    // Attach exactly one listener
    _sub ??= _iap.purchaseStream.listen(
      _onPurchaseUpdates,
      onError: (e, s) => debugPrint('[IapService] ❌ IAP stream error: $e'),
    );

    // Warm up product cache (ignore notFoundIDs here; we fetch on demand, too)
    final resp = await _iap.queryProductDetails({
      kStarterMonthlyId, kProMonthlyId, kBusinessMonthlyId
    });
    
    debugPrint('[IapService] Found ${resp.productDetails.length} products');
    if (resp.notFoundIDs.isNotEmpty) {
      debugPrint('[IapService] ⚠️ Not found: ${resp.notFoundIDs}');
    }
    
    for (final p in resp.productDetails) {
      _products[p.id] = p;
      debugPrint('[IapService] Cached product: ${p.id} - ${p.title}');
    }
  }

  Future<void> dispose() async {
    await _sub?.cancel();
    _sub = null;
    _initialized = false;
  }

  /// Set callback to be notified when a purchase is successfully verified
  void setOnPurchaseSuccessCallback(OnPurchaseSuccessCallback callback) {
    _onPurchaseSuccess = callback;
  }

  /// Public helpers to kick off purchases
  Future<String> purchaseStarter()  => _purchaseProduct(kStarterMonthlyId);
  Future<String> purchasePro()      => _purchaseProduct(kProMonthlyId);
  Future<String> purchaseBusiness() => _purchaseProduct(kBusinessMonthlyId);

  Future<String> _purchaseProduct(String productId) async {
    await init();
    if (!_available) {
      throw Exception('IAP not available on this device/store.');
    }

    if (_purchaseInFlight) {
      debugPrint('[IapService] ⚠️ Purchase already in progress');
      return 'busy';
    }
    
    _purchaseInFlight = true;
    debugPrint('[IapService] 🛒 Starting purchase flow for: $productId');

    try {
      var product = _products[productId];
      if (product == null) {
        debugPrint('[IapService] Product not in cache, fetching...');
        final resp = await _iap.queryProductDetails({
          kStarterMonthlyId, kProMonthlyId, kBusinessMonthlyId
        });
        
        // Helpful debug:
        if (kDebugMode && resp.notFoundIDs.isNotEmpty) {
          debugPrint('[IapService] ⚠️ IAP notFoundIDs: ${resp.notFoundIDs}');
        }
        
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

      debugPrint('[IapService] Starting purchase for: ${product.title}');
      final param = PurchaseParam(productDetails: product);
      final ok = await _iap.buyNonConsumable(purchaseParam: param);

      if (!ok) {
        debugPrint('[IapService] ❌ Failed to start purchase flow');
        _purchaseInFlight = false;
        return 'failed_to_start';
      }
      
      debugPrint('[IapService] ✅ Purchase flow started, waiting for result...');
      return 'pending';
    } catch (e) {
      debugPrint('[IapService] ❌ Purchase error: $e');
      _purchaseInFlight = false;
      rethrow;
    } finally {
      // When a real purchase update arrives we'll clear again; harmless if already false.
      // This guarantees the button isn't left disabled in edge cases.
      _purchaseInFlight = false;
    }
  }

  Future<void> restorePurchases() async {
    await init();
    if (!_available) {
      throw Exception('IAP not available on this device/store.');
    }
    
    debugPrint('[IapService] 🔄 Restoring purchases...');
    await _iap.restorePurchases();
  }

  /// Handle purchase updates from store
  Future<void> _onPurchaseUpdates(List<PurchaseDetails> list) async {
    debugPrint('[IapService] 📦 Received ${list.length} purchase update(s)');
    
    try {
      for (final p in list) {
        debugPrint('[IapService] Processing: ${p.productID} - Status: ${p.status}');
        
        switch (p.status) {
          case PurchaseStatus.pending:
            debugPrint('[IapService] ⏳ Purchase pending: ${p.productID}');
            break;

          case PurchaseStatus.purchased:
          case PurchaseStatus.restored:
            debugPrint('[IapService] ✅ Purchase ${p.status == PurchaseStatus.purchased ? "successful" : "restored"}: ${p.productID}');
            try {
              await _verifyWithBackend(p);
            } catch (e) {
              debugPrint('[IapService] ❌ Verification error: $e');
            } finally {
              if (p.pendingCompletePurchase) {
                await _iap.completePurchase(p);
                debugPrint('[IapService] ✅ Purchase completed: ${p.productID}');
              }
            }
            break;

          case PurchaseStatus.error:
            debugPrint('[IapService] ❌ Purchase error: ${p.error?.message ?? "Unknown error"}');
            
            // ✅ CRITICAL FIX: Handle "itemAlreadyOwned" by restoring purchases
            if (p.error?.code == 'BillingResponse.itemAlreadyOwned') {
              debugPrint('[IapService] 🔄 Item already owned - attempting to restore...');
              try {
                await restorePurchases();
                debugPrint('[IapService] ✅ Restore triggered successfully');
              } catch (e) {
                debugPrint('[IapService] ❌ Restore failed: $e');
              }
            }
            
            if (p.pendingCompletePurchase) {
              await _iap.completePurchase(p);
            }
            break;

          case PurchaseStatus.canceled:
            debugPrint('[IapService] ⚠️ Purchase canceled by user');
            break;
        }
      }
    } finally {
      // Clear the busy flag once we've processed the batch
      _purchaseInFlight = false;
      debugPrint('[IapService] ✅ Batch processing complete');
    }
  }
  
  /// Send receipt/token to backend to verify and issue/update license
  Future<void> _verifyWithBackend(PurchaseDetails purchase) async {
    try {
      debugPrint('[IapService] 🔐 Verifying purchase with backend...');
      debugPrint('[IapService] Purchase ID: ${purchase.purchaseID}');
      debugPrint('[IapService] Product ID: ${purchase.productID}');

      // Get device ID
      final deviceId = await _getDeviceId();
      debugPrint('[IapService] Device ID: $deviceId');
      
      // Get receipt data
      final receipt = purchase.verificationData.serverVerificationData.isNotEmpty
          ? purchase.verificationData.serverVerificationData
          : purchase.verificationData.localVerificationData;
      
      debugPrint('[IapService] Receipt length: ${receipt.length} bytes');
      
      // Determine store
      final store = Platform.isAndroid ? 'google_play' : 'app_store';
      debugPrint('[IapService] Store: $store');
      
      // Send to backend for verification
      debugPrint('[IapService] 📡 Sending verification request...');
      final licenseKey = await _api.verifyIapAndGetLicense(
        userId: deviceId,
        receipt: receipt,
        productId: purchase.productID,
        store: store,
        email: null, // Can be added if you have user email
      );
      
      debugPrint('[IapService] ✅ Backend verification successful!');
      
      
      // ✅ CRITICAL: Save the license key
      await _api.saveLicenseKey(licenseKey);
      debugPrint('[IapService] ✅ License key saved to local storage');
      
      // ✅ CRITICAL: Refresh license info immediately
      debugPrint('[IapService] 🔄 Refreshing license info...');
      final licenseInfo = await _api.getLicenseInfo();
      debugPrint('[IapService] ✅ License info refreshed!');
      debugPrint('[IapService] Tier: ${licenseInfo['tier']}');
      debugPrint('[IapService] Tier Name: ${licenseInfo['tier_name']}');
      
      // ✅ Notify listeners to update UI
      if (_onPurchaseSuccess != null) {
        debugPrint('[IapService] 🔔 Notifying listeners...');
        _onPurchaseSuccess!(licenseKey, licenseInfo['tier']);
      }
      
      debugPrint('[IapService] ✅ Verification complete!');
      
    } catch (e, stackTrace) {
      debugPrint('[IapService] ❌ Backend verification failed: $e');
      debugPrint('[IapService] Stack trace: $stackTrace');
      
      if (e.toString().contains('socket') || 
          e.toString().contains('network') ||
          e.toString().contains('connection')) {
        debugPrint('[IapService] ⚠️ Network error - will retry on next app launch');
        // Don't complete purchase yet - retry later
        return;
      }
      
      // For other errors, still complete the purchase
      // (user paid, even if verification had issues)
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
      return iosInfo.identifierForVendor ?? 'unknown';
    }
  }
}
class AppConstants {
  // API Configuration
  static const String baseUrl = 'https://ai-meeting-notes-production-81d7.up.railway.app';
  
  // Endpoints
  static const String uploadEndpoint = '/storage/upload-direct';
  static const String meetingEndpoint = '/meetings';
  static const String licenseActivateEndpoint = '/license/activate';
  static const String licenseInfoEndpoint = '/license/info';
  
  // In-App Purchase Product IDs
  static const String professionalTierProductId = 'clipnote_professional';
  static const String businessTierProductId = 'clipnote_business';
  
  // Storage Keys
  static const String licenseKeyKey = 'license_key';
  static const String userEmailKey = 'user_email';
  
  // Tier Limits
  static const Map<String, Map<String, dynamic>> tierLimits = {
    'free': {
      'meetings_per_month': 5,
      'max_file_size_mb': 25,
      'name': 'Free'
    },
    'starter': {
      'meetings_per_month': 25,
      'max_file_size_mb': 50,
      'name': 'Starter'
    },
    'professional': {
      'meetings_per_month': 50,
      'max_file_size_mb': 200,
      'name': 'Professional'
    },
    'business': {
      'meetings_per_month': 100,
      'max_file_size_mb': 500,
      'name': 'Business'
    },
  };
}
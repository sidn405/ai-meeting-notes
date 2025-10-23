import 'package:flutter/material.dart';
import 'upload_screen.dart';
import 'user_guide_screen.dart';
import 'meetings_list_screen.dart';
import '../services/iap_service.dart';
import '../services/api_service.dart';
import '../utils/route_observer.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> with RouteAware {
  final _iapService = IapService();
  final _api = ApiService.I;
  
  Map<String, dynamic>? _licenseInfo;
  Map<String, dynamic>? _meetingStats;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _initIAP();
    _initializeLicenseAndLoadData();
  }

  Future<void> _initializeLicenseAndLoadData() async {
    // First, ensure user has a license (free tier if new)
    await _api.ensureUserHasLicense();
    // Then load all data
    await _loadData();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final route = ModalRoute.of(context);
    if (route is PageRoute) {
      routeObserver.subscribe(this, route);
    }
  }

  @override
  void dispose() {
    routeObserver.unsubscribe(this);
    super.dispose();
  }

  @override
  void didPopNext() {
    print('ðŸ"± Returned to HomeScreen - refreshing data...');
    _loadData();
  }

  @override
  void didPush() {
    print('ðŸ"± HomeScreen pushed');
  }

  @override
  void didPop() {
    print('ðŸ"± HomeScreen popped');
  }

  @override
  void didPushNext() {
    print('ðŸ"± Navigating away from HomeScreen');
  }

  Future<void> _initIAP() async {
    try {
      await _iapService.init();
    } catch (e) {
      print('Failed to initialize IAP: $e');
    }
  }

  Future<void> _loadData() async {
    setState(() => _isLoading = true);
    
    try {
      await _api.loadLicenseKey();
      
      // Load license info FIRST and wait for it
      try {
        final licenseInfo = await _api.getLicenseInfo();
        print('📝 Raw license info: $licenseInfo');
        if (mounted) {
          setState(() {
            _licenseInfo = licenseInfo;
            print('📝 License info loaded. Tier: ${licenseInfo?['tier']}, Is Paid: $isPaidUser');
          });
        }
      } catch (e) {
        print('❌ Error loading license info: $e');
        // Set default free tier if loading fails
        if (mounted) {
          setState(() {
            _licenseInfo = {
              'tier': 'free',
              'tier_name': 'Free',
              'meetings_per_month': 5,
              'max_file_size_mb': 25,
              'meetings_used': 0,
            };
          });
        }
      }
      
      // Load meeting stats separately
      try {
        final meetingStats = await _api.getMeetingStats();
        if (mounted) {
          setState(() {
            _meetingStats = meetingStats;
          });
        }
      } catch (e) {
        print('Error loading meeting stats: $e');
        if (mounted) {
          setState(() {
            _meetingStats = {
              'total_meetings': 0,
              'meetings_this_month': 0,
              'completed': 0,
              'processing': 0,
            };
          });
        }
      }
      
      if (mounted) {
        setState(() => _isLoading = false);
      }
    } catch (e) {
      print('Error loading data: $e');
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  void _navigateToUpload() async {
    await Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => const UploadScreen()),
    );
  }

  void _navigateToMeetings(String filter) async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => MeetingsListScreen(initialFilter: filter),
      ),
    );
  }

  bool get isPaidUser => _licenseInfo?['tier'] != null && _licenseInfo?['tier'] != 'free';
  String? get userEmail => _licenseInfo?['email'];
  String? get planName => _licenseInfo?['tier_name'];
  int get meetingsUsed => _licenseInfo?['meetings_used'] ?? 0;
  int get meetingsLimit => _licenseInfo?['meetings_per_month'] ?? 5;
  int get maxFileSizeMB => _licenseInfo?['max_file_size_mb'] ?? 25;
  
  int get totalMeetings => _meetingStats?['total_meetings'] ?? 0;
  int get meetingsThisMonth => _meetingStats?['meetings_this_month'] ?? 0;
  int get completedMeetings => _meetingStats?['completed'] ?? 0;
  int get processingMeetings => _meetingStats?['processing'] ?? 0;

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return Scaffold(
        body: Container(
          decoration: const BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [Color(0xFF667eea), Color(0xFF764ba2)],
            ),
          ),
          child: const Center(
            child: CircularProgressIndicator(
              valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
            ),
          ),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        title: Row(
          children: [
            Icon(Icons.mic, color: Colors.white, size: 24),
            const SizedBox(width: 8),
            const Text(
              'Clipnote',
              style: TextStyle(
                color: Colors.white,
                fontSize: 20,
                fontWeight: FontWeight.bold,
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () {
              Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const UserGuideScreen()),
              );
            },
            child: const Text(
              'Guide',
              style: TextStyle(color: Colors.white),
            ),
          ),
          const SizedBox(width: 8),
        ],
      ),
      extendBodyBehindAppBar: true,
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [Color(0xFF667eea), Color(0xFF764ba2)],
          ),
        ),
        child: SafeArea(
          child: RefreshIndicator(
            onRefresh: _loadData,
            color: const Color(0xFF667eea),
            child: ListView(
              padding: const EdgeInsets.all(20),
              children: [
                if (isPaidUser && userEmail != null) ...[
                  Container(
                    padding: const EdgeInsets.all(20),
                    decoration: BoxDecoration(
                      color: Colors.white.withOpacity(0.15),
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(
                        color: Colors.white.withOpacity(0.3),
                        width: 1,
                      ),
                    ),
                    child: Column(
                      children: [
                        Row(
                          children: [
                            const Icon(Icons.check_circle, color: Colors.white, size: 20),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                '${planName ?? 'Premium'} Active',
                                style: const TextStyle(color: Colors.white, fontSize: 14),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 16),
                        Row(
                          children: [
                            const CircleAvatar(
                              radius: 24,
                              backgroundColor: Colors.white,
                              child: Icon(Icons.person, color: Color(0xFF667eea)),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    userEmail ?? 'User',
                                    style: const TextStyle(
                                      color: Colors.white,
                                      fontSize: 16,
                                      fontWeight: FontWeight.w600,
                                    ),
                                  ),
                                  if (planName != null)
                                    Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                      decoration: BoxDecoration(
                                        color: Colors.white.withOpacity(0.3),
                                        borderRadius: BorderRadius.circular(12),
                                      ),
                                      child: Text(
                                        planName!,
                                        style: const TextStyle(color: Colors.white, fontSize: 12),
                                      ),
                                    ),
                                ],
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 16),
                        Row(
                          children: [
                            Expanded(
                              child: _statItem('This Month', '$meetingsThisMonth / $meetingsLimit'),
                            ),
                            Container(width: 1, height: 40, color: Colors.white.withOpacity(0.3)),
                            Expanded(
                              child: _statItem('Max File', '${maxFileSizeMB}MB'),
                            ),
                            Container(width: 1, height: 40, color: Colors.white.withOpacity(0.3)),
                            Expanded(
                              child: _statItem('Remaining', '${meetingsLimit - meetingsThisMonth}'),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 24),
                ] else ...[
                  Container(
                    padding: const EdgeInsets.all(24),
                    decoration: BoxDecoration(
                      color: Colors.white.withOpacity(0.15),
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(
                        color: Colors.white.withOpacity(0.3),
                        width: 1,
                      ),
                    ),
                    child: Column(
                      children: [
                        Text(
                          planName ?? 'Free Tier',
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 28,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 12),
                        Text(
                          '$meetingsLimit meetings per month\n${maxFileSizeMB}MB max file size',
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 16,
                          ),
                        ),
                        const SizedBox(height: 20),
                        SizedBox(
                          width: double.infinity,
                          child: ElevatedButton(
                            onPressed: _showUpgradeSheet,
                            style: ElevatedButton.styleFrom(
                              backgroundColor: Colors.white,
                              foregroundColor: const Color(0xFF667eea),
                              padding: const EdgeInsets.symmetric(vertical: 14),
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(30),
                              ),
                              elevation: 0,
                            ),
                            child: const Text(
                              'Upgrade',
                              style: TextStyle(
                                fontSize: 18,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 24),
                ],
                
                SizedBox(
                  height: 56,
                  child: ElevatedButton.icon(
                    onPressed: _navigateToUpload,
                    icon: const Icon(Icons.add_circle_outline, size: 24),
                    label: const Text(
                      'Create Meeting',
                      style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
                    ),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.white,
                      foregroundColor: const Color(0xFF667eea),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                      elevation: 2,
                    ),
                  ),
                ),
              
                const SizedBox(height: 24),
                
                Row(
                  children: [
                    Expanded(
                      child: _quickStatCard(
                        icon: Icons.description,
                        value: '$totalMeetings',
                        label: 'Total Meetings',
                        onTap: () => _navigateToMeetings('all'),
                      ),
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: _quickStatCard(
                        icon: Icons.check_circle,
                        value: '$completedMeetings',
                        label: 'Completed',
                        onTap: () => _navigateToMeetings('delivered'),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                Row(
                  children: [
                    Expanded(
                      child: _quickStatCard(
                        icon: Icons.calendar_month,
                        value: '$meetingsThisMonth',
                        label: 'This Month',
                        onTap: () => _navigateToMeetings('this_month'),
                      ),
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: _quickStatCard(
                        icon: Icons.hourglass_empty,
                        value: '$processingMeetings',
                        label: 'Processing',
                        onTap: () => _navigateToMeetings('processing'),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _statItem(String label, String value) {
    return Column(
      children: [
        Text(
          label,
          style: const TextStyle(
            color: Colors.white,
            fontSize: 11,
          ),
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: 4),
        Text(
          value,
          style: const TextStyle(
            color: Colors.white,
            fontSize: 18,
            fontWeight: FontWeight.bold,
          ),
        ),
      ],
    );
  }

  Widget _quickStatCard({
    required IconData icon,
    required String value,
    required String label,
    required VoidCallback onTap,
  }) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.15),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: Colors.white.withOpacity(0.3),
          width: 1,
        ),
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(12),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              children: [
                Icon(icon, color: Colors.white, size: 28),
                const SizedBox(height: 8),
                Text(
                  value,
                  style: const TextStyle(
                    fontSize: 24,
                    fontWeight: FontWeight.bold,
                    color: Colors.white,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  label,
                  style: const TextStyle(
                    fontSize: 12,
                    color: Colors.white,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  void _showUpgradeSheet() {
    showModalBottomSheet(
      context: context,
      showDragHandle: true,
      backgroundColor: Colors.white,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (c) => SafeArea(
        child: SingleChildScrollView(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(20, 8, 20, 20),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text(
                  'Choose Your Plan',
                  style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 20),
                _planTile(
                  context: c,
                  icon: Icons.verified,
                  title: 'Starter',
                  subtitle: '25 meetings per month\n50MB max file size',
                  price: _iapService.proProduct?.price ?? '\$29/month',
                  isPro: true,
                ),
                const SizedBox(height: 20),
                _planTile(
                  context: c,
                  icon: Icons.verified,
                  title: 'Professional',
                  subtitle: '50 meetings per month\n200MB max file size',
                  price: _iapService.proProduct?.price ?? '\$69/month',
                  isPro: true,
                ),
                const SizedBox(height: 12),
                _planTile(
                  context: c,
                  icon: Icons.business,
                  title: 'Business',
                  subtitle: '100 meetings per month\n500MB max file size',
                  price: _iapService.businessProduct?.price ?? '\$119/month',
                  isPro: false,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _planTile({
    required BuildContext context,
    required IconData icon,
    required String title,
    required String subtitle,
    required String price,
    required bool isPro,
  }) {
    return Container(
      decoration: BoxDecoration(
        border: Border.all(color: Colors.grey.shade300),
        borderRadius: BorderRadius.circular(16),
      ),
      child: ListTile(
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        leading: CircleAvatar(
          backgroundColor: const Color(0xFF667eea).withOpacity(0.1),
          child: Icon(icon, color: const Color(0xFF667eea)),
        ),
        title: Text(
          title,
          style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 16),
        ),
        subtitle: Text(subtitle, style: const TextStyle(fontSize: 13)),
        trailing: Text(
          price,
          style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
        ),
        onTap: () async {
          Navigator.pop(context);
          
          showDialog(
            context: this.context,
            barrierDismissible: false,
            builder: (c) => const Center(child: CircularProgressIndicator()),
          );
          
          try {
            final result = isPro 
                ? await _iapService.purchasePro()
                : await _iapService.purchaseBusiness();
            
            if (!mounted) return;
            Navigator.pop(this.context);
            
            ScaffoldMessenger.of(this.context).showSnackBar(
              SnackBar(
                content: Text('Purchase initiated: $result'),
                backgroundColor: Colors.green,
              ),
            );
          } catch (e) {
            if (!mounted) return;
            Navigator.pop(this.context);
            
            ScaffoldMessenger.of(this.context).showSnackBar(
              SnackBar(
                content: Text('Purchase failed: $e'),
                backgroundColor: Colors.red,
              ),
            );
          }
        },
      ),
    );
  }
}
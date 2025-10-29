// Example backend API for serving dynamic banner ads
// Install: npm install express body-parser

const express = require('express');
const bodyParser = require('body-parser');
const cors = require('cors');

const app = express();
app.use(cors()); // Add this for Flutter to access the API
app.use(bodyParser.json());

// Your banner database (in production, use a real database)
const banners = [
  {
    id: 'banner_001',
    image_url: 'https://ai-meeting-notes-production-81d7.up.railway.app/api/banner1.jpg',
    click_url: 'https://villiersjetcom?id=7275',
    title: 'Product 1',
    weight: 10,
    active: true
  },
  {
    id: 'banner_002',
    image_url: 'https://ai-meeting-notes-production-81d7.up.railway.app/api/banner2.jpg',
    click_url: 'https://villiersjetcom?id=7275',
    title: 'Product 2',
    weight: 5,
    active: true
  },
  {
    id: 'banner_003',
    image_url: 'https://ai-meeting-notes-production-81d7.up.railway.app/api/banner3.jpg',
    click_url: 'https://villiersjetcom?id=7275',
    title: 'Product 3',
    weight: 15,
    active: true
  },
  {
    id: 'banner_004',
    image_url: 'https://ai-meeting-notes-production-81d7.up.railway.app/api/banner4.jpg',
    click_url: 'https://villiersjetcom?id=7275',
    title: 'Product 4',
    weight: 10,
    active: true
  },
  {
    id: 'banner_005',
    image_url: 'https://ai-meeting-notes-production-81d7.up.railway.app/api/banner5.jpg',
    click_url: 'https://villiersjetcom?id=7275',
    title: 'Product 5',
    weight: 5,
    active: true
  },
  {
    id: 'banner_006',
    image_url: 'https://ai-meeting-notes-production-81d7.up.railway.app/api/banner6.jpg',
    click_url: 'https://villiersjetcom?id=7275',
    title: 'Product 6',
    weight: 15,
    active: true
  }
];

// Analytics storage (in production, use a real database)
const analytics = {
  impressions: {},
  clicks: {}
};

// ==============================================
// BANNER API ROUTES
// ==============================================

// GET /api/banners - Return all active banners
app.get('/api/banners', (req, res) => {
  try {
    const activeBanners = banners.filter(b => b.active);
    res.json(activeBanners);
  } catch (error) {
    console.error('Error fetching banners:', error);
    res.status(500).json({ error: 'Failed to fetch banners' });
  }
});

// POST /api/banners/impression - Track banner impression
app.post('/api/banners/impression', (req, res) => {
  try {
    const { banner_id } = req.body;
    
    if (!banner_id) {
      return res.status(400).json({ error: 'banner_id required' });
    }
    
    if (!bannerAnalytics.impressions[banner_id]) {
      bannerAnalytics.impressions[banner_id] = 0;
    }
    
    bannerAnalytics.impressions[banner_id]++;
    
    console.log(`👁️ Impression: ${banner_id} - Total: ${bannerAnalytics.impressions[banner_id]}`);
    
    res.json({ 
      success: true, 
      banner_id, 
      impressions: bannerAnalytics.impressions[banner_id] 
    });
  } catch (error) {
    console.error('Error recording impression:', error);
    res.status(500).json({ error: 'Failed to record impression' });
  }
});

// POST /api/banners/click - Track banner click
app.post('/api/banners/click', (req, res) => {
  try {
    const { banner_id } = req.body;
    
    if (!banner_id) {
      return res.status(400).json({ error: 'banner_id required' });
    }
    
    if (!bannerAnalytics.clicks[banner_id]) {
      bannerAnalytics.clicks[banner_id] = 0;
    }
    
    bannerAnalytics.clicks[banner_id]++;
    
    console.log(`🖱️ Click: ${banner_id} - Total: ${bannerAnalytics.clicks[banner_id]}`);
    
    res.json({ 
      success: true, 
      banner_id, 
      clicks: bannerAnalytics.clicks[banner_id] 
    });
  } catch (error) {
    console.error('Error recording click:', error);
    res.status(500).json({ error: 'Failed to record click' });
  }
});

// GET /api/banners/analytics - Get analytics data (admin only - add auth!)
app.get('/api/banners/analytics', (req, res) => {
  try {
    const data = banners.map(banner => {
      const impressions = bannerAnalytics.impressions[banner.id] || 0;
      const clicks = bannerAnalytics.clicks[banner.id] || 0;
      const ctr = impressions > 0 
        ? ((clicks / impressions) * 100).toFixed(2) + '%'
        : '0%';
      
      return {
        id: banner.id,
        title: banner.title,
        impressions,
        clicks,
        ctr,
        active: banner.active
      };
    });
    
    res.json(data);
  } catch (error) {
    console.error('Error fetching analytics:', error);
    res.status(500).json({ error: 'Failed to fetch analytics' });
  }
});

// ==============================================
// ADMIN ROUTES (Add authentication middleware!)
// ==============================================

// POST /api/banners - Add new banner
app.post('/api/banners', (req, res) => {
  try {
    const { image_url, click_url, title, weight } = req.body;
    
    if (!image_url || !click_url) {
      return res.status(400).json({ error: 'image_url and click_url required' });
    }
    
    const newBanner = {
      id: `banner_${Date.now()}`,
      image_url,
      click_url,
      title: title || 'New Banner',
      weight: weight || 1,
      active: true
    };
    
    banners.push(newBanner);
    
    console.log(`✨ New banner created: ${newBanner.id}`);
    
    res.json({ success: true, banner: newBanner });
  } catch (error) {
    console.error('Error creating banner:', error);
    res.status(500).json({ error: 'Failed to create banner' });
  }
});

// PATCH /api/banners/:id - Update banner
app.patch('/api/banners/:id', (req, res) => {
  try {
    const { id } = req.params;
    const updates = req.body;
    
    const bannerIndex = banners.findIndex(b => b.id === id);
    
    if (bannerIndex === -1) {
      return res.status(404).json({ error: 'Banner not found' });
    }
    
    banners[bannerIndex] = { ...banners[bannerIndex], ...updates };
    
    console.log(`📝 Banner updated: ${id}`);
    
    res.json({ success: true, banner: banners[bannerIndex] });
  } catch (error) {
    console.error('Error updating banner:', error);
    res.status(500).json({ error: 'Failed to update banner' });
  }
});

// DELETE /api/banners/:id - Deactivate banner
app.delete('/api/banners/:id', (req, res) => {
  try {
    const { id } = req.params;
    
    const banner = banners.find(b => b.id === id);
    
    if (!banner) {
      return res.status(404).json({ error: 'Banner not found' });
    }
    
    banner.active = false;
    
    console.log(`🗑️ Banner deactivated: ${id}`);
    
    res.json({ success: true, banner });
  } catch (error) {
    console.error('Error deleting banner:', error);
    res.status(500).json({ error: 'Failed to delete banner' });
  }
});

console.log('🎯 Banner routes initialized');
console.log(`📊 Active banners: ${banners.filter(b => b.active).length}`);
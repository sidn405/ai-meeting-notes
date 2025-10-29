// Example backend API for serving dynamic banner ads
// Install: npm install express body-parser

const express = require('express');
const bodyParser = require('body-parser');

const app = express();
app.use(bodyParser.json());

// Your banner database (in production, use a real database)
const banners = [
  {
    id: 'banner_001',
    image_url: 'https://your-cdn.com/banner1.jpg',
    click_url: 'https://villiersjetcom?id=7275',
    title: 'Product 1',
    weight: 10,
    active: true
  },
  {
    id: 'banner_002',
    image_url: 'https://your-cdn.com/banner2.jpg',
    click_url: 'https://villiersjetcom?id=7275',
    title: 'Product 2',
    weight: 5,
    active: true
  },
  {
    id: 'banner_003',
    image_url: 'https://your-cdn.com/banner3.jpg',
    click_url: 'https://villiersjetcom?id=7275',
    title: 'Product 3',
    weight: 15,
    active: true
  }
];

// Analytics storage (in production, use a real database)
const analytics = {
  impressions: {},
  clicks: {}
};

// GET /api/banners - Return all active banners
app.get('/api/banners', (req, res) => {
  const activeBanners = banners.filter(b => b.active);
  res.json(activeBanners);
});

// POST /api/banners/impression - Track banner impression
app.post('/api/banners/impression', (req, res) => {
  const { banner_id } = req.body;
  
  if (!banner_id) {
    return res.status(400).json({ error: 'banner_id required' });
  }
  
  if (!analytics.impressions[banner_id]) {
    analytics.impressions[banner_id] = 0;
  }
  
  analytics.impressions[banner_id]++;
  
  console.log(`Impression recorded for banner ${banner_id}. Total: ${analytics.impressions[banner_id]}`);
  
  res.json({ success: true, banner_id, impressions: analytics.impressions[banner_id] });
});

// POST /api/banners/click - Track banner click
app.post('/api/banners/click', (req, res) => {
  const { banner_id } = req.body;
  
  if (!banner_id) {
    return res.status(400).json({ error: 'banner_id required' });
  }
  
  if (!analytics.clicks[banner_id]) {
    analytics.clicks[banner_id] = 0;
  }
  
  analytics.clicks[banner_id]++;
  
  console.log(`Click recorded for banner ${banner_id}. Total: ${analytics.clicks[banner_id]}`);
  
  res.json({ success: true, banner_id, clicks: analytics.clicks[banner_id] });
});

// GET /api/banners/analytics - Get analytics data
app.get('/api/banners/analytics', (req, res) => {
  const data = banners.map(banner => ({
    id: banner.id,
    title: banner.title,
    impressions: analytics.impressions[banner.id] || 0,
    clicks: analytics.clicks[banner.id] || 0,
    ctr: analytics.impressions[banner.id] > 0 
      ? ((analytics.clicks[banner.id] || 0) / analytics.impressions[banner.id] * 100).toFixed(2) + '%'
      : '0%'
  }));
  
  res.json(data);
});

// POST /api/banners - Add new banner (admin endpoint - add auth in production)
app.post('/api/banners', (req, res) => {
  const { image_url, click_url, title, weight } = req.body;
  
  const newBanner = {
    id: `banner_${Date.now()}`,
    image_url,
    click_url,
    title,
    weight: weight || 1,
    active: true
  };
  
  banners.push(newBanner);
  
  res.json({ success: true, banner: newBanner });
});

// PATCH /api/banners/:id - Update banner (admin endpoint)
app.patch('/api/banners/:id', (req, res) => {
  const { id } = req.params;
  const updates = req.body;
  
  const bannerIndex = banners.findIndex(b => b.id === id);
  
  if (bannerIndex === -1) {
    return res.status(404).json({ error: 'Banner not found' });
  }
  
  banners[bannerIndex] = { ...banners[bannerIndex], ...updates };
  
  res.json({ success: true, banner: banners[bannerIndex] });
});

// DELETE /api/banners/:id - Deactivate banner (admin endpoint)
app.delete('/api/banners/:id', (req, res) => {
  const { id } = req.params;
  
  const banner = banners.find(b => b.id === id);
  
  if (!banner) {
    return res.status(404).json({ error: 'Banner not found' });
  }
  
  banner.active = false;
  
  res.json({ success: true, banner });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Banner API running on port ${PORT}`);
  console.log(`Active banners: ${banners.filter(b => b.active).length}`);
});

module.exports = app;
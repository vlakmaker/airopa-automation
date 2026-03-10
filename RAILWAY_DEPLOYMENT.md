# Railway Deployment Guide

## Quick Deploy to Railway

### Step 1: Sign Up / Log In
1. Go to [railway.app](https://railway.app)
2. Sign up with GitHub (recommended)

### Step 2: Create New Project
1. Click "New Project"
2. Select "Deploy from GitHub repo"
3. Choose `vlakmaker/airopa-automation`
4. Railway will auto-detect the configuration

### Step 3: Configure Environment (Optional)
Railway will automatically set `PORT` - no configuration needed for MVP!

For production, you can add:
- `DATABASE_URL` - If using PostgreSQL instead of SQLite
- `API_DEBUG` - Set to `false` for production

### Step 4: Deploy
- Railway will automatically build and deploy
- You'll get a public URL like: `https://api.airopa.news`

### Step 5: Verify Deployment
Once deployed, test these endpoints:

```bash
# Health check
curl https://api.airopa.news/api/health

# List articles (will be empty initially)
curl https://api.airopa.news/api/articles

# Trigger scraping
curl -X POST https://api.airopa.news/api/scrape

# API docs
open https://api.airopa.news/docs
```

## Automatic Features

✅ **Auto-deployment**: Every push to `main` triggers a new deployment
✅ **HTTPS**: Automatic SSL certificates
✅ **Database**: SQLite database persists in Railway volumes
✅ **Logs**: View logs in Railway dashboard
✅ **Metrics**: CPU, memory, and request metrics

## Database Persistence

Railway uses ephemeral filesystems, so for production you should:

### Option A: Add PostgreSQL (Recommended)
1. In Railway dashboard, click "New" → "Database" → "PostgreSQL"
2. Railway will set `DATABASE_URL` automatically
3. Update `airopa_automation/api/models/database.py` to use `DATABASE_URL`

### Option B: Use Railway Volumes (SQLite)
1. In Railway settings, add a volume
2. Mount to `/app/database`
3. SQLite database will persist across deploys

## CORS Configuration

The API is pre-configured with CORS for:
- `http://localhost:5173` (Vite dev)
- `http://localhost:3000` (React dev)

To add your frontend domain:
1. Go to Railway → Variables
2. Add `FRONTEND_URL=https://yourfrontend.com`
3. Update `airopa_automation/api/main.py` to use this variable

## Costs

Railway offers:
- **$5 free credit** per month (hobby plan)
- Enough for MVP testing and development
- ~550 hours of runtime

## Troubleshooting

### View Logs
Railway Dashboard → Deployments → Click deployment → Logs

### Common Issues

**Build fails**: Check that all dependencies are in `requirements.txt`

**Database not initialized**: Check logs for initialization errors

**CORS errors**: Add your frontend URL to CORS allowed origins

## Monitoring

Access your Railway dashboard to monitor:
- Request count and latency
- Memory and CPU usage
- Deployment history
- Live logs

## Next Steps After Deployment

1. **Test all endpoints** using the Railway URL
2. **Update frontend** to use Railway API URL
3. **Set up PostgreSQL** for production persistence
4. **Configure custom domain** (optional)
5. **Add monitoring** (Railway provides basic metrics)

Your API is now live and accessible! 🚀

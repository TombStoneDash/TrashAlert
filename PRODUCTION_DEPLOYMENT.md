# TrashAlert Production Deployment Guide

Complete guide for deploying TrashAlert to production using modern cloud platforms.

## 🎯 Overview

This production deployment includes:
- **API**: Deployed to Railway with managed PostgreSQL
- **Admin Dashboard**: Deployed to Vercel
- **CI/CD**: GitHub Actions for automated testing and deployment
- **Monitoring**: Uptime monitoring and health checks
- **Database**: Managed PostgreSQL on Railway

## 📋 Prerequisites

- GitHub account with repository access
- Railway account (https://railway.app)
- Vercel account (https://vercel.com)
- Domain name (optional but recommended)
- Email for notifications

## 🚀 Deployment Steps

### 1. Database Setup (Railway PostgreSQL)

1. **Create Railway Account**
   - Visit https://railway.app
   - Sign in with GitHub

2. **Create New Project**
   ```bash
   # Create a new Railway project
   railway init
   ```

3. **Add PostgreSQL Database**
   - In Railway dashboard: `New` → `Database` → `PostgreSQL`
   - Railway will automatically provision a PostgreSQL instance
   - Copy the `DATABASE_URL` from the PostgreSQL service

4. **Configure Database Connection**
   - Database URL format: `postgresql://user:password@host:port/database`
   - Save this for the API deployment step

### 2. API Deployment (Railway)

1. **Connect GitHub Repository**
   - In Railway dashboard: `New` → `GitHub Repo`
   - Select `TrashAlert` repository
   - Railway will detect the `railway.toml` and `Dockerfile`

2. **Configure Environment Variables**

   In Railway project settings, add these variables:

   ```env
   DATABASE_URL=postgresql://... (from step 1)
   ENVIRONMENT=production
   LOG_LEVEL=info
   ALLOWED_ORIGINS=https://your-dashboard.vercel.app
   ```

3. **Configure Custom Domain (Optional)**
   - In Railway service settings: `Settings` → `Domains`
   - Add custom domain or use Railway's provided domain
   - Update DNS records as instructed

4. **Deploy**
   ```bash
   # Deploy using Railway CLI
   railway up

   # Or push to main branch for automatic deployment
   git push origin main
   ```

5. **Run Database Migrations**
   ```bash
   # Connect to Railway and run migrations
   railway run alembic upgrade head
   ```

6. **Verify Deployment**
   ```bash
   # Check health endpoint
   curl https://your-api.railway.app/health

   # Expected response:
   # {"status":"ok","database":"connected"}
   ```

### 3. Admin Dashboard Deployment (Vercel)

1. **Install Vercel CLI**
   ```bash
   npm install -g vercel
   ```

2. **Login to Vercel**
   ```bash
   vercel login
   ```

3. **Configure Environment Variables**

   Create `.env.production` in `frontend/admin-dashboard/`:

   ```env
   VITE_API_BASE_URL=https://your-api.railway.app
   VITE_DEV_AUTH_BYPASS=false
   ```

4. **Deploy to Vercel**
   ```bash
   cd frontend/admin-dashboard
   vercel --prod
   ```

5. **Configure Custom Domain (Optional)**
   - In Vercel project settings: `Settings` → `Domains`
   - Add your custom domain
   - Update DNS records as instructed

6. **Set Production Environment Variables in Vercel**
   - Go to Vercel dashboard: `Settings` → `Environment Variables`
   - Add `VITE_API_BASE_URL` with your Railway API URL
   - Add `VITE_DEV_AUTH_BYPASS=false`

7. **Redeploy with Variables**
   ```bash
   vercel --prod
   ```

### 4. GitHub Actions CI/CD Setup

1. **Configure GitHub Secrets**

   Go to GitHub repository: `Settings` → `Secrets and variables` → `Actions`

   Add these secrets:

   ```
   RAILWAY_TOKEN          # Get from Railway account settings
   API_URL                # Your Railway API URL
   VERCEL_TOKEN           # Get from Vercel account settings
   VERCEL_ORG_ID          # Get from Vercel project settings
   VERCEL_PROJECT_ID      # Get from Vercel project settings
   FRONTEND_URL           # Your Vercel dashboard URL
   SLACK_WEBHOOK_URL      # Optional: For Slack notifications
   ```

2. **Get Railway Token**
   ```bash
   # Login to Railway CLI
   railway login

   # Get token from account settings
   # https://railway.app/account/tokens
   ```

3. **Get Vercel Credentials**
   ```bash
   # Link project to get IDs
   cd frontend/admin-dashboard
   vercel link

   # Get token from Vercel account
   # https://vercel.com/account/tokens
   ```

4. **Test Workflows**
   - Push to `main` branch to trigger deployment
   - Check Actions tab in GitHub to monitor progress
   - Workflows will automatically:
     - Run tests on push/PR
     - Deploy API to Railway on main push
     - Deploy frontend to Vercel on main push
     - Monitor uptime every 5 minutes

### 5. Uptime Monitoring Setup

#### Option A: GitHub Actions (Free)

Already configured! The uptime monitoring workflow runs every 5 minutes and:
- Checks API health endpoint
- Checks frontend availability
- Creates GitHub issue on failure
- Sends Slack notification (if configured)

#### Option B: Better Stack (Recommended)

1. **Sign up for Better Stack**
   - Visit https://betterstack.com/uptime
   - Create account (free tier available)

2. **Create Monitors**
   - API Health: `https://your-api.railway.app/health`
   - API Lookup: `https://your-api.railway.app/lookup?address=test`
   - Dashboard: `https://your-dashboard.vercel.app`
   - SSL Certificate check

3. **Configure Alerts**
   - Email notifications
   - Slack integration
   - SMS (paid plans)
   - PagerDuty integration

4. **Use Configuration File**
   - Import `monitoring/betterstack-config.yml` as a template
   - Update URLs with your actual deployment URLs

#### Option C: Uptime Kuma (Self-hosted)

1. **Deploy Uptime Kuma**
   ```bash
   # Deploy on Railway
   railway add
   # Select "Uptime Kuma" template
   ```

2. **Configure Monitors**
   - Import `monitoring/uptime-kuma-config.json`
   - Update URLs with your deployment URLs

3. **Set up Notifications**
   - Email, Slack, Discord, Telegram, etc.
   - Configure in Uptime Kuma settings

## 🔒 Security Configuration

### 1. Environment Variables

Never commit these files:
- `.env`
- `.env.production`
- Any files containing secrets

They should be in `.gitignore` (already configured).

### 2. CORS Configuration

Update allowed origins in Railway environment variables:
```env
ALLOWED_ORIGINS=https://your-dashboard.vercel.app,https://yourdomain.com
```

### 3. Database Security

Railway PostgreSQL includes:
- Automatic backups
- SSL/TLS encryption
- Private networking

### 4. API Rate Limiting

Configure in `app/rate_limiter.py`:
```python
rate_limit = "100/hour"  # Adjust as needed
```

## 📊 Monitoring and Logging

### View Railway Logs

```bash
# View API logs
railway logs

# Follow logs in real-time
railway logs --follow
```

### View Vercel Logs

```bash
# View deployment logs
vercel logs

# Follow logs in real-time
vercel logs --follow
```

### GitHub Actions Logs

- Go to repository `Actions` tab
- Click on any workflow run
- View detailed logs for each step

### Metrics Endpoint

```bash
# View API metrics
curl https://your-api.railway.app/metrics
```

Returns Prometheus-compatible metrics:
- Request counts
- Response times
- Database query performance
- Error rates

## 🔧 Management Tasks

### Update API

```bash
# Push to main branch
git add .
git commit -m "Update API"
git push origin main

# Or deploy directly via Railway CLI
railway up
```

### Update Dashboard

```bash
# Push to main branch (auto-deploys via GitHub Actions)
git push origin main

# Or deploy directly
cd frontend/admin-dashboard
vercel --prod
```

### Run Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "Description"

# Apply migrations on Railway
railway run alembic upgrade head
```

### Rollback Deployment

**Railway:**
```bash
# View deployments
railway status

# Rollback to previous deployment
railway rollback
```

**Vercel:**
```bash
# View deployments
vercel ls

# Promote a previous deployment
vercel promote <deployment-url>
```

## 🐛 Troubleshooting

### API Not Responding

1. **Check Railway Logs**
   ```bash
   railway logs --tail 100
   ```

2. **Check Database Connection**
   ```bash
   railway run python -c "from app.database import engine; print(engine.url)"
   ```

3. **Restart Service**
   ```bash
   railway restart
   ```

### Frontend Build Failures

1. **Check Vercel Logs**
   ```bash
   vercel logs
   ```

2. **Verify Environment Variables**
   - Ensure `VITE_API_BASE_URL` is set correctly

3. **Test Build Locally**
   ```bash
   cd frontend/admin-dashboard
   npm run build
   ```

### Database Migration Issues

1. **Check Current Migration Version**
   ```bash
   railway run alembic current
   ```

2. **View Migration History**
   ```bash
   railway run alembic history
   ```

3. **Rollback Migration**
   ```bash
   railway run alembic downgrade -1
   ```

### Uptime Monitoring False Positives

1. **Check Service Health**
   ```bash
   curl -v https://your-api.railway.app/health
   ```

2. **Adjust Monitoring Intervals**
   - Increase retry count
   - Increase timeout values
   - Adjust check frequency

## 📈 Scaling

### Railway Scaling

1. **Vertical Scaling**
   - In Railway project settings: `Settings` → `Resources`
   - Increase memory/CPU allocation

2. **Horizontal Scaling**
   - Railway auto-scales based on load
   - Configure replicas in project settings

3. **Database Scaling**
   - Upgrade PostgreSQL plan in Railway
   - Enable read replicas for high traffic

### Vercel Scaling

- Vercel automatically scales to handle traffic
- Edge network distribution included
- No configuration needed

## 💰 Cost Estimation

### Railway (Hobby Plan - $5/month)

- API hosting: ~$5/month
- PostgreSQL: ~$5/month
- **Total**: ~$10/month

### Vercel (Free Tier)

- Frontend hosting: Free
- 100GB bandwidth/month
- Upgrade to Pro ($20/month) for:
  - 1TB bandwidth
  - Custom domains
  - Advanced analytics

### Better Stack (Free Tier)

- Up to 10 monitors
- 3-minute check interval
- Email notifications
- Upgrade to paid plans for:
  - More monitors
  - Faster checks
  - SMS/Phone alerts
  - Advanced integrations

**Total Minimum Cost**: ~$10/month (Railway only)

## 🎉 Success Criteria

Your deployment is successful when:

- ✅ API responds at production URL: `https://your-api.railway.app/health`
- ✅ Admin dashboard loads: `https://your-dashboard.vercel.app`
- ✅ Database migrations completed successfully
- ✅ GitHub Actions workflows passing
- ✅ Uptime monitoring active and alerting
- ✅ SSL certificates valid (automatic via Railway/Vercel)
- ✅ Logs accessible and streaming
- ✅ Metrics endpoint returning data

## 📝 Post-Deployment Checklist

### Day 1
- [ ] Verify all endpoints responding
- [ ] Test admin dashboard functionality
- [ ] Check logs for errors
- [ ] Verify uptime monitoring alerts
- [ ] Test notification channels

### Week 1
- [ ] Monitor error rates and performance
- [ ] Review database query performance
- [ ] Check resource usage and costs
- [ ] Verify backup systems working
- [ ] Document any issues or optimizations

### Monthly
- [ ] Review and analyze metrics
- [ ] Update dependencies
- [ ] Review security advisories
- [ ] Optimize database queries
- [ ] Review and adjust monitoring thresholds
- [ ] Check SSL certificate expiration

## 🆘 Support Resources

- **Railway**: https://docs.railway.app
- **Vercel**: https://vercel.com/docs
- **GitHub Actions**: https://docs.github.com/en/actions
- **Better Stack**: https://betterstack.com/docs
- **TrashAlert Issues**: https://github.com/your-org/trashalert/issues

## 🔄 Next Steps

After successful deployment:

1. **Set up custom domain** for both API and dashboard
2. **Configure DNS** records (CNAME for Railway, A/AAAA for Vercel)
3. **Enable production monitoring** dashboards
4. **Set up error tracking** (Sentry, Rollbar, etc.)
5. **Configure backup strategy** for database
6. **Document incident response** procedures
7. **Set up performance monitoring** (New Relic, DataDog, etc.)
8. **Enable security scanning** (Snyk, Dependabot)

---

**Questions?** Open an issue or check the main [README.md](README.md).

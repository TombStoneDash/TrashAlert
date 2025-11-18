# TrashAlert Production Deployment Checklist

Use this checklist to ensure a smooth production deployment.

## Pre-Deployment

### Accounts & Access
- [ ] Railway account created (https://railway.app)
- [ ] Vercel account created (https://vercel.com)
- [ ] GitHub repository access confirmed
- [ ] Domain registrar access (if using custom domain)
- [ ] Email configured for alerts

### Development Environment
- [ ] All tests passing locally
- [ ] Code committed and pushed to GitHub
- [ ] Latest changes merged to `main` branch
- [ ] Environment variables documented
- [ ] Secrets identified and secured

### Documentation Review
- [ ] Read PRODUCTION_DEPLOYMENT.md
- [ ] Review Railway and Vercel documentation
- [ ] Understand GitHub Actions workflows
- [ ] Review monitoring options

## Database Setup

- [ ] Railway project created
- [ ] PostgreSQL database provisioned
- [ ] DATABASE_URL copied from Railway
- [ ] Database credentials secured
- [ ] Connection string tested
- [ ] Initial migration plan reviewed

## API Deployment (Railway)

### Configuration
- [ ] GitHub repository connected to Railway
- [ ] `railway.toml` configuration verified
- [ ] `Dockerfile` tested locally
- [ ] `Procfile` commands verified

### Environment Variables
- [ ] `DATABASE_URL` configured
- [ ] `ENVIRONMENT=production` set
- [ ] `LOG_LEVEL=info` set
- [ ] `ALLOWED_ORIGINS` configured with dashboard URL
- [ ] Any API keys/secrets added (if needed)

### Deployment
- [ ] Railway CLI installed (`npm install -g @railway/cli`)
- [ ] Logged into Railway (`railway login`)
- [ ] Initial deployment successful (`railway up`)
- [ ] Database migrations run (`railway run alembic upgrade head`)
- [ ] Health endpoint responding (`/health`)
- [ ] API documentation accessible (`/docs`)
- [ ] Sample API calls working

### Domain Setup (Optional)
- [ ] Custom domain added in Railway
- [ ] DNS records configured
- [ ] SSL certificate provisioned
- [ ] HTTPS working correctly

## Frontend Deployment (Vercel)

### Configuration
- [ ] Vercel CLI installed (`npm install -g vercel`)
- [ ] Logged into Vercel (`vercel login`)
- [ ] `.env.production` created with API URL
- [ ] `vercel.json` configuration reviewed

### Environment Variables
- [ ] `VITE_API_BASE_URL` set to Railway API URL
- [ ] `VITE_DEV_AUTH_BYPASS=false` set
- [ ] Environment variables added in Vercel dashboard

### Deployment
- [ ] Dependencies installed (`npm ci`)
- [ ] Build successful locally (`npm run build`)
- [ ] Deployed to Vercel (`vercel --prod`)
- [ ] Dashboard accessible in browser
- [ ] API integration working
- [ ] All pages loading correctly
- [ ] No console errors

### Domain Setup (Optional)
- [ ] Custom domain added in Vercel
- [ ] DNS records configured
- [ ] SSL certificate auto-provisioned
- [ ] HTTPS working correctly

## CI/CD Setup (GitHub Actions)

### Secrets Configuration
- [ ] `RAILWAY_TOKEN` added to GitHub secrets
- [ ] `API_URL` added to GitHub secrets
- [ ] `VERCEL_TOKEN` added to GitHub secrets
- [ ] `VERCEL_ORG_ID` added to GitHub secrets
- [ ] `VERCEL_PROJECT_ID` added to GitHub secrets
- [ ] `FRONTEND_URL` added to GitHub secrets
- [ ] `SLACK_WEBHOOK_URL` added (optional)

### Workflows
- [ ] `.github/workflows/ci.yml` - Tests running
- [ ] `.github/workflows/deploy-api.yml` - API deploys on push
- [ ] `.github/workflows/deploy-frontend.yml` - Dashboard deploys on push
- [ ] `.github/workflows/uptime-monitoring.yml` - Monitoring active
- [ ] All workflows passing
- [ ] Deployment workflows triggered on push to main

### Testing
- [ ] Push test commit to trigger workflows
- [ ] Verify CI tests run successfully
- [ ] Verify deployments complete
- [ ] Check GitHub Actions logs for errors

## Monitoring Setup

### Choose Monitoring Solution
- [ ] Option selected (GitHub Actions / Better Stack / Uptime Kuma)

### GitHub Actions Monitoring (Free)
- [ ] Uptime workflow running every 5 minutes
- [ ] Health checks configured
- [ ] Issue creation on failure tested
- [ ] Slack notifications configured (optional)

### Better Stack (Recommended)
- [ ] Account created
- [ ] API health monitor created
- [ ] Frontend monitor created
- [ ] SSL certificate monitor created
- [ ] Email notifications configured
- [ ] Slack integration set up (optional)
- [ ] Test alert sent and received

### Uptime Kuma (Self-hosted)
- [ ] Deployed to Railway/other platform
- [ ] Monitors imported from config
- [ ] Notifications configured
- [ ] Test alert sent and received

## Security & Compliance

### Access Control
- [ ] Production database credentials secured
- [ ] API keys stored in environment variables only
- [ ] `.env` files in `.gitignore`
- [ ] GitHub secrets properly configured
- [ ] Team access levels reviewed

### CORS & Security Headers
- [ ] CORS configured with specific origins
- [ ] Rate limiting enabled and tested
- [ ] Security headers configured
- [ ] HTTPS enforced

### Backups
- [ ] Database backup strategy defined
- [ ] Railway automatic backups enabled
- [ ] Manual backup tested
- [ ] Restore procedure documented

## Performance & Scaling

### Load Testing
- [ ] API response times acceptable
- [ ] Database query performance reviewed
- [ ] Frontend load time acceptable
- [ ] Error rates at acceptable levels

### Resource Monitoring
- [ ] Railway resource usage reviewed
- [ ] Memory usage within limits
- [ ] CPU usage within limits
- [ ] Database connection pool sized appropriately

### Scaling Configuration
- [ ] Railway scaling limits configured
- [ ] Worker count optimized
- [ ] Database plan appropriate for traffic

## Post-Deployment Verification

### Functional Testing
- [ ] All API endpoints responding
- [ ] Admin dashboard fully functional
- [ ] Database queries working
- [ ] Authentication working (if applicable)
- [ ] File uploads working (if applicable)
- [ ] Background jobs running (if applicable)

### Performance Testing
- [ ] API response times < 500ms
- [ ] Database queries optimized
- [ ] Frontend load time < 3s
- [ ] No memory leaks detected

### Monitoring Verification
- [ ] Health checks passing
- [ ] Metrics being collected
- [ ] Logs accessible and streaming
- [ ] Alerts configured and tested
- [ ] Error tracking working

### User Testing
- [ ] Invite beta users (if applicable)
- [ ] Collect initial feedback
- [ ] Monitor for errors
- [ ] Review user experience

## Documentation

### Update Documentation
- [ ] Production URLs documented
- [ ] Environment variables documented
- [ ] Deployment process documented
- [ ] Incident response procedures documented
- [ ] Monitoring dashboards documented

### Team Enablement
- [ ] Team notified of deployment
- [ ] Access credentials shared securely
- [ ] Dashboard URLs shared
- [ ] Monitoring access granted
- [ ] On-call rotation established (if applicable)

## Ongoing Maintenance

### Daily
- [ ] Review error logs
- [ ] Check uptime monitoring
- [ ] Verify backup completion
- [ ] Monitor performance metrics

### Weekly
- [ ] Review and address GitHub issues
- [ ] Check for dependency updates
- [ ] Review security advisories
- [ ] Analyze usage metrics

### Monthly
- [ ] Update dependencies
- [ ] Review and optimize database
- [ ] Check SSL certificate expiration
- [ ] Review and optimize costs
- [ ] Security audit
- [ ] Performance optimization review

## Rollback Plan

### If Issues Occur
- [ ] Rollback procedure documented
- [ ] Railway rollback tested (`railway rollback`)
- [ ] Vercel rollback tested (`vercel promote <previous-deployment>`)
- [ ] Database rollback procedure documented
- [ ] Emergency contacts list prepared
- [ ] Communication plan for outages prepared

## Launch

### Pre-Launch
- [ ] All checklist items above completed
- [ ] Final security review
- [ ] Final performance review
- [ ] Team briefing completed
- [ ] Support team ready

### Launch Day
- [ ] Monitor closely for first 24 hours
- [ ] Be available for quick fixes
- [ ] Communicate with users
- [ ] Document any issues
- [ ] Celebrate! 🎉

### Post-Launch (Week 1)
- [ ] Daily monitoring and optimization
- [ ] Collect and address user feedback
- [ ] Fix any bugs found
- [ ] Optimize based on real usage
- [ ] Document lessons learned

## Success Metrics

Define and track these metrics:

- [ ] API uptime target: ____% (recommend: 99.9%)
- [ ] API response time target: ____ms (recommend: <500ms)
- [ ] Frontend load time target: ____s (recommend: <3s)
- [ ] Error rate target: ____% (recommend: <1%)
- [ ] User satisfaction target: ____% (recommend: >90%)

## Notes

Use this section for deployment-specific notes:

```
Date: _______________
API URL: _____________________________
Dashboard URL: _______________________
Database: ____________________________
Deployed by: _________________________
Notes:
```

---

**Deployment Status**: [ ] Not Started [ ] In Progress [ ] Completed [ ] Verified

**Last Updated**: _______________

**Next Review**: _______________

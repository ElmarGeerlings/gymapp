# 🔍 Health Check Troubleshooting Guide

## What are Health Checks?

Health checks are Railway's way of testing if your app is running properly. Railway sends a request to your app and expects a response. If your app doesn't respond correctly, Railway marks it as "failing health checks."

## What I've Fixed

1. **Added a dedicated health check endpoint** at `/health/` that returns a simple "OK" response
2. **Updated Railway configuration** to use this endpoint for health checks
3. **Increased timeout** to 300 seconds to give your app more time to start
4. **Added better Gunicorn configuration** with workers and timeout settings

## How to Test Locally

Before deploying, test your health check locally:

```bash
# Start your Django server
python manage.py runserver

# Test the health check endpoint
curl http://localhost:8000/health/
```

You should see: `OK`

## Common Health Check Issues

### 1. App Not Starting
**Symptoms**: Health checks fail immediately
**Solutions**:
- Check Railway logs for startup errors
- Verify all environment variables are set
- Make sure `SECRET_KEY` is set
- Check that `DATABASE_URL` is properly configured

### 2. Database Connection Issues
**Symptoms**: App starts but health checks fail
**Solutions**:
- Ensure PostgreSQL service is added to Railway project
- Check that `DATABASE_URL` is automatically set by Railway
- Verify database service is running

### 3. Static Files Issues
**Symptoms**: App starts but pages don't load properly
**Solutions**:
- Check that `collectstatic` is running during deployment
- Verify `STATIC_ROOT` is set correctly
- Make sure WhiteNoise is configured properly

### 4. Port Binding Issues
**Symptoms**: App can't bind to the port
**Solutions**:
- Make sure Gunicorn is binding to `0.0.0.0:$PORT`
- Check that the port is available

## Railway Dashboard Steps

1. **Go to your Railway project**
2. **Click on your app service**
3. **Check the "Deployments" tab** for recent deployment logs
4. **Look for error messages** in the logs
5. **Check the "Variables" tab** to ensure all environment variables are set

## Environment Variables Checklist

Make sure these are set in Railway:

```
DEBUG=False
SECRET_KEY=your-secret-key-here
DATABASE_URL=postgresql://... (auto-set by Railway)
REDIS_URL=redis://... (auto-set by Railway)
ALLOWED_HOSTS=your-app-name.railway.app
```

## Manual Health Check Test

Once deployed, you can manually test your health check:

1. **Get your app URL** from Railway dashboard
2. **Add `/health/` to the URL**
3. **You should see "OK"**

Example: `https://your-app-name.railway.app/health/`

## If Health Checks Still Fail

1. **Check Railway logs** for specific error messages
2. **Test the health endpoint manually** in your browser
3. **Verify all services are running** (PostgreSQL, Redis)
4. **Check that migrations completed successfully**
5. **Ensure static files were collected**

## Quick Fix Commands

If you need to run commands manually in Railway:

```bash
# Check if app is running
ps aux | grep gunicorn

# Test database connection
python manage.py dbshell

# Run migrations manually
python manage.py migrate --noinput

# Collect static files
python manage.py collectstatic --noinput

# Test health endpoint
curl http://localhost:$PORT/health/
```

## Still Having Issues?

1. **Share the Railway deployment logs** - they contain specific error messages
2. **Check if your app starts locally** with the same environment variables
3. **Verify your `requirements.txt`** has all necessary dependencies
4. **Make sure your code is pushed to GitHub** and Railway is deploying the latest version

---

💡 **Pro Tip**: The health check endpoint I added (`/health/`) is very simple and should always work. If it's failing, there's likely a fundamental issue with your app startup or configuration.

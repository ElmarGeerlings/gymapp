# 🚀 Deploying Gainz App to Railway

This guide will help you deploy your Django gym app to Railway so you can access it from your phone.

## Prerequisites

1. **GitHub Account**: Your code should be in a GitHub repository
2. **Railway Account**: Sign up at [railway.app](https://railway.app) (free tier available)

## Step 1: Prepare Your Code

Your code is already prepared with the necessary deployment files:
- `Procfile` - Tells Railway how to run your app
- `railway.json` - Railway-specific configuration
- `runtime.txt` - Python version specification
- Updated `settings.py` - Production-ready settings

## Step 2: Deploy to Railway

### Option A: Using Railway Dashboard (Recommended)

1. **Go to Railway Dashboard**
   - Visit [railway.app](https://railway.app)
   - Sign in with your GitHub account

2. **Create New Project**
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your gymapp repository

3. **Add Services**
   - **PostgreSQL Database**: Click "Add Service" → "Database" → "PostgreSQL"
   - **Redis Cache**: Click "Add Service" → "Database" → "Redis"

4. **Configure Environment Variables**
   - Go to your app service → "Variables" tab
   - Add these environment variables:
   ```
   DEBUG=False
   SECRET_KEY=your-secret-key-here
   GEMINI_API_KEY=your-gemini-api-key
   ALLOWED_HOSTS=your-app-name.railway.app
   ```

5. **Deploy**
   - Railway will automatically detect your Django app
   - It will run migrations and collect static files
   - Your app will be deployed!

### Option B: Using Railway CLI

1. **Install Railway CLI**
   ```bash
   npm install -g @railway/cli
   ```

2. **Login and Deploy**
   ```bash
   railway login
   railway init
   railway up
   ```

## Step 3: Access Your App

1. **Get Your App URL**
   - In Railway dashboard, go to your app service
   - Copy the generated URL (e.g., `https://your-app-name.railway.app`)

2. **Test on Your Phone**
   - Open your phone's browser
   - Navigate to your app URL
   - Your gym app should work perfectly!

## Step 4: Create a Superuser (Optional)

If you want to access the Django admin:

1. **Open Railway Dashboard**
2. **Go to your app service**
3. **Click "Deployments" tab**
4. **Click on the latest deployment**
5. **Open the terminal and run:**
   ```bash
   python manage.py createsuperuser
   ```

## Environment Variables Reference

| Variable | Description | Required |
|----------|-------------|----------|
| `DEBUG` | Set to `False` in production | Yes |
| `SECRET_KEY` | Django secret key | Yes |
| `DATABASE_URL` | PostgreSQL connection (auto-set by Railway) | Yes |
| `REDIS_URL` | Redis connection (auto-set by Railway) | Yes |
| `GEMINI_API_KEY` | Google Gemini API key for AI features | No |
| `ALLOWED_HOSTS` | Comma-separated list of allowed hosts | Yes |

## Troubleshooting

### App Won't Start
- Check the deployment logs in Railway dashboard
- Ensure all environment variables are set
- Verify your `requirements.txt` is up to date

### Database Issues
- Make sure PostgreSQL service is added and connected
- Check that `DATABASE_URL` is properly set

### Static Files Not Loading
- Railway automatically runs `collectstatic` during deployment
- Check that `STATIC_ROOT` is set correctly in settings

### Mobile Access Issues
- Ensure `ALLOWED_HOSTS` includes your Railway domain
- Check CORS settings if you're using API endpoints

## Free Tier Limits

Railway's free tier includes:
- 500 hours/month of runtime
- 1GB storage
- Shared resources
- Perfect for personal projects!

## Next Steps

Once deployed, you can:
1. **Custom Domain**: Add a custom domain in Railway settings
2. **SSL Certificate**: Automatically provided by Railway
3. **Monitoring**: Use Railway's built-in monitoring
4. **Scaling**: Upgrade to paid plan for more resources

## Support

- **Railway Docs**: [docs.railway.app](https://docs.railway.app)
- **Django Deployment**: [docs.djangoproject.com/en/stable/howto/deployment/](https://docs.djangoproject.com/en/stable/howto/deployment/)

---

🎉 **Congratulations!** Your gym app is now accessible from anywhere, including your phone!

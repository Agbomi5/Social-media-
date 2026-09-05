# Deploying to Vercel

This Django application is configured for serverless deployment on Vercel. Follow these steps to deploy.

## Prerequisites

1. Vercel account (https://vercel.com)
2. GitHub repository with this code pushed
3. PostgreSQL database (required for production - SQLite won't persist)
4. Optionally: Cloud storage for media files (AWS S3, Cloudinary, etc.)

## Step 1: Set Up Database

### Option A: Use Vercel's Partner Database
- Go to Vercel Dashboard → Add Integration → PostgreSQL
- Follow the setup wizard
- `DATABASE_URL` will be automatically added to your environment

### Option B: Use External PostgreSQL
- Neon: https://neon.tech (free tier available)
- Railway: https://railway.app
- Supabase: https://supabase.com

Get your `DATABASE_URL` in format: `postgresql://user:password@host:port/database`

## Step 2: Configure Environment Variables

1. Go to your project in Vercel Dashboard
2. Settings → Environment Variables
3. Add these variables:

```
SECRET_KEY=your-very-secret-key-generate-a-new-one
DEBUG=False
ALLOWED_HOSTS=your-domain.com,your-domain.vercel.app
CORS_ALLOWED_ORIGINS=https://your-domain.com,https://your-domain.vercel.app
CSRF_TRUSTED_ORIGINS=https://your-domain.com,https://your-domain.vercel.app
DATABASE_URL=postgresql://user:password@host:port/database
```

### Generate a secure SECRET_KEY:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

## Step 3: Update Domain Settings

1. Add your custom domain in Vercel (if applicable)
2. Update `ALLOWED_HOSTS` and `CORS_ALLOWED_ORIGINS` with your actual domain

## Step 4: Migrate Database

After first deployment, you need to run migrations:

```bash
# On your local machine with DATABASE_URL set
DJANGO_SETTINGS_MODULE=socialmedia_backend.settings python manage.py migrate
```

## Step 5: Create Superuser (Optional)

```bash
DJANGO_SETTINGS_MODULE=socialmedia_backend.settings python manage.py createsuperuser
```

## Step 6: Deploy

### Via Git (Recommended)
```bash
git push origin main
# Vercel will automatically detect changes and deploy
```

### Via Vercel CLI
```bash
vercel --prod
```

## Step 7: Verify Deployment

1. Visit your deployed app URL
2. Check deployment logs in Vercel Dashboard
3. Test API endpoints

## Troubleshooting

### 502 Bad Gateway
- Check function logs in Vercel Dashboard
- Verify `DATABASE_URL` is set correctly
- Check that migrations ran successfully

### Static files not loading
- Run: `python manage.py collectstatic`
- Ensure WhiteNoise is in MIDDLEWARE (it's automatic)

### CORS errors
- Check `CORS_ALLOWED_ORIGINS` includes your frontend domain
- Verify `CSRF_TRUSTED_ORIGINS` is set correctly

### Database connection errors
- Verify `DATABASE_URL` in environment variables
- Check database is accessible from Vercel
- If using private database, consider using Vercel's Postgres

## Setting Up Media Files (Optional)

To handle image uploads, configure cloud storage:

### AWS S3
```bash
pip install django-storages boto3
# Set environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_STORAGE_BUCKET_NAME
```

### Cloudinary
```bash
pip install cloudinary
# Set CLOUDINARY_URL environment variable
```

## Monitoring

- Check Vercel Dashboard → Logs for errors
- Monitor database usage
- Set up error tracking (e.g., Sentry)

## Important Notes

- Vercel is good for REST APIs but not ideal for long-running tasks
- Media files need cloud storage (not local filesystem)
- Consider alternatives: Railway, Render, or Fly.io for better Django support

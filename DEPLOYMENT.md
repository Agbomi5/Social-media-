# Deployment Guide for Vercel

## Prerequisites

1. **PostgreSQL Database**: Vercel's filesystem is read-only, so you need an external PostgreSQL database (Supabase, Neon, Railway, PlanetScale, etc.)
2. **Vercel Account**: [vercel.com](https://vercel.com)
3. **GitHub/GitLab/Bitbucket**: Repository hosting

## Quick Deploy

### 1. Push to Git Repository

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin <your-repo-url>
git push -u origin main
```

### 2. Configure Vercel Project

1. Go to [Vercel Dashboard](https://vercel.com/dashboard)
2. Click "Add New..." → "Project"
3. Import your Git repository
4. Configure:
   - **Framework Preset**: Other
   - **Build Command**: `./build.sh`
   - **Output Directory**: (leave empty)
   - **Install Command**: (leave empty - handled by build.sh)

### 3. Environment Variables

Add these in Vercel Project Settings → Environment Variables:

| Variable | Value | Required |
|----------|-------|----------|
| `SECRET_KEY` | Random 50+ char string | Yes |
| `DEBUG` | `False` | Yes |
| `ALLOWED_HOSTS` | `.vercel.app,.now.sh` | Yes |
| `DATABASE_URL` | Your PostgreSQL connection string | Yes |
| `CORS_ALLOWED_ORIGINS` | `https://your-app.vercel.app` | Yes |
| `CSRF_TRUSTED_ORIGINS` | `https://your-app.vercel.app` | Yes |

Generate a secret key:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 4. Database Setup

The Vercel build applies Django migrations automatically. Make sure `DATABASE_URL`
is configured for each Vercel environment (Production, Preview, and Development)
that you deploy. Use a separate database for Preview deployments so preview builds
cannot apply migrations to your production database.

To create an administrator after deployment, use the production database URL locally:
```bash
vercel env pull .env.production
source .env.production
python manage.py createsuperuser
```

### 5. Media Files

Vercel's filesystem is temporary. Configure Supabase Storage so profile pictures
and post media persist:

1. In Supabase, create a **public** bucket (for example, `vordi-media`). Public
   buckets allow the app's existing public media links to display.
2. In **Storage → Settings → S3 Connection**, create S3 credentials.
3. Add these Vercel environment variables:

| Variable | Value |
|----------|-------|
| `SUPABASE_PROJECT_REF` | Project reference from the Supabase project URL |
| `SUPABASE_S3_BUCKET` | Exact bucket name, such as `vordi-media` |
| `SUPABASE_S3_ACCESS_KEY_ID` | Supabase Storage S3 access key |
| `SUPABASE_S3_SECRET_ACCESS_KEY` | Supabase Storage S3 secret key |

The app uses Supabase Storage for uploads when configured. Keep the S3 credentials
private and redeploy after setting the variables. The client limits each upload
to 4 MB to stay within Vercel's request-size limit.

## Local Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env with your local settings

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Run development server
python manage.py runserver
```

## Project Structure

```
├── build.sh              # Vercel build script
├── vercel.json           # Vercel configuration
├── requirements.txt      # Python dependencies
├── .vercelignore         # Files to exclude from deployment
├── .env.example          # Environment variable template
├── manage.py
├── socialmedia_backend/  # Django project
│   ├── settings.py       # Settings (production-ready)
│   ├── wsgi.py          # WSGI entry point
│   └── urls.py
├── core/                 # Main app
└── static/               # Static assets (CSS, JS)
    ├── styles.css
    ├── app.js
    └── config.js
└── frontend/             # Django templates
    ├── index.html
    ├── signin.html
    ├── signup.html
    └── messages.html
```

## Troubleshooting

### Static files not loading
1. Ensure `STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'` in settings.py
2. Check that `whitenoise.middleware.WhiteNoiseMiddleware` is right after `SecurityMiddleware`
3. Verify `collectstatic` runs during build (check build logs)

### Database connection errors
1. Verify `DATABASE_URL` format: `postgresql://user:pass@host:port/dbname?sslmode=require`
2. Check database allows connections from Vercel's IP ranges
3. Check Vercel build logs for migration errors

### CORS errors
1. Add your Vercel domain to `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS`
2. Ensure both include `https://`

### Media uploads fail
- Expected on Vercel's read-only filesystem
- Configure external storage (S3, Cloudinary, etc.)

## Useful Vercel CLI Commands

```bash
# Install CLI
npm i -g vercel

# Login
vercel login

# Deploy
vercel --prod

# View logs
vercel logs <deployment-url>

# Run management commands
vercel run python manage.py migrate
vercel run python manage.py collectstatic

# Pull environment variables
vercel env pull .env.local
```
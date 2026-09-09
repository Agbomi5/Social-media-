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

After first deployment, run migrations:
```bash
# In Vercel CLI or locally with production DATABASE_URL
vercel env pull .env.production
source .env.production
python manage.py migrate
python manage.py createsuperuser
```

Or use Vercel's CLI:
```bash
vercel run python manage.py migrate
vercel run python manage.py createsuperuser
```

### 5. Media Files

**Important**: Vercel's filesystem is read-only. Media uploads (avatars, post images/videos) won't persist on Vercel.

Options:
- **AWS S3**: Use `django-storages` with `boto3`
- **Cloudinary**: Use `cloudinary-storage`
- **Supabase Storage**: Use `supabase-storage`

Example for S3 (add to settings.py):
```python
if not DEBUG:
    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_REGION_NAME = os.getenv('AWS_S3_REGION_NAME', 'us-east-1')
```

Add to requirements.txt:
```
django-storages>=1.14.0
boto3>=1.34.0
```

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
3. Run migrations after deployment

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
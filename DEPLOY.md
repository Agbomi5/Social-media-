# Deployment Commands - Copy & Paste Ready

## Step 1: Commit Changes Locally (On Your Machine)

```bash
# Navigate to project directory
cd /path/to/socialmedia_backend

# Check what changed
git status

# Stage all changes
git add -A

# Commit with message
git commit -m "Fix static files serving and enhance UI/UX for Vercel deployment

- Configure WhiteNoise for static file serving
- Add proper Django static template tags
- Implement responsive mobile design with sticky bottom navigation
- Add light/dark theme support with persistence
- Set up proper Vercel routing for static files
- Add comprehensive deployment documentation"

# Verify commit was created
git log --oneline -1
```

## Step 2: Verify Environment Variables in Vercel

Before deploying, set these in Vercel Dashboard → Project Settings → Environment Variables:

```
SECRET_KEY=<generate-new-key>
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,yourdomain.vercel.app
DATABASE_URL=postgresql://user:password@host:port/database
CORS_ALLOWED_ORIGINS=https://yourdomain.com,https://yourdomain.vercel.app
CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://yourdomain.vercel.app
```

Generate SECRET_KEY locally:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

## Step 3: Push to GitHub (Triggers Auto-Deployment)

```bash
# Push to main branch (auto-deploys to Vercel)
git push origin main

# OR if you use different branch
git push origin your-branch-name

# Watch deployment in Vercel dashboard (takes 1-3 minutes)
```

## Step 4: Verify Deployment Success

### Check Build Logs
```bash
# In Vercel Dashboard:
# 1. Go to Project
# 2. Click latest Deployment
# 3. Check "Build Logs" tab
# 4. Look for "Collecting static files..."
# 5. Should show success message
```

### Test in Browser
```bash
# Open your deployed URL
https://yourapp.vercel.app

# Press F12 to open DevTools → Network tab
# Reload page (Ctrl+R)
# Look for:
# - /static/styles.css → Status 200 ✓
# - /static/app.js → Status 200 ✓
# - No 404 errors ✓

# Check page is styled (not plain white text)
# Check bottom nav appears on mobile (< 768px)
# Click theme toggle (🌙) - should switch dark/light
```

---

## Optional: Local Testing Before Deploy

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables (Linux/Mac)
export DEBUG=True
export SECRET_KEY="test-key-for-local-development"

# OR set them (Windows PowerShell)
$env:DEBUG="True"
$env:SECRET_KEY="test-key-for-local-development"

# Collect static files
python manage.py collectstatic --noinput

# Run migrations
python manage.py migrate

# Start server
python manage.py runserver

# Open http://localhost:8000
# Check:
# - Page loads with styling (CSS works)
# - Navigation appears at top
# - Bottom nav NOT visible (only on mobile)
# - Theme toggle works (click moon icon)
# - No console errors (F12 → Console)
```

---

## Troubleshooting: If Static Files Still Don't Load

### Option 1: Clear Vercel Cache (Quick Fix)
```bash
# In Vercel Dashboard:
# 1. Go to Project → Settings → Deployments
# 2. Click "Clear Cache" button
# 3. Redeploy (git push or click "Redeploy" in dashboard)
```

### Option 2: Verify Configuration Locally
```bash
# Check STATIC_ROOT exists
ls -la staticfiles/

# Check files were collected
ls -la staticfiles/styles.*.css
ls -la staticfiles/app.*.js

# Look for version hashes (e.g., styles.abc123.css)
# Should have hash, not plain "styles.css"
```

### Option 3: Check Vercel Build Output
```bash
# In Vercel Dashboard:
# 1. Click failing deployment
# 2. Check "Build Logs"
# 3. Search for "collectstatic"
# 4. Look for error messages
# 5. Common issues:
#    - Missing STATIC_ROOT directory
#    - Permission denied writing files
#    - DATABASE_URL not set causing migration errors
```

### Option 4: Manual Test Locally Exactly Like Production
```bash
# Recreate production environment locally
export DEBUG=False
export SECRET_KEY="test-production-key"
export DATABASE_URL="postgresql://..."  # Use real DB

# Run collectstatic like Vercel does
python manage.py collectstatic --noinput

# Check files with version hashes
ls -la staticfiles/ | grep styles
# Should show: styles.abc123def456.css (not styles.css)

# This means compression worked correctly
```

---

## After Deployment: Monitoring

### Monitor Errors
```bash
# Vercel Dashboard → Project → Function Logs
# Watch for errors as users access the site
# Common errors:
# - 404 for static files → collectstatic didn't run
# - 502 Bad Gateway → Database connection issue
# - 503 Service Unavailable → Server overloaded
```

### Check Performance
```bash
# Run Lighthouse audit
# 1. Open your deployed app
# 2. Press F12 → Lighthouse tab
# 3. Click "Analyze page load"
# 4. Check:
#    - Performance > 80
#    - Accessibility > 90
#    - Best Practices > 90

# Check specific metrics:
# First Contentful Paint (FCP) < 3 seconds
# Largest Contentful Paint (LCP) < 4 seconds
# Cumulative Layout Shift (CLS) < 0.1
```

### Monitor Traffic
```bash
# Vercel Dashboard → Analytics (if enabled)
# Track:
# - Page views
# - Error rate
# - Response times
# - Browser usage
```

---

## Rolling Back If Needed

```bash
# If deployment fails, you can revert:
git log --oneline | head -5  # See recent commits

# Revert to previous commit
git revert HEAD
git push origin main

# OR completely undo last commit (if not pushed)
git reset --hard HEAD~1

# Vercel will auto-deploy the reverted code
```

---

## Database Setup (First Time Only)

```bash
# After first deployment, run migrations on production:
# Option 1: Use Vercel CLI
vercel env pull  # Pull env vars
python manage.py migrate  # Run locally with production DB

# Option 2: Via Django shell (if available)
# In Vercel dashboard, you can't easily run Django management commands
# Instead, run them locally with DATABASE_URL set to production

# Create superuser (optional)
DJANGO_SETTINGS_MODULE=socialmedia_backend.settings \
python manage.py createsuperuser --database=default
```

---

## Summary: All Commands in Order

```bash
# 1. Commit
git add -A
git commit -m "Fix static files and enhance UI/UX for Vercel"

# 2. Push (auto-deploys)
git push origin main

# 3. Monitor
# → Go to Vercel Dashboard
# → Click last deployment
# → Watch build logs until "Build completed"

# 4. Test
# → Open https://yourapp.vercel.app
# → F12 → Network tab
# → Verify /static/styles.css returns 200
# → Check page is styled (not plain white)
# → Test theme toggle
# → Resize to mobile and check bottom nav

# 5. If fails, clear cache and retry
# → Vercel Dashboard → Settings → Deployments → Clear Cache
# → git push origin main (retrigger)

# Done! 🎉
```

---

## Quick Links

| Task | Location |
|------|----------|
| View Deployment | https://vercel.com/dashboard |
| Check Build Logs | Project → Deployments → Latest → "Build Logs" |
| Set Env Variables | Project → Settings → Environment Variables |
| View Live Site | Project → Overview → copy URL |
| Verify STatic Files | DevTools → Network tab → /static/* |
| Return to Git | `git log --oneline` |

---

## Environment Variables Generator

```bash
# Run this locally and copy output to Vercel
python << 'EOF'
from django.core.management.utils import get_random_secret_key
import os

# Generate SECRET_KEY
secret = get_random_secret_key()
print(f"SECRET_KEY={secret}")
print(f"DEBUG=False")
print(f"ALLOWED_HOSTS=yourdomain.vercel.app")
print(f"CORS_ALLOWED_ORIGINS=https://yourdomain.vercel.app")
print(f"CSRF_TRUSTED_ORIGINS=https://yourdomain.vercel.app")
print(f"DATABASE_URL=postgresql://user:password@host:port/db")
EOF
```

---

**Ready? Run these commands now:**

```bash
git add -A && git commit -m "Fix static files and enhance UI/UX" && git push origin main
```

**Then watch it deploy in Vercel Dashboard! 🚀**

---

## Support

If anything goes wrong:
1. Check [STATIC_FILES_DEPLOYMENT.md](STATIC_FILES_DEPLOYMENT.md) → Troubleshooting section
2. Check [QUICK_REFERENCE.md](QUICK_REFERENCE.md) → Troubleshooting section
3. Check Vercel Dashboard → Build Logs
4. Check browser DevTools → Console for errors

Last Updated: September 9, 2026

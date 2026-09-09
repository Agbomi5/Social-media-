# Deployment Architecture & Static Files Flow

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    Pulse Social Media App                        │
│                   Deployed on Vercel                             │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      Browser / Client                            │
│  - Makes HTTP requests                                          │
│  - Renders HTML, CSS, JavaScript                                │
│  - Stores theme in localStorage                                 │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTP/HTTPS Requests
                         │
           ┌─────────────▼──────────────┐
           │   Vercel Edge Network     │
           │  (Global CDN)             │
           │  - Cache static files     │
           │  - Route requests         │
           │  - Compression (gzip)     │
           └─┬────────────────────────┬┘
             │                        │
    ┌────────▼──┐          ┌─────────▼─────┐
    │ /static/* │          │  /api/*       │
    │ /media/*  │          │  Other routes │
    └────────┬──┘          └────────┬──────┘
             │                      │
    ┌────────▼──────────────┐      │
    │ Static Files Storage  │      │
    │  (staticfiles/)       │      │
    │                       │      │
    │  ✓ styles.abc123.css  │      │
    │  ✓ app.def456.js      │      │
    │  ✓ Compressed files   │      │
    │  ✓ 1-hour cache       │      │
    └───────────────────────┘      │
                                   │
              ┌────────────────────▼──────────────┐
              │  Django Application (Lambda)      │
              │  - Handles API requests           │
              │  - Database queries               │
              │  - Authentication                 │
              │  - Renders HTML pages             │
              └─────────────┬──────────────────┬──┘
                            │                  │
              ┌─────────────▼────┐  ┌─────────▼──────┐
              │  PostgreSQL DB   │  │  Media Storage │
              │  - User data     │  │  - User photos │
              │  - Posts         │  │  - Avatars     │
              │  - Messages      │  │  - Music files │
              └──────────────────┘  └────────────────┘
```

## Request Flow: Static Files

### 1. Browser Requests CSS

```
┌─────────────────────────────────────────────────────────────────┐
│ HTML Template:                                                   │
│ <link rel="stylesheet" href="{% static 'styles.css' %}">        │
│                                                                  │
│ Rendered as:                                                     │
│ <link rel="stylesheet" href="/static/styles.abc123.css">        │
│ (WhiteNoise adds hash to filename)                              │
└────────────────┬────────────────────────────────────────────────┘
                 │
    ┌────────────▼────────────────┐
    │  Browser sends request:      │
    │  GET /static/styles.abc123.css
    │  Accept-Encoding: gzip       │
    └────────────┬─────────────────┘
                 │
    ┌────────────▼──────────────────────────┐
    │  Vercel Routes (vercel.json):         │
    │  /static/(.*) → /staticfiles/$1       │
    └────────────┬──────────────────────────┘
                 │
    ┌────────────▼──────────────────────────┐
    │  Vercel Responds:                     │
    │  Cache-Control: public,               │
    │    max-age=3600, immutable            │
    │  Content-Encoding: gzip               │
    │  ETag: "abc123..."                    │
    │  200 OK ✓                             │
    │                                       │
    │  Response Body (compressed):          │
    │  /* CSS rules */                      │
    └────────────┬──────────────────────────┘
                 │
    ┌────────────▼──────────────────────────┐
    │  Browser Applies Styles               │
    │  - Parses CSS                         │
    │  - Applies to DOM                     │
    │  - Renders page with styling ✓        │
    └──────────────────────────────────────┘
```

## Build Process: Static Files Collection

### What Happens When You Push to GitHub

```
Git Push
   │ github.com/your-repo
   ▼
┌────────────────────┐
│ Vercel Webhook     │
│ Triggered          │
└─────────┬──────────┘
          │
┌─────────▼──────────────────────────────────┐
│ 1. Clone Repository                        │
│    └─ Copy source code to builder instance │
└──────────┬───────────────────────────────┬─┘
           │                               │
┌──────────▼───────────────────┐  ┌────────▼──────────────┐
│ 2. Install Dependencies      │  │ 3. Set Environment    │
│    Run: pip install -r       │  │    Set all ENV vars   │
│         requirements.txt      │  │    from settings      │
│    ✓ Django 6.0.3            │  │                       │
│    ✓ WhiteNoise 6.6.0        │  │                       │
│    ✓ Other packages          │  │                       │
└──────────┬───────────────────┘  └────────┬──────────────┘
           │                               │
           └───────────────┬────────────────┘
                           │
         ┌─────────────────▼─────────────────┐
         │ 4. Run Build Command (vercel.json)│
         │    Command:                       │
         │    python manage.py collectstatic │
         │              --noinput            │
         └──────────────┬────────────────────┘
                        │
         ┌──────────────▼──────────────────────┐
         │ 5. Collect Static Files             │
         │    Django walks through:             │
         │    - frontend/ directory            │
         │    - app directories                │
         │    - admin files                    │
         │                                     │
         │    Copies to: staticfiles/         │
         │                                     │
         │    Applies STATICFILES_STORAGE:     │
         │    - Compresses files              │
         │    - Adds version hashes           │
         │    - Creates manifest.json          │
         │                                     │
         │    Result:                          │
         │    staticfiles/                    │
         │    ├─ styles.abc123def.css         │
         │    ├─ app.ghi456jkl.js             │
         │    ├─ manifest.json                │
         │    └─ (other static files)         │
         └──────────────┬──────────────────────┘
                        │
         ┌──────────────▼──────────────────────┐
         │ 6. Deploy to Vercel                 │
         │    - Package application            │
         │    - Deploy to AWS Lambda functions │
         │    - Serve from Vercel CDN          │
         │                                     │
         │    staticfiles/ becomes accessible │
         │    at: /static/                    │
         └──────────────┬──────────────────────┘
                        │
         ┌──────────────▼──────────────────────┐
         │ 7. Success ✓                        │
         │    Deployment complete             │
         │    Site is live at:                │
         │    https://yourapp.vercel.app      │
         └──────────────────────────────────────┘
```

## File Structure After Build

### Local Development
```
project-root/
├── frontend/
│   ├── styles.css              (Source CSS)
│   └── app.js                  (Source JavaScript)
│
└── That's it! CSS served directly by Django
   (When DEBUG=True)
```

### After Vercel Build (Production)
```
project-root/
├── staticfiles/                (Generated by collectstatic)
│   ├── styles.abc123def.css    (Compressed, versioned)
│   ├── app.ghi456jkl.js        (Compressed, versioned)
│   ├── manifest.json           (Maps original → versioned)
│   └── ... other static files
│
├── frontend/                   (Original source)
│   ├── styles.css
│   └── app.js
│
└── Django serves from staticfiles/
   HTML templates reference versioned names
```

## CSS & Theme System Architecture

### CSS Variables for Theming

```
:root (Light Theme - Default)
├─ --bg: #fafafa
├─ --card: #ffffff
├─ --text: #0f172a
├─ --accent: #6366f1
└─ ... 30+ color variables

[data-theme="dark"] (Dark Theme)
├─ --bg: #0a0a0a
├─ --card: #131313
├─ --text: #fafafa
├─ --accent: #818cf8
└─ ... 30+ color variables (overrides)

All CSS components use: color: var(--text)
When theme changes, all vars update automatically!
```

### Theme Toggle Flow

```
┌─────────────────┐
│ User clicks 🌙  │
└────────┬────────┘
         │
┌────────▼─────────────────────┐
│ applyTheme('dark') called    │
│ (from app.js)                │
└────────┬─────────────────────┘
         │
    ┌────▼────────────────────────────────┐
    │ document.documentElement.setAttribute│
    │   ('data-theme', 'dark')           │
    └────┬─────────────────────────────────┘
         │
    ┌────▼──────────────────────────────┐
    │ CSS Variables Update               │
    │ [data-theme="dark"] styles apply  │
    │ All colors flip instantly          │
    └────┬───────────────────────────────┘
         │
    ┌────▼──────────────────────────────┐
    │ localStorage.setItem('theme',     │
    │   'dark')                          │
    │ Saves preference                   │
    └────┬───────────────────────────────┘
         │
    ┌────▼──────────────────────────────────┐
    │ Update Icon: '☀️' → '🌙'              │
    │ Page instantly shows dark mode ✓      │
    └───────────────────────────────────────┘
```

## Responsive Layout Breakpoints

### Grid Architecture

```
Desktop (> 1100px)
┌─────────────────────────────────────────────┐
│  Sidebar (fixed) │ Main Feed │ Trending     │
│                  │           │              │
│  Quick Links     │ Posts     │ Trending     │
│                  │ Comments  │ Topics       │
│                  │ Create    │ Suggestions  │
│                  │           │              │
└─────────────────────────────────────────────┘
3-Column Grid: 1fr 300px

Tablet (768px - 1100px)
┌────────────────────────────────┐
│        Main Feed (full width)  │
│  Posts, Comments, Create Post  │
│  Sticky Header                 │
│  (Sidebar hidden)              │
│  (Trending hidden)             │
│  (Bottom nav hidden)           │
└────────────────────────────────┘
1-Column Grid: 1fr

Mobile (< 768px)
┌──────────────────────┐
│  Sticky Header       │ ← 72px
├──────────────────────┤
│   Main Feed          │
│   (full screen)      │
│  Posts               │
│  Comments            │
│  Create Post         │
│                      │
│  (Padding: 56px)     │ ← For bottom nav
├──────────────────────┤
│  Sticky Bottom Nav   │ ← 56px
│  5 Icons w/ Badges   │
└──────────────────────┘
100% width, adjusts for safe areas
```

## Mobile Navigation Architecture

### Bottom Navigation States

```
Default State
┌──────────────────────────────────┐
│ 🏠 Home │ 🔍 │ 💬 │ 🔔 │ 👤 │
│ (active)│    │   │    │    │
└──────────────────────────────────┘

With Unread Badges
┌──────────────────────────────────┐
│ 🏠 Home  │ 🔍 │ 💬 │ 🔔 │ 👤 │
│          │    │   │ 3  │    │ ← Alert badge
└──────────────────────────────────┘

Active Navigation State
┌──────────────────────────────────┐
│ 🏠 Home │ 🔍 │ 💬 │ 🔔 │ 👤 │
│         │    │    │    │ (active)
│ (all blue accent when active)    │
└──────────────────────────────────┘
```

## Summary: Key Components

### Frontend
```
┌─ HTML Templates
│  ├─ Uses Django {% load static %} tag
│  ├─ References versioned file names
│  └─ Renders from Django views
│
├─ CSS Styling (styles.css)
│  ├─ CSS variables for theming
│  ├─ Media queries for responsive
│  ├─ Glassmorphism effects
│  └─ 44px+ touch targets
│
├─ JavaScript (app.js)
│  ├─ Theme toggle logic
│  ├─ API client
│  ├─ DOM manipulation
│  └─ Event handlers
│
└─ Static Assets
   ├─ Collected by collectstatic
   ├─ Versioned with hashes
   ├─ Compressed with gzip
   └─ Cached for 1 hour
```

### Backend
```
┌─ Django Application
│  ├─ settings.py
│  │  ├─ WhiteNoise config
│  │  ├─ Static files settings
│  │  └─ Security settings
│  │
│  ├─ urls.py
│  │  └─ API endpoints (Vercel routes to this)
│  │
│  └─ views.py
│     └─ Serve HTML templates with static tags
│
└─ Database (PostgreSQL)
   ├─ User accounts
   ├─ Posts & comments
   └─ Messages
```

### Deployment
```
┌─ vercel.json
│  ├─ buildCommand: runs collectstatic
│  ├─ routes: /static/ → /staticfiles/
│  └─ cache headers: 1 hour
│
├─ build.sh
│  ├─ Install dependencies
│  ├─ Collect static files
│  └─ Run migrations
│
└─ GitHub + Vercel Integration
   ├─ git push → auto-deploy
   ├─ Build runs automatically
   └─ Site goes live
```

---

## Environment Flow

```
Development
├─ DEBUG=True
├─ SECRET_KEY=test-key
├─ SQLite database
├─ Static files served by Django
└─ Theme: saved to localStorage

Production (Vercel)
├─ DEBUG=False
├─ SECRET_KEY=secure-generated-key (env var)
├─ PostgreSQL database
├─ Static files served by WhiteNoise + Vercel CDN
└─ Theme: persisted in localStorage
```

---

*This architecture ensures your Pulse social media app runs efficiently and professionally on Vercel with proper static file serving and responsive mobile-first design.*

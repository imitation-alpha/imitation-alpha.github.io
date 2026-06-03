# Personal Site

Static portfolio site. No build step, no dependencies.

## Structure

```
home-page/
├── index.html              # Main page (about, experience, projects, publications)
├── css/styles.css          # All styles (light + dark theme)
├── js/main.js              # Nav toggle, theme switcher, year, scroll spy
├── scripts/generate_rss.py # RSS feed generator
└── blog/
    ├── index.html          # Blog index (post list)
    ├── feed.xml            # English RSS feed
    └── orchestrating-coding-agents.html  # Sample post — copy & rename for new posts
```

## Run locally

Any static file server works. From this directory:

```bash
# Python
python3 -m http.server 8000

# Node
npx serve .
```

Then open <http://localhost:8000>.

## Add a new blog post

1. Copy `blog/orchestrating-coding-agents.html` to `blog/your-slug.html`
2. Update `<title>`, `<meta description>`, the `<h1>`, the `post__meta` date, and the body
3. Add a new `<li>` to the `.post-list` in `blog/index.html` linking to the new file
4. Run `python3 scripts/generate_rss.py` to update `feed.xml` and localized blog feeds

## Customize

- **Colors / fonts**: top of `css/styles.css` (`:root` block, plus `[data-theme="dark"]`)
- **Contact links**: search for `linkedin.com/in/arthur-yau`, `github.com/imitation-alpha`, and `x.com/imitation_alpha` and replace as needed
- **Sections**: edit `index.html`; sections are clearly delimited with comments

## Deploy

This is a plain static site — drop it anywhere.

- **GitHub Pages**: push to a repo, enable Pages on the `main` branch root
- **Vercel**: `vercel deploy` from this directory (no config needed)
- **Netlify**: drag the folder onto netlify.com/drop, or connect a repo
- **Cloudflare Pages**: connect a repo; build command is empty, output dir is `/`

## Notes

- Theme preference is stored in a cookie (no `localStorage`), so it survives across visits
- All asset paths are relative — site works from any subpath
- RSS feeds are generated from committed blog HTML metadata with `python3 scripts/generate_rss.py`

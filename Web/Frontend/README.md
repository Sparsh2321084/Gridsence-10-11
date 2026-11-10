# GridSense Frontend

GridSense is a responsive electricity forecasting website for Delhi, built with React, TypeScript, and Vite. It currently includes a home page and a dashboard placeholder. Live load and forecast data are not connected yet.

## Project structure

```text
src/
├── assets/                 # Images and other frontend assets
├── components/
│   └── layout/             # Shared site header, footer, and layout
├── pages/
│   ├── home/
│   │   ├── HomePage.tsx    # Composes the home page sections
│   │   └── sections/       # Independently editable home page sections
│   └── dashboard/
│       ├── DashboardPage.tsx
│       └── sections/       # Dashboard-specific sections
├── App.tsx                 # Selects the page for the current URL
├── App.css                 # Application styles
├── index.css               # Global styles
└── main.tsx                # Application entry point
```

The shared `SiteLayout` wraps each page with the same header and footer. Page-specific content stays inside its page folder. To change the order of home page sections, rearrange their component entries in `pages/home/HomePage.tsx`; each section can otherwise be edited independently.

The `/dashboard` route currently displays a placeholder until the backend and forecasting model are connected.

## Development

Run these commands from `Web/Frontend`:

```powershell
npm install
npm run dev
```

## Checks

```powershell
npm run build
npm run lint
```

## Deployment

For Vercel, set the project root directory to `Web/Frontend`. The Vercel configuration rewrites `/dashboard` to the app entry point so the client-side dashboard route works on direct visits and refreshes.

# TrashAlert Documentation Website

This directory contains the TrashAlert documentation site built with [Docusaurus](https://docusaurus.io/).

## Overview

The documentation covers:
- **API Reference**: Complete REST API documentation
- **Getting Started**: Setup and quick start guides
- **Architecture**: System design and database schema
- **Data Pipeline**: OSM collection and address sampling
- **Developer Guides**: Contributing, testing, and deployment

## Local Development

### Prerequisites
- Node.js 20.0 or higher
- npm

### Installation

```bash
cd website
npm install
```

### Start Development Server

```bash
npm start
```

This command starts a local development server and opens up a browser window at http://localhost:3000/. Most changes are reflected live without having to restart the server.

### Build

```bash
npm run build
```

This command generates static content into the `build` directory that can be served using any static hosting service.

## Deployment

The documentation is automatically deployed to GitHub Pages when changes are pushed to the `main` branch under the `website/` directory.

### Manual Deployment

```bash
npm run deploy
```

This command builds the website and pushes to the `gh-pages` branch.

## Documentation Structure

```
docs/
├── intro.md                 # Introduction page
├── api/                     # API Reference
│   ├── overview.md
│   ├── endpoints/          # Endpoint docs
│   ├── models/             # Data models
│   ├── examples.md
│   └── errors.md
├── guides/                  # Getting Started & Guides
│   ├── setup.md
│   ├── quickstart.md
│   ├── docker.md
│   ├── contributing.md
│   ├── testing.md
│   └── deployment.md
├── architecture/            # Architecture Documentation
│   ├── overview.md
│   ├── database.md
│   ├── crowdsourcing.md
│   └── diagrams.md
└── pipeline/                # Data Pipeline
    ├── overview.md
    ├── osm-collection.md
    ├── address-sampling.md
    └── adding-cities.md
```

## Configuration

- **docusaurus.config.ts**: Main configuration file
- **sidebars.ts**: Sidebar navigation structure
- **src/css/custom.css**: Custom styling

## Contributing to Documentation

To contribute to the documentation:

1. Make your changes in the appropriate `.md` file under `docs/`
2. Test locally with `npm start`
3. Build to ensure no errors: `npm run build`
4. Submit a pull request

## Links

- **Live Site**: https://tombstonedash.github.io/TrashAlert/
- **Docusaurus Documentation**: https://docusaurus.io/docs
- **Main Repository**: https://github.com/TombStoneDash/TrashAlert

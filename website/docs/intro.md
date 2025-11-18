---
sidebar_position: 1
title: Introduction
slug: /
---

# TrashAlert Documentation

Welcome to the **TrashAlert** documentation! TrashAlert is a crowdsourced trash collection day lookup system designed to help residents quickly find their trash, recycling, and green waste pickup schedules.

## 🎯 What is TrashAlert?

TrashAlert solves a common problem: **finding your trash collection day shouldn't be difficult**. Many cities have confusing websites, outdated schedules, or vary pickup days by neighborhood. TrashAlert uses crowdsourcing to build a reliable, community-driven database of trash pickup schedules.

### Key Features

- **📍 Address-based Lookup**: Enter your address and get your pickup schedule instantly
- **👥 Crowdsourced Data**: Community observations create a self-correcting database
- **🎯 Confidence Scores**: Know how reliable each schedule is based on report consensus
- **🔄 Self-updating**: Automatically adapts to schedule changes through user reports
- **🗺️ Geographic Coverage**: Supports multiple cities with intelligent data sampling

## 🚀 Quick Links

- **[Getting Started](/docs/guides/setup)**: Set up TrashAlert locally
- **[API Reference](/docs/api/overview)**: Explore REST API endpoints
- **[Architecture](/docs/architecture/overview)**: Understand system design

## 🎓 The Problem We're Solving

Finding your trash collection day is harder than it should be:

- **🔍 Hard to Find**: City websites are often confusing or outdated
- **📍 Location-Specific**: Schedules vary by neighborhood or subdivision
- **📅 Schedule Changes**: Route changes aren't communicated effectively
- **🆕 New Residents**: Newcomers don't know where to look

## 💡 The TrashAlert Solution

TrashAlert uses a **crowdsourcing consensus model**:

1. **Users Report**: Residents submit when they observe trash collection
2. **System Calculates**: Multiple reports create a consensus schedule
3. **Confidence Scoring**: Agreement ratios show reliability
4. **Self-Correcting**: More data improves accuracy over time

### Data Source Priority

TrashAlert intelligently combines multiple data sources:

1. **CROWD_VERIFIED** - Verified crowdsourced consensus (>=3 reports, >=67% agreement)
2. **OFFICIAL** - Official municipal GIS/government data
3. **CROWD_UNVERIFIED** - Unverified crowdsourced data (&lt;3 reports or low agreement)
4. **UNKNOWN** - No data available

## 🏛️ Project Status

**Current Phase**: Production Ready (v1.0.0)

### ✅ Completed

- OpenStreetMap address extraction pipeline
- FastAPI backend with crowdsourcing logic
- Consensus algorithm with verification thresholds
- Admin dashboard (React)
- Docker deployment configuration
- PostgreSQL with PostGIS support

### 📅 Roadmap

- Real-time notifications
- Schedule change alerts
- Mobile application

## 🌍 Current Coverage

TrashAlert currently covers pilot cities in:

- **Imperial Valley, CA**: El Centro, Imperial, Brawley, Holtville, Calexico
- **San Diego County, CA**: San Diego (select neighborhoods)

## 🤝 Contributing

TrashAlert is open source and welcomes contributions! Check out our [Contributing Guide](/docs/guides/contributing) to get started.

## 📖 Documentation Structure

### Getting Started
- **[Setup Guide](/docs/guides/setup)**: Install and run locally
- **[Quick Start](/docs/guides/quickstart)**: Get running in 5 minutes
- **[Docker Guide](/docs/guides/docker)**: Deploy with Docker

### Architecture
- **[System Overview](/docs/architecture/overview)**: High-level architecture
- **[Database Schema](/docs/architecture/database)**: Data models
- **[Crowdsourcing Logic](/docs/architecture/crowdsourcing)**: Consensus algorithm

### Data Pipeline
- **[Pipeline Overview](/docs/pipeline/overview)**: Data collection workflow
- **[OSM Collection](/docs/pipeline/osm-collection)**: Address extraction
- **[Adding Cities](/docs/pipeline/adding-cities)**: Expand coverage

### API Reference
- **[API Overview](/docs/api/overview)**: REST API introduction
- **[Endpoints](/docs/api/endpoints/lookup)**: Endpoint documentation
- **[Examples](/docs/api/examples)**: Code examples

## 🔗 Useful Links

- **GitHub**: [TombStoneDash/TrashAlert](https://github.com/TombStoneDash/TrashAlert)
- **Issues**: [Report bugs](https://github.com/TombStoneDash/TrashAlert/issues)

---

**Ready to get started?** Head to the [Setup Guide](/docs/guides/setup) to install TrashAlert locally.

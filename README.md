# GitHub Stars Badge API

A high-performance FastAPI service that generates dynamic GitHub star count badges and provides star count data via REST API. Perfect for README files, documentation, and dashboards.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

## Features

- **High Performance**: Async FastAPI with LMDB caching for lightning-fast responses
- **Dual Output**: JSON API for star counts + SVG badges for visual display
- **Rate Limiting**: Built-in protection against abuse with configurable limits
- **Persistent Caching**: LMDB-based storage reduces GitHub API calls
- **Customizable Badges**: Multiple themes and colors via shields.io
- **GitHub Token Support**: Higher rate limits with personal access token
- **Real-time Data**: Fetches live star counts from GitHub API

## Quick Start

### Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/rawbytedev/github-stars-badge.git
   cd github-stars-badge
   ```

2. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Run the server:**

   ```bash
   python -m src
   ```

The API will be available at `http://localhost:8000`

### Docker (Not readu yet)

```bash
# When available:
docker build -t github-stars-badge .
docker run -p 8000:8000 github-stars-badge
```

## API Documentation

### Endpoints

#### Get User Star Count

```http
GET /api/v1/stars/{username}
```

**Response:**

```json
{
  "owner": "torvalds",
  "stars": 156789
}
```

#### Get Repository Star Count

```http
GET /api/v1/stars/{owner}/{repo}
```

**Response:**

```json
{
  "owner": "microsoft",
  "repo": "vscode",
  "stars": 145678
}
```

#### Get User Badge

```http
GET /api/v1/badge/user/{username}?theme=flat
```

Returns an SVG badge showing total stars for the user.

#### Get Repository Badge

```http
GET /api/v1/badge/repo/{owner}/{repo}?theme=flat
```

Returns an SVG badge showing stars for the specific repository.

#### Health Check

```http
GET /api/v1/health
```

**Response:**

```json
{
  "status": "healthy",
  "database": "connected"
}
```

Or if unhealthy:

```json
{
  "status": "unhealthy",
  "database": "error",
  "error": "Database connection failed"
}
```

### Parameters

| Parameter | Type | Default | Description |
| ----------- | ------ | --------- | ------------- |
| `theme` | string | `flat` | Badge theme: `flat`, `flat-square`, `for-the-badge`, `plastic` |

### Rate Limits

- **User badges**: 10 requests/minute
- **Repository badges**: 10 requests/minute (cost: 2)
- **Star counts**: 10 requests/minute (cost: 2)

## Usage Examples

### In Markdown (README files)

#### User Total Stars

```markdown
![GitHub Stars](https://img.shields.io/endpoint?url=https://your-domain.com/api/v1/badge/user/torvalds)
```

#### Repository Stars

```markdown
![VS Code Stars](https://img.shields.io/endpoint?url=https://your-domain.com/api/v1/badge/repo/microsoft/vscode)
```

#### With Custom Theme

```markdown
![Stars](https://img.shields.io/endpoint?url=https://your-domain.com/api/v1/badge/user/torvalds&theme=for-the-badge)
```

### In HTML

```html
<img src="https://your-domain.com/api/v1/badge/user/torvalds" alt="GitHub Stars" />
```

### Programmatic Usage

#### Python

```python
import requests

# Get star count
response = requests.get("http://localhost:8000/api/v1/stars/microsoft/vscode")
data = response.json()
print(f"VS Code has {data['stars']:,} stars")

# Get badge URL
badge_url = "http://localhost:8000/api/v1/badge/repo/microsoft/vscode?theme=flat-square"
```

#### JavaScript

```javascript
// Fetch star count
fetch('http://localhost:8000/api/v1/stars/microsoft/vscode')
  .then(res => res.json())
  .then(data => console.log(`${data.stars} stars`));

// Use badge in HTML
const img = document.createElement('img');
img.src = 'http://localhost:8000/api/v1/badge/repo/microsoft/vscode';
document.body.appendChild(img);
```

#### cURL

```bash
# Get star count
curl http://localhost:8000/api/v1/stars/microsoft/vscode

# Get badge (returns SVG)
curl http://localhost:8000/api/v1/badge/repo/microsoft/vscode
```

## Configuration

### Environment Variables

| Variable | Default | Description |
| ---------- | --------- | ------------- |
| `GITHUB_TOKEN` | None | GitHub personal access token for higher rate limits |
| `RATE_LIMIT` | 10 | Number of requests allowed per period |
| `RATE_LIMIT_COST` | 2 | Cost per request for rate limiting |
| `RATE_LIMIT_PERIOD` | minute | Time period for rate limiting (e.g., minute, hour) |
| `LOG_LEVEL` | INFO | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `DB_PATH` | store.db | Path to LMDB database file |
| `INDEX_PATH` | index.db | Path to LMDB index file |

### GitHub Token Setup

1. Go to [GitHub Settings > Developer settings > Personal access tokens](https://github.com/settings/tokens)
2. Generate a new token with `public_repo` scope
3. Set environment variable: `export GITHUB_TOKEN=your_token_here`
4. Restart the server

**Benefits:** Increases rate limit from 60 to 5000 requests/hour.

## Architecture

```arch
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI App   │───▶│   LMDB Cache    │───▶│  GitHub API     │
│                 │◀───│   (Persistent)  │◀───│  (Live Data)    │
│ • Rate Limiting │    │ • Fast Lookup   │    │ • Star Counts    │
│ • Error Handling│    │ • TTL Support   │    │ • Rate Limited   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Components

- **FastAPI**: Modern async web framework
- **httpx**: Async HTTP client for GitHub API
- **LMDB**: Lightning-fast embedded database
- **slowapi**: Rate limiting middleware
- **shields.io**: Badge generation service

## Development

### Setup Development Environment

```bash
# Install dev dependencies (if available)
pip install -r requirements-dev.txt

# Run with auto-reload
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

## Testing

Run the test suite:

```bash
pytest
```

## Linting

Run linting:

```bash
pylint src/
```

### Project Structure

```
github-stars-badge/
├── src/
│   ├── __init__.py      # Package initialization
│   ├── __main__.py      # Entry point for python -m src
│   ├── main.py          # FastAPI application
│   ├── config.py        # Configuration constants
│   ├── models.py        # Pydantic models
│   ├── services.py      # GitHub service layer
│   ├── utils.py         # Utility functions
│   ├── dbmanager.py     # Database management utilities
│   └── storage/
│       ├── __init__.py  # Storage package
│       ├── db.py        # LMDB database wrapper
│       └── hashcrypto.py # Hashing utilities
├── tests/               # Test suite
│   ├── conftest.py      # Pytest configuration
│   ├── test_api.py      # API endpoint tests
│   ├── test_caching.py  # Caching functionality tests
│   └── test_github.py   # GitHub API integration tests
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

### Development Guidelines

- Follow PEP 8 style guidelines
- Add type hints to new functions
- Write tests for new features
- Update documentation for API changes
- Use conventional commit messages

## Testing

Run the test suite:

```bash
pytest
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) - Modern async web framework
- [shields.io](https://shields.io/) - Beautiful badge generation
- [LMDB](https://www.symas.com/lmdb) - High-performance database
- [GitHub API](https://docs.github.com/en/rest) - Star count data source

## Support

- **Email**: [radiationbolt@gmail.com]
- **Issues**: [GitHub Issues](https://github.com/rawbytedev/github-stars-badge/issues)
- **Discussions**: [GitHub Discussions](https://github.com/rawbytedev/github-stars-badge/discussions)

---

**Made with ❤️ for the open source community**

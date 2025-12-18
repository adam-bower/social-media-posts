# Social Media Post Creator

## Project Overview

A platform for generating social media posts (text + images) using AI. Focus is on **content creation**, not scheduling or management (Postiz handles that at social.ab-civil.com).

## Key Information

| Field | Value |
|-------|-------|
| **Repo** | https://github.com/adam-bower/social-media-posts |
| **Deployment Target** | Hetzner DE (88.99.51.122) |
| **Future Integration** | Windmill (workflow.ab-civil.com) |
| **Primary Language** | Python |

## Architecture Goals

1. **Local-first development** - Test everything locally before deployment
2. **Windmill-compatible** - Scripts should use `def main()` pattern with typed params
3. **Docker deployment** - Will run as a service on Hetzner behind Caddy
4. **API-driven** - Expose endpoints for post generation

## Available Services

### AI/LLM (Content Generation)
- **Anthropic Claude** - Primary for text generation
- **OpenAI** - GPT-4 for alternatives, DALL-E for images
- **Gemini** - Google's model
- **OpenRouter** - Access to multiple models

### Vision/Image
- **Qwen VL** - Self-hosted vision model at vision.ab-civil.com
- **Azure CV** - OCR for extracting text from reference images

### Storage & Database
- **Supabase** - PostgreSQL at db.ab-civil.com
- **Seafile** - File storage at files.ab-civil.com

### Notifications
- **Slack** - LinkedIn bot and Project Pulse for previews/alerts

## Development Pattern

### Script Structure (Windmill-compatible)
```python
import os
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()

def main(
    topic: str,
    platform: str = "linkedin",
    tone: str = "professional"
) -> Dict[str, Any]:
    """
    Generate a social media post.

    Args:
        topic: What the post should be about
        platform: Target platform (linkedin, twitter, facebook)
        tone: Writing tone (professional, casual, humorous)

    Returns:
        Dictionary with generated content
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")

    # Your logic here

    return {
        "success": True,
        "text": generated_text,
        "hashtags": hashtags,
        "platform": platform
    }

if __name__ == "__main__":
    # Local testing
    result = main(topic="civil engineering innovation", platform="linkedin")
    print(result)
```

### Converting to Windmill Later
```python
# Change os.getenv() to wmill.get_variable()
import wmill

def main(topic: str, platform: str = "linkedin") -> Dict[str, Any]:
    api_key = wmill.get_variable("f/ai/anthropic/api_key")
    # ... rest of code
```

## Deployment Target

### Hetzner DE Server (88.99.51.122)
- **SSH**: `ssh -i ~/.ssh/id_ed25519_robot admin@88.99.51.122`
- **Docker**: All services run in containers
- **Port binding**: Must use `127.0.0.1:PORT:PORT` (Caddy handles SSL)
- **Location**: Will be `/opt/social-media-posts/`

### Caddy Config (when ready)
```
posts.ab-civil.com {
    reverse_proxy 127.0.0.1:PORT
}
```

## Project Structure (Planned)

```
social-media-posts/
├── CLAUDE.md              # This file
├── .env                   # API keys (never commit)
├── .gitignore
├── requirements.txt       # Python dependencies
├── scripts/               # Standalone generation scripts
│   ├── generate_post.py
│   ├── generate_image.py
│   └── analyze_image.py
├── src/                   # Core library code
│   ├── __init__.py
│   ├── llm/              # LLM integrations
│   ├── platforms/        # Platform-specific formatters
│   └── templates/        # Post templates
├── api/                   # FastAPI endpoints (later)
└── docker/               # Docker deployment files
    ├── Dockerfile
    └── docker-compose.yml
```

## Core Features (To Build)

1. **Text Generation**
   - Generate posts from topics/prompts
   - Platform-specific formatting (character limits, hashtag styles)
   - Tone customization
   - Multi-variant generation for A/B testing

2. **Image Generation**
   - Generate images via DALL-E or other APIs
   - Resize/format for different platforms
   - Add text overlays if needed

3. **Image Analysis**
   - Analyze reference images with Qwen VL
   - Extract text from images with Azure CV
   - Generate posts inspired by images

4. **Templates**
   - Industry-specific templates (civil engineering, construction)
   - Holiday/seasonal templates
   - Announcement templates

## Quick Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run a script
python scripts/generate_post.py

# Test locally
python -m pytest tests/
```

## Related Projects

- **Postiz** (social.ab-civil.com) - Social media scheduling/management
- **Windmill** (workflow.ab-civil.com) - Workflow automation platform
- **server-manager** - Hetzner server documentation

## TODO

- [ ] Set up basic project structure
- [ ] Create text generation script with Claude
- [ ] Add platform formatters (LinkedIn, Twitter, Facebook)
- [ ] Integrate image generation
- [ ] Build FastAPI endpoints
- [ ] Create Docker deployment
- [ ] Deploy to Hetzner
- [ ] (Later) Convert scripts for Windmill

# RunningCoach Backend

AI-powered running coach with Garmin integration.

## Setup

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload
```

## Testing

```bash
pytest tests/ -v
```

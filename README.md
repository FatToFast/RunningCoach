# RunningCoach

AI-powered running coach with Garmin integration.

## Overview

RunningCoach는 Garmin 데이터를 기반으로 AI가 생성한 과학적 훈련 계획을 제공하는 개인 러닝 코치 애플리케이션입니다.

## Features

- **Garmin 연동**: 활동, 수면, 심박수 데이터 자동 동기화
- **대시보드**: 주간/월간 요약 및 트렌드 분석
- **워크아웃 관리**: 워크아웃 생성 및 Garmin 전송
- **AI 훈련 계획** (예정): 가이드라인 기반 개인화 훈련 계획

## Documentation

- [Blueprint](docs/blueprint.md) - 프로젝트 청사진
- [MVP](docs/MVP.md) - MVP 명세
- [PRD](docs/PRD.md) - 제품 요구사항 문서

## Tech Stack

### Backend
- Python 3.11+
- FastAPI
- SQLAlchemy 2.0
- PostgreSQL + TimescaleDB
- Redis
- garminconnect

### Frontend
- SvelteKit (예정)
- TailwindCSS
- ECharts

### Infrastructure
- Docker + Docker Compose
- NAS 배포

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.11+ (로컬 개발 시)

### Development Setup

1. Clone the repository
```bash
git clone <repository-url>
cd RunningCoach
```

2. Copy environment variables
```bash
cp backend/.env.example backend/.env
# Edit .env with your Garmin credentials
```

3. Start services with Docker Compose
```bash
docker-compose up -d
```

4. Access the API
- API Docs: http://localhost:8000/api/v1/docs
- Health Check: http://localhost:8000/health

### Local Development (without Docker)

1. Create virtual environment
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
```

2. Install dependencies
```bash
pip install -e ".[dev]"
```

3. Start PostgreSQL and Redis (using Docker)
```bash
docker-compose up -d db redis
```

4. Run the development server
```bash
uvicorn app.main:app --reload
```

### HTTPS 로컬 개발 (권장)

쿠키 기반 인증이 정상 작동하려면 HTTPS가 필요합니다.

1. mkcert 설치 및 인증서 생성
```bash
brew install mkcert
mkcert -install
mkcert localhost 127.0.0.1 ::1
```

2. HTTPS로 서버 실행
```bash
uvicorn app.main:app --reload --ssl-keyfile=localhost+2-key.pem --ssl-certfile=localhost+2.pem
```

3. Frontend 환경변수 설정
```bash
# frontend/.env.local
VITE_API_URL=https://localhost:8000/api/v1
```

## Project Structure

```
RunningCoach/
├── backend/
│   ├── app/
│   │   ├── api/           # API endpoints
│   │   │   └── v1/
│   │   ├── adapters/      # External service adapters
│   │   ├── core/          # Configuration, database
│   │   ├── models/        # SQLAlchemy models
│   │   ├── schemas/       # Pydantic schemas
│   │   ├── services/      # Business logic
│   │   └── main.py        # FastAPI app
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/              # SvelteKit (예정)
├── docs/
│   ├── blueprint.md
│   ├── MVP.md
│   └── PRD.md
├── docker-compose.yml
└── README.md
```

## API Endpoints

### Auth
- `POST /api/v1/auth/garmin/connect` - Garmin 계정 연결
- `GET /api/v1/auth/status` - 연결 상태 확인

### Ingest (Data Sync)
- `POST /api/v1/ingest/run` - 수동 동기화
- `GET /api/v1/ingest/status` - 동기화 상태

### Activities
- `GET /api/v1/activities` - 활동 목록
- `GET /api/v1/activities/{id}` - 활동 상세

### Dashboard
- `GET /api/v1/dashboard/summary` - 주간 요약
- `GET /api/v1/dashboard/trends` - 트렌드 데이터

### Workouts
- `POST /api/v1/workouts` - 워크아웃 생성
- `POST /api/v1/workouts/{id}/push` - Garmin 전송
- `POST /api/v1/workouts/{id}/schedule` - 스케줄링

## Contributing

1. Create a feature branch
2. Make your changes
3. Run tests: `pytest`
4. Run linting: `ruff check .`
5. Submit a pull request

## License

MIT License

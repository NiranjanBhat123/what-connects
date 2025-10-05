# WhatConnects - Multiplayer Quiz Game

A real-time multiplayer quiz game where players connect random words to find common connections. Built with Django, WebSockets, and React.

## 🎮 Game Features

- **2-6 Players**: Multiplayer support for up to 6 players
- **10 Questions per Game**: Each game consists of 10 multiple-choice questions
- **30-Second Time Limit**: Quick-thinking required for each question
- **Hint System**: Players can take hints (affects scoring)
- **Real-time Leaderboard**: Live updates after each question
- **AI-Generated Questions**: Powered by Google Gemini AI

## 🏗️ Architecture

### Backend (Django REST Framework)
- **Django 5.0**: Web framework
- **Django Channels**: WebSocket support
- **PostgreSQL**: Primary database
- **Redis**: Cache and WebSocket channel layer
- **Google Gemini AI**: Question generation

### Frontend (Coming Soon)
- **React**: UI library
- **shadcn/ui**: Component library
- **WebSocket**: Real-time communication

## 📁 Project Structure

```
whatconnects/
├── backend/
│   ├── apps/
│   │   ├── core/          # Core utilities and base models
│   │   ├── users/         # User management & authentication
│   │   ├── rooms/         # Game room management
│   │   ├── games/         # Game logic and questions
│   │   └── websockets/    # WebSocket consumers
│   ├── config/            # Django settings and configuration
│   └── requirements/      # Python dependencies
├── docker/                # Dockerfiles
├── .github/workflows/     # CI/CD pipelines
└── docker-compose.yml     # Development environment
```

## 🚀 Getting Started

### Prerequisites

- Docker & Docker Compose
- Google Gemini API Key ([Get one here](https://makersuite.google.com/app/apikey))

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/whatconnects.git
cd whatconnects
```

2. **Set up environment variables**
```bash
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

3. **Build and start services**
```bash
docker-compose up --build
```

4. **Run migrations**
```bash
docker-compose exec backend python manage.py migrate
```

5. **Create a superuser (optional)**
```bash
docker-compose exec backend python manage.py createsuperuser
```

6. **Access the application**
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/api/docs/
- Admin Panel: http://localhost:8000/admin/
- WebSocket: ws://localhost:8001

## 🧪 Running Tests

```bash
# Run all tests
docker-compose exec backend pytest

# Run with coverage
docker-compose exec backend pytest --cov=apps --cov-report=html

# Run specific test file
docker-compose exec backend pytest apps/games/tests/test_models.py

# Run tests with specific markers
docker-compose exec backend pytest -m unit
```

## 🔧 Development

### Code Quality

```bash
# Format code with black
docker-compose exec backend black .

# Sort imports
docker-compose exec backend isort .

# Lint with flake8
docker-compose exec backend flake8 .

# Type checking
docker-compose exec backend mypy apps/
```

### Database Management

```bash
# Create migrations
docker-compose exec backend python manage.py makemigrations

# Apply migrations
docker-compose exec backend python manage.py migrate

# Create superuser
docker-compose exec backend python manage.py createsuperuser

# Access Django shell
docker-compose exec backend python manage.py shell
```

### Logs

```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f backend
docker-compose logs -f db
docker-compose logs -f redis
```

## 📊 API Endpoints

### Authentication
- `POST /api/v1/users/register/` - Register new user
- `POST /api/v1/users/login/` - Login user
- `POST /api/v1/users/token/refresh/` - Refresh JWT token

### Rooms
- `POST /api/v1/rooms/create/` - Create new game room
- `POST /api/v1/rooms/join/` - Join existing room
- `GET /api/v1/rooms/{room_code}/` - Get room details
- `POST /api/v1/rooms/{room_code}/start/` - Start game (host only)

### Games
- `GET /api/v1/games/{game_id}/` - Get game details
- `POST /api/v1/games/{game_id}/answer/` - Submit answer
- `GET /api/v1/games/{game_id}/leaderboard/` - Get current leaderboard

### WebSocket Events
- `ws://localhost:8001/ws/room/{room_code}/` - Room WebSocket connection

## 🎯 Game Scoring

- **Correct Answer**: +10 points
- **Correct Answer (with hint)**: +5 points
- **Wrong Answer**: 0 points
- **Wrong Answer (with hint)**: -5 points

## 🐳 Docker Commands

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# Rebuild services
docker-compose up --build

# View running containers
docker-compose ps

# Remove volumes (WARNING: Deletes all data)
docker-compose down -v
```

## 🚢 Production Deployment

```bash
# Build production images
docker-compose -f docker-compose.prod.yml build

# Start production services
docker-compose -f docker-compose.prod.yml up -d

# Run production migrations
docker-compose -f docker-compose.prod.yml exec backend python manage.py migrate

# Collect static files
docker-compose -f docker-compose.prod.yml exec backend python manage.py collectstatic --noinput
```

## 📝 Environment Variables

See `.env.example` for all available environment variables.

Key variables:
- `GEMINI_API_KEY`: Google Gemini AI API key (required)
- `SECRET_KEY`: Django secret key
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `DEBUG`: Debug mode (True/False)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License.

## 🙏 Acknowledgments

- Google Gemini AI for question generation
- Django & Django REST Framework communities
- shadcn/ui for beautiful React components

## 📧 Contact

Your Name - your.email@example.com

Project Link: [https://github.com/yourusername/whatconnects](https://github.com/yourusername/whatconnects)

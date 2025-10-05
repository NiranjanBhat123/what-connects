#!/bin/bash

# WhatConnects Setup Script
# This script sets up the complete project structure

set -e

echo "🎮 Setting up WhatConnects Backend..."

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Create main project structure
echo -e "${BLUE}Creating project structure...${NC}"

mkdir -p backend/apps/{core,users,rooms,games,websockets}/{migrations,tests}
mkdir -p backend/config/settings
mkdir -p backend/requirements
mkdir -p docker/{backend,nginx}
mkdir -p .github/workflows

# Create __init__.py files
echo -e "${BLUE}Creating Python package files...${NC}"

# Config init files
touch backend/config/__init__.py
touch backend/config/settings/__init__.py

# Apps init files
touch backend/apps/__init__.py
touch backend/apps/core/__init__.py
touch backend/apps/users/__init__.py
touch backend/apps/rooms/__init__.py
touch backend/apps/games/__init__.py
touch backend/apps/websockets/__init__.py

# Migrations init files
touch backend/apps/core/migrations/__init__.py
touch backend/apps/users/migrations/__init__.py
touch backend/apps/rooms/migrations/__init__.py
touch backend/apps/games/migrations/__init__.py
touch backend/apps/websockets/migrations/__init__.py

# Tests init files
touch backend/apps/core/tests/__init__.py
touch backend/apps/users/tests/__init__.py
touch backend/apps/rooms/tests/__init__.py
touch backend/apps/games/tests/__init__.py
touch backend/apps/websockets/tests/__init__.py

# Create manage.py
echo -e "${BLUE}Creating manage.py...${NC}"
cat > backend/manage.py << 'EOF'
#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
EOF

chmod +x backend/manage.py

# Create empty app files
echo -e "${BLUE}Creating app structure files...${NC}"

# Core app files
touch backend/apps/core/{admin.py,apps.py,serializers.py}

# Users app files
touch backend/apps/users/{admin.py,apps.py,models.py,serializers.py,urls.py,views.py}

# Rooms app files
touch backend/apps/rooms/{admin.py,apps.py,models.py,serializers.py,urls.py,views.py}

# Games app files
touch backend/apps/games/{admin.py,apps.py,models.py,serializers.py,urls.py,views.py,services.py}

# WebSockets app files
touch backend/apps/websockets/{apps.py,consumers.py,routing.py}

# Create apps.py for core
cat > backend/apps/core/apps.py << 'EOF'
from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'
EOF

# Create apps.py for users
cat > backend/apps/users/apps.py << 'EOF'
from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.users'
EOF

# Create apps.py for rooms
cat > backend/apps/rooms/apps.py << 'EOF'
from django.apps import AppConfig


class RoomsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.rooms'
EOF

# Create apps.py for games
cat > backend/apps/games/apps.py << 'EOF'
from django.apps import AppConfig


class GamesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.games'
EOF

# Create apps.py for websockets
cat > backend/apps/websockets/apps.py << 'EOF'
from django.apps import AppConfig


class WebsocketsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.websockets'
EOF

# Create basic routing.py for websockets
cat > backend/apps/websockets/routing.py << 'EOF'
"""
WebSocket URL routing.
"""
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/room/(?P<room_code>\w+)/$', consumers.GameRoomConsumer.as_asgi()),
]
EOF

echo -e "${GREEN}✅ Project structure created successfully!${NC}"

echo -e "${YELLOW}Next steps:${NC}"
echo -e "1. Copy .env.example to .env and add your GEMINI_API_KEY"
echo -e "2. Run: ${BLUE}docker-compose up --build${NC}"
echo -e "3. In another terminal, run: ${BLUE}docker-compose exec backend python manage.py migrate${NC}"
echo -e "4. Create superuser: ${BLUE}docker-compose exec backend python manage.py createsuperuser${NC}"
echo -e "5. Visit: ${BLUE}http://localhost:8000/api/docs/${NC}"

echo -e "${GREEN}🎉 Setup complete!${NC}"
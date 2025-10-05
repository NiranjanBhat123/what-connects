"""
Game services for question generation.
"""
import json
import logging
from typing import List, Dict, Any
from django.conf import settings
from django.db import transaction
from .models import Question, Game
from ..core.exceptions import QuestionGenerationException

logger = logging.getLogger(__name__)


class QuestionGeneratorService:
    """Service for generating game questions using Gemini AI."""

    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.model_name = getattr(settings, 'GEMINI_MODEL', 'gemini-pro')

        if not self.api_key:
            logger.warning("GEMINI_API_KEY not configured, will use sample questions")

    @transaction.atomic
    def generate_questions(self, game: Game, num_questions: int = 10) -> List[Question]:
        """
        Generate questions for a game.

        Args:
            game: Game instance
            num_questions: Number of questions to generate

        Returns:
            List of created Question instances

        Raises:
            QuestionGenerationException: If generation fails critically
        """
        try:
            if not self.api_key:
                logger.info(f"Using sample questions for game {game.id}")
                return self._create_sample_questions(game, num_questions)

            # Use Gemini AI to generate questions
            logger.info(f"Generating {num_questions} questions using Gemini AI for game {game.id}")
            questions_data = self._fetch_questions_from_gemini(num_questions)
            questions = self._create_questions_from_data(game, questions_data)

            logger.info(f"Successfully generated {len(questions)} questions for game {game.id}")
            return questions

        except QuestionGenerationException:
            raise
        except Exception as e:
            logger.error(f"Failed to generate questions for game {game.id}: {str(e)}", exc_info=True)
            # Fallback to sample questions
            logger.info(f"Falling back to sample questions for game {game.id}")
            return self._create_sample_questions(game, num_questions)

    def _fetch_questions_from_gemini(self, num_questions: int) -> List[Dict[str, Any]]:
        """
        Fetch questions from Gemini AI API.

        Args:
            num_questions: Number of questions to generate

        Returns:
            List of question data dictionaries

        Raises:
            QuestionGenerationException: If API call fails
        """
        try:
            import google.generativeai as genai

            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(self.model_name)

            prompt = self._build_prompt(num_questions)

            response = model.generate_content(prompt)

            if not response.text:
                raise QuestionGenerationException("Empty response from Gemini API")

            # Extract and parse JSON from response
            questions_data = self._parse_gemini_response(response.text)

            # Validate the data
            self._validate_questions_data(questions_data, num_questions)

            return questions_data

        except ImportError:
            logger.error("google-generativeai package not installed")
            raise QuestionGenerationException(
                "AI service not available - google-generativeai package not installed"
            )
        except Exception as e:
            logger.error(f"Gemini API error: {str(e)}", exc_info=True)
            raise QuestionGenerationException(f"Failed to generate questions from AI: {str(e)}")

    def _build_prompt(self, num_questions: int) -> str:
        """Build the prompt for Gemini AI."""
        return f"""Generate {num_questions} "What Connects" quiz questions. Each question should have:
- 4 items that share a common connection
- A clear, concise answer explaining what connects them
- An optional hint (can be empty string if no hint needed)

IMPORTANT: Make sure all items in a question are related to the same answer.

Format as a JSON array ONLY (no markdown, no explanations):
[
  {{
    "items": ["item1", "item2", "item3", "item4"],
    "answer": "what connects them",
    "hint": "optional hint or empty string"
  }}
]

Guidelines:
- Make questions varied and interesting across different topics (history, pop culture, science, geography, sports, entertainment, etc.)
- Ensure the connection is clear but not too obvious
- Keep answers concise (under 100 characters)
- Make hints helpful but not give away the answer
- Avoid offensive or controversial topics

Return ONLY the JSON array, nothing else."""

    def _parse_gemini_response(self, response_text: str) -> List[Dict[str, Any]]:
        """Parse the JSON response from Gemini."""
        text = response_text.strip()

        # Remove markdown code blocks if present
        if text.startswith('```json'):
            text = text[7:]
        elif text.startswith('```'):
            text = text[3:]

        if text.endswith('```'):
            text = text[:-3]

        text = text.strip()

        try:
            questions_data = json.loads(text)
            if not isinstance(questions_data, list):
                raise ValueError("Response is not a JSON array")
            return questions_data
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {text[:200]}")
            raise QuestionGenerationException(f"Invalid JSON response from AI: {str(e)}")

    def _validate_questions_data(self, questions_data: List[Dict[str, Any]], expected_count: int):
        """Validate the questions data structure."""
        if len(questions_data) < expected_count:
            logger.error(
                f"Generated {len(questions_data)} questions, expected {expected_count}"
            )
            raise QuestionGenerationException(
                f"Insufficient questions generated. Expected {expected_count}, got {len(questions_data)}."
            )

        for idx, q_data in enumerate(questions_data):
            if not isinstance(q_data, dict):
                raise QuestionGenerationException(f"Question {idx} is not a dictionary")

            if 'items' not in q_data or 'answer' not in q_data:
                raise QuestionGenerationException(
                    f"Question {idx} missing required fields (items, answer)"
                )

            if not isinstance(q_data['items'], list) or len(q_data['items']) != 4:
                raise QuestionGenerationException(
                    f"Question {idx} must have exactly 4 items"
                )

            # Validate all items are non-empty strings
            for item_idx, item in enumerate(q_data['items']):
                if not isinstance(item, str) or not item.strip():
                    raise QuestionGenerationException(
                        f"Question {idx}, item {item_idx} is invalid or empty"
                    )

            if not q_data['answer'].strip():
                raise QuestionGenerationException(f"Question {idx} has empty answer")

            # Validate answer length
            if len(q_data['answer']) > 500:
                raise QuestionGenerationException(
                    f"Question {idx} answer exceeds 500 characters"
                )

    def _create_questions_from_data(self, game: Game, questions_data: List[Dict[str, Any]]) -> List[Question]:
        """Create Question instances from generated data."""
        questions = []
        time_limit = settings.GAME_SETTINGS.get('TIME_LIMIT_SECONDS', 30)

        for idx, q_data in enumerate(questions_data):
            question = Question.objects.create(
                game=game,
                order=idx,
                text="What connects these four items?",
                items=q_data.get('items', []),
                correct_answer=q_data.get('answer', '').strip(),
                hint=q_data.get('hint', '').strip(),
                time_limit=time_limit
            )
            questions.append(question)

        return questions

    def _create_sample_questions(self, game: Game, num_questions: int) -> List[Question]:
        """Create sample questions as fallback."""
        sample_questions = [
            {
                "items": ["Mercury", "Venus", "Earth", "Mars"],
                "answer": "Inner planets of the solar system",
                "hint": "They're all closer to the Sun than the asteroid belt"
            },
            {
                "items": ["Paris", "Rome", "London", "Berlin"],
                "answer": "European capital cities",
                "hint": "Each is the capital of a major European country"
            },
            {
                "items": ["Leonardo da Vinci", "Michelangelo", "Raphael", "Donatello"],
                "answer": "Renaissance artists and Ninja Turtles",
                "hint": "Famous artists from the Renaissance period"
            },
            {
                "items": ["Red", "Orange", "Yellow", "Green"],
                "answer": "Colors in the rainbow",
                "hint": "They appear in a specific light spectrum"
            },
            {
                "items": ["Spring", "Summer", "Autumn", "Winter"],
                "answer": "The four seasons",
                "hint": "They repeat every year"
            },
            {
                "items": ["Heart", "Diamond", "Club", "Spade"],
                "answer": "Suits in a deck of cards",
                "hint": "Found on playing cards"
            },
            {
                "items": ["Apple", "Microsoft", "Google", "Amazon"],
                "answer": "Major tech companies",
                "hint": "They're all trillion-dollar companies"
            },
            {
                "items": ["Lion", "Tiger", "Leopard", "Jaguar"],
                "answer": "Big cats",
                "hint": "All are large felines"
            },
            {
                "items": ["Guitar", "Piano", "Violin", "Drums"],
                "answer": "Musical instruments",
                "hint": "Used to create music"
            },
            {
                "items": ["Gold", "Silver", "Bronze", "Copper"],
                "answer": "Metallic elements",
                "hint": "All are types of metal"
            },
            {
                "items": ["Pacific", "Atlantic", "Indian", "Arctic"],
                "answer": "Earth's oceans",
                "hint": "Large bodies of saltwater"
            },
            {
                "items": ["Shakespeare", "Dickens", "Austen", "Orwell"],
                "answer": "Famous British authors",
                "hint": "All wrote classic English literature"
            },
            {
                "items": ["Nile", "Amazon", "Yangtze", "Mississippi"],
                "answer": "Major rivers of the world",
                "hint": "Long flowing bodies of water"
            },
            {
                "items": ["Jupiter", "Saturn", "Uranus", "Neptune"],
                "answer": "Gas giant planets",
                "hint": "Outer planets of the solar system"
            },
            {
                "items": ["Football", "Basketball", "Tennis", "Cricket"],
                "answer": "Popular sports",
                "hint": "Games played with balls"
            },
            {
                "items": ["Hydrogen", "Helium", "Oxygen", "Nitrogen"],
                "answer": "Chemical elements",
                "hint": "Found on the periodic table"
            },
            {
                "items": ["Washington DC", "Ottawa", "Mexico City", "Havana"],
                "answer": "North American capital cities",
                "hint": "Capitals of countries in North America"
            },
            {
                "items": ["Toyota", "Honda", "Ford", "BMW"],
                "answer": "Car manufacturers",
                "hint": "Companies that make automobiles"
            },
            {
                "items": ["Mandarin", "Spanish", "English", "Hindi"],
                "answer": "Most spoken languages",
                "hint": "Languages spoken by millions"
            },
            {
                "items": ["Python", "Java", "JavaScript", "C++"],
                "answer": "Programming languages",
                "hint": "Used for software development"
            }
        ]

        questions = []
        time_limit = settings.GAME_SETTINGS.get('TIME_LIMIT_SECONDS', 30)

        # Use only the requested number of questions
        for idx in range(min(num_questions, len(sample_questions))):
            q_data = sample_questions[idx]
            question = Question.objects.create(
                game=game,
                order=idx,
                text="What connects these four items?",
                items=q_data['items'],
                correct_answer=q_data['answer'],
                hint=q_data.get('hint', ''),
                time_limit=time_limit
            )
            questions.append(question)

        return questions


class GameService:
    """Service for game-related operations."""

    def __init__(self):
        self.question_generator = QuestionGeneratorService()

    @transaction.atomic
    def start_game(self, game: Game, num_questions: int = 10) -> Game:
        """
        Start a game by generating questions.

        Args:
            game: Game instance
            num_questions: Number of questions to generate

        Returns:
            Updated Game instance

        Raises:
            QuestionGenerationException: If question generation fails
        """
        if game.status != 'active':
            raise ValueError("Game is not in active status")

        # Generate questions
        questions = self.question_generator.generate_questions(game, num_questions)

        if not questions:
            raise QuestionGenerationException("No questions were generated")

        logger.info(f"Game {game.id} started with {len(questions)} questions")
        return game

    def get_game_progress(self, game: Game) -> Dict[str, Any]:
        """
        Get game progress information.

        Args:
            game: Game instance

        Returns:
            Dictionary with progress information
        """
        total_questions = game.total_questions
        current_index = game.current_question_index

        progress_percentage = 0
        if total_questions > 0:
            progress_percentage = round((current_index / total_questions) * 100, 2)

        return {
            'game_id': str(game.id),
            'status': game.status,
            'current_question_index': current_index,
            'total_questions': total_questions,
            'progress_percentage': progress_percentage,
            'is_completed': game.is_completed,
        }

    def calculate_final_rankings(self, game: Game) -> List[Dict[str, Any]]:
        """
        Calculate and return final rankings for a completed game.

        Args:
            game: Game instance

        Returns:
            List of player rankings with detailed stats
        """
        from .models import GameScore

        scores = GameScore.objects.filter(game=game).select_related('player').order_by(
            '-total_score', 'created_at'
        )

        rankings = []
        current_rank = 1
        previous_score = None
        rank_counter = 1

        for score in scores:
            # Handle ties - same score gets same rank
            if previous_score is not None and score.total_score < previous_score:
                current_rank = rank_counter

            score.rank = current_rank
            score.save(update_fields=['rank'])

            rankings.append({
                'rank': current_rank,
                'player_id': str(score.player.id),
                'player_username': score.player.username,
                'total_score': score.total_score,
                'correct_answers': score.correct_answers,
                'wrong_answers': score.wrong_answers,
                'accuracy': score.accuracy,
            })

            previous_score = score.total_score
            rank_counter += 1

        return rankings
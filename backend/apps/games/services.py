"""
Game services for question generation - MCQ Format.
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
        return f"""Generate {num_questions} "What Connects" MCQ quiz questions. 

The game format:
- Show 4 items (words/short phrases) that have a common connection
- Players must identify the connection from 4 multiple choice options
- 1 correct answer, 3 plausible wrong answers
- A subtle hint that helps but doesn't give away the answer

Example question:
Items: ["Newton", "Steve Jobs", "Adam and Eve", "A forbidden fruit"]
Options: ["Apple", "Microsoft", "Garden", "Gravity"]
Correct Answer: "Apple"
Hint: "This connects a tech giant, biblical story, physics, and fruit"

Another example:
Items: ["Superman", "Batman", "Wonder Woman", "The Flash"]
Options: ["DC Comics", "Marvel", "Avengers", "X-Men"]
Correct Answer: "DC Comics"
Hint: "A comic book universe known for dark, serious superhero films"

Format as JSON array ONLY (no markdown, no explanations):
[
  {{
    "items": ["item1", "item2", "item3", "item4"],
    "options": ["option1", "option2", "option3", "option4"],
    "correct_answer": "option1",
    "hint": "subtle hint that helps narrow down"
  }}
]

Guidelines:
- Make questions varied across topics (pop culture, history, geography, science, sports, brands, entertainment)
- Ensure all 4 items genuinely connect to the answer
- Make wrong options plausible but clearly incorrect when thought through
- Hints should be helpful but not obvious - they narrow possibilities without revealing
- Correct answer must be one of the 4 options (exact match)
- Keep items and options concise (1-4 words each)
- Difficulty: Medium (not too easy, not impossible)

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
            logger.warning(
                f"Generated {len(questions_data)} questions, expected {expected_count}"
            )

        for idx, q_data in enumerate(questions_data):
            if not isinstance(q_data, dict):
                raise QuestionGenerationException(f"Question {idx} is not a dictionary")

            required_fields = ['items', 'options', 'correct_answer']
            for field in required_fields:
                if field not in q_data:
                    raise QuestionGenerationException(
                        f"Question {idx} missing required field: {field}"
                    )

            # Validate items (4 items)
            if not isinstance(q_data['items'], list) or len(q_data['items']) != 4:
                raise QuestionGenerationException(
                    f"Question {idx} must have exactly 4 items"
                )

            # Validate options (4 options)
            if not isinstance(q_data['options'], list) or len(q_data['options']) != 4:
                raise QuestionGenerationException(
                    f"Question {idx} must have exactly 4 options"
                )

            # Validate all items and options are non-empty strings
            for item_idx, item in enumerate(q_data['items']):
                if not isinstance(item, str) or not item.strip():
                    raise QuestionGenerationException(
                        f"Question {idx}, item {item_idx} is invalid or empty"
                    )

            for opt_idx, option in enumerate(q_data['options']):
                if not isinstance(option, str) or not option.strip():
                    raise QuestionGenerationException(
                        f"Question {idx}, option {opt_idx} is invalid or empty"
                    )

            # Validate correct answer
            if not q_data['correct_answer'].strip():
                raise QuestionGenerationException(f"Question {idx} has empty answer")

            # Verify correct answer is in options
            if q_data['correct_answer'] not in q_data['options']:
                raise QuestionGenerationException(
                    f"Question {idx}: correct_answer must be one of the options"
                )

    def _create_questions_from_data(self, game: Game, questions_data: List[Dict[str, Any]]) -> List[Question]:
        """Create Question instances from generated data."""
        questions = []
        time_limit = settings.GAME_SETTINGS.get('TIME_LIMIT_SECONDS', 30)

        for idx, q_data in enumerate(questions_data):
            question = Question.objects.create(
                game=game,
                order=idx,
                items=q_data.get('items', []),
                options=q_data.get('options', []),
                correct_answer=q_data.get('correct_answer', '').strip(),
                hint=q_data.get('hint', '').strip(),
                time_limit=time_limit
            )
            questions.append(question)

        return questions

    def _create_sample_questions(self, game: Game, num_questions: int) -> List[Question]:
        """Create sample questions as fallback."""
        sample_questions = [
            {
                "items": ["Newton", "Steve Jobs", "New York", "Granny Smith"],
                "options": ["Apple", "Microsoft", "Orange", "Banana"],
                "correct_answer": "Apple",
                "hint": "A company, a fruit, and a physicist's discovery"
            },
            {
                "items": ["Superman", "Batman", "Wonder Woman", "The Flash"],
                "options": ["DC Comics", "Marvel", "Avengers", "X-Men"],
                "correct_answer": "DC Comics",
                "hint": "Publisher of superhero comics with dark, serious films"
            },
            {
                "items": ["Paris", "Eiffel", "Croissant", "Louvre"],
                "options": ["France", "Italy", "Spain", "Germany"],
                "correct_answer": "France",
                "hint": "European country famous for cuisine and romance"
            },
            {
                "items": ["Swoosh", "Just Do It", "Air Jordan", "Oregon"],
                "options": ["Nike", "Adidas", "Puma", "Reebok"],
                "correct_answer": "Nike",
                "hint": "Sports brand founded by athletes in the 1960s"
            },
            {
                "items": ["King", "Crown", "Palace", "Throne"],
                "options": ["Royalty", "Chess", "Cards", "Democracy"],
                "correct_answer": "Royalty",
                "hint": "Related to monarchs and their rule"
            },
            {
                "items": ["Simba", "Nala", "Pride Rock", "Hakuna Matata"],
                "options": ["The Lion King", "Jungle Book", "Madagascar", "Tarzan"],
                "correct_answer": "The Lion King",
                "hint": "Disney movie about a young lion prince"
            },
            {
                "items": ["Gryffindor", "Hogwarts", "Quidditch", "Muggles"],
                "options": ["Harry Potter", "Lord of the Rings", "Narnia", "Percy Jackson"],
                "correct_answer": "Harry Potter",
                "hint": "Wizarding world created by J.K. Rowling"
            },
            {
                "items": ["Pikachu", "Charizard", "Ash", "Pokéballs"],
                "options": ["Pokémon", "Digimon", "Yu-Gi-Oh", "Dragon Ball"],
                "correct_answer": "Pokémon",
                "hint": "Gotta catch 'em all!"
            },
            {
                "items": ["Messi", "Barcelona", "Argentina", "World Cup 2022"],
                "options": ["Football/Soccer", "Basketball", "Cricket", "Tennis"],
                "correct_answer": "Football/Soccer",
                "hint": "The beautiful game played with feet"
            },
            {
                "items": ["Statue of Liberty", "Times Square", "Central Park", "Broadway"],
                "options": ["New York", "Los Angeles", "Chicago", "Boston"],
                "correct_answer": "New York",
                "hint": "The Big Apple, the city that never sleeps"
            },
            {
                "items": ["Pizza", "Pasta", "Colosseum", "Venice"],
                "options": ["Italy", "Greece", "France", "Spain"],
                "correct_answer": "Italy",
                "hint": "Boot-shaped European country famous for food"
            },
            {
                "items": ["Sushi", "Tokyo", "Mt. Fuji", "Samurai"],
                "options": ["Japan", "China", "Korea", "Thailand"],
                "correct_answer": "Japan",
                "hint": "Island nation known for technology and tradition"
            },
            {
                "items": ["Pyramids", "Sphinx", "Nile", "Pharaohs"],
                "options": ["Egypt", "Iraq", "Morocco", "Libya"],
                "correct_answer": "Egypt",
                "hint": "Ancient civilization with iconic monuments"
            },
            {
                "items": ["Kangaroo", "Sydney", "Outback", "Great Barrier Reef"],
                "options": ["Australia", "New Zealand", "Indonesia", "Papua New Guinea"],
                "correct_answer": "Australia",
                "hint": "Island continent down under"
            },
            {
                "items": ["Tea", "Big Ben", "Queen", "London"],
                "options": ["England", "France", "Scotland", "Ireland"],
                "correct_answer": "England",
                "hint": "Part of the United Kingdom with royal history"
            },
            {
                "items": ["C++", "Java", "Python", "JavaScript"],
                "options": ["Programming Languages", "Coffee Types", "Snake Species", "Islands"],
                "correct_answer": "Programming Languages",
                "hint": "Used by software developers to write code"
            },
            {
                "items": ["iPhone", "Mac", "iPad", "AirPods"],
                "options": ["Apple Products", "Samsung Products", "Tech Accessories", "Phone Brands"],
                "correct_answer": "Apple Products",
                "hint": "Devices from a company with a bitten fruit logo"
            },
            {
                "items": ["Spotify", "YouTube Music", "Apple Music", "Deezer"],
                "options": ["Music Streaming", "Video Platforms", "Social Media", "Podcast Apps"],
                "correct_answer": "Music Streaming",
                "hint": "Services for listening to songs online"
            },
            {
                "items": ["Mercury", "Venus", "Earth", "Mars"],
                "options": ["Inner Planets", "Outer Planets", "Gas Giants", "Dwarf Planets"],
                "correct_answer": "Inner Planets",
                "hint": "Rocky planets closest to the Sun"
            },
            {
                "items": ["Heart", "Diamond", "Club", "Spade"],
                "options": ["Card Suits", "Jewelry", "Garden Tools", "Symbols"],
                "correct_answer": "Card Suits",
                "hint": "Found on a standard deck of playing cards"
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
                items=q_data['items'],
                options=q_data['options'],
                correct_answer=q_data['correct_answer'],
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
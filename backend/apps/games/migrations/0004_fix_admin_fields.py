# Generated manually to fix admin field errors
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("games", "0003_remove_question_text_gamescore_hints_used_and_more"),
    ]

    operations = [
        # Make Game.started_at nullable for pending games
        migrations.AlterField(
            model_name="game",
            name="started_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        # Add points_earned field to Answer model
        migrations.AlterField(
            model_name="answer",
            name="points_earned",
            field=models.IntegerField(default=0),
        ),
        # Add rank field to GameScore model (if not exists)
        migrations.AlterField(
            model_name="gamescore",
            name="rank",
            field=models.IntegerField(blank=True, db_index=True, null=True),
        ),
        # Update answer_text max_length to 500
        migrations.AlterField(
            model_name="answer",
            name="answer_text",
            field=models.CharField(max_length=500),
        ),
        # Update correct_answer max_length to 500
        migrations.AlterField(
            model_name="question",
            name="correct_answer",
            field=models.CharField(max_length=500),
        ),
    ]

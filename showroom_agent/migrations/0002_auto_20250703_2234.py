from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('showroom_agent', '0001_initial'),  # Replace with your actual last migration number
    ]

    operations = [
        # First, delete any existing data to avoid conflicts
        migrations.RunSQL("DELETE FROM showroom_agent_chatinteraction;"),
        migrations.RunSQL("DELETE FROM showroom_agent_usersession;"),
        
        # Drop and recreate the table with correct structure
        migrations.RunSQL("DROP TABLE IF EXISTS showroom_agent_usersession CASCADE;"),
        
        # Create the table with proper integer ID
        migrations.RunSQL("""
            CREATE TABLE showroom_agent_usersession (
                id SERIAL PRIMARY KEY,
                session_key VARCHAR(100) UNIQUE,
                preferences JSONB NOT NULL DEFAULT '{}',
                room_type VARCHAR(50),
                style_preference VARCHAR(50),
                budget_range VARCHAR(50),
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                user_id INTEGER REFERENCES auth_user(id) ON DELETE CASCADE
            );
        """),
        
        # Recreate the ChatInteraction table to reference the new UserSession
        migrations.RunSQL("DROP TABLE IF EXISTS showroom_agent_chatinteraction CASCADE;"),
        migrations.RunSQL("""
            CREATE TABLE showroom_agent_chatinteraction (
                id SERIAL PRIMARY KEY,
                session_id INTEGER NOT NULL REFERENCES showroom_agent_usersession(id) ON DELETE CASCADE,
                user_message TEXT NOT NULL,
                ai_response TEXT NOT NULL,
                intent VARCHAR(100),
                extracted_preferences JSONB NOT NULL DEFAULT '{}',
                confidence_score DOUBLE PRECISION,
                timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            );
        """),
        
        # Create index for ordering
        migrations.RunSQL("CREATE INDEX showroom_agent_chatinteraction_timestamp_idx ON showroom_agent_chatinteraction(timestamp);"),
    ]
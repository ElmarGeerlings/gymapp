from django.core.management.base import BaseCommand
from django.conf import settings
from gainz.ai.services import GeminiAIService


class Command(BaseCommand):
    help = 'Test the AI API connection'

    def handle(self, *args, **options):
        self.stdout.write("Testing AI API connection...")

        # Check if API key is loaded
        api_key = getattr(settings, 'GEMINI_API_KEY', None)
        if not api_key:
            self.stdout.write(self.style.ERROR("❌ GEMINI_API_KEY not found in settings"))
            return

        self.stdout.write(f"✅ API key found: {api_key[:10]}...")

        try:
            # Test the API service
            ai_service = GeminiAIService()
            self.stdout.write("✅ GeminiAIService initialized successfully")

            # Test a simple prompt
            response = ai_service.generate_content("Say 'Hello World'")
            if response:
                self.stdout.write(f"✅ API response: {response[:100]}...")
            else:
                self.stdout.write(self.style.WARNING("⚠️ API returned no response"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error: {e}"))

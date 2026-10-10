from django.core.management import call_command
from django.core.management.base import BaseCommand

from trading.services.runtime_config import validate_startup


class Command(BaseCommand):
    help = "Migrate DB, validate config, and ensure demo seed exists (single boot step)"

    def add_arguments(self, parser):
        parser.add_argument("--no-seed", action="store_true", help="Skip seed_demo")

    def handle(self, *args, **options):
        self.stdout.write("Running migrations...")
        call_command("migrate", interactive=False, verbosity=1)
        self.stdout.write("Validating configuration...")
        validate_startup()
        self.stdout.write(self.style.SUCCESS("Configuration OK."))
        if not options["no_seed"]:
            call_command("seed_demo")
        self.stdout.write(
            self.style.SUCCESS(
                "Bootstrap complete. Start the app with: python manage.py runserver 0.0.0.0:8000"
            )
        )

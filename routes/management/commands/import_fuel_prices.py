import csv

from django.core.management.base import BaseCommand
from routes.models import FuelStation


class Command(BaseCommand):
    help = "Replace fuel station data with enriched CSV data"

    def add_arguments(self, parser):
        parser.add_argument("file_path")

    def handle(self, *args, **options):
        file_path = options["file_path"]

        stations = []

        with open(
            file_path,
            mode="r",
            encoding="cp1252",
            newline=""
        ) as file:

            reader = csv.DictReader(file)

            for row in reader:
                opis_id = row.get("OPIS Truckstop ID")

                if not opis_id:
                    continue

                stations.append(
                    FuelStation(
                        opis_truckstop_id=int(
                            float(opis_id)
                        ),

                        name=self.clean(
                            row.get("Truckstop Name")
                        ),

                        address=self.clean(
                            row.get("Address")
                        ),

                        city=self.clean(
                            row.get("City")
                        ),

                        state=self.clean(
                            row.get("State")
                        ),

                        rack_id=self.parse_int(
                            row.get("Rack ID")
                        ),

                        retail_price=self.parse_float(
                            row.get("Retail Price")
                        ),

                        latitude=self.parse_float(
                            row.get("Latitude")
                        ),

                        longitude=self.parse_float(
                            row.get("Longitude")
                        ),

                        geocode_status=self.clean(
                            row.get("match_status")
                        ),

                        geocode_match_type=self.clean(
                            row.get("match_type")
                        ),
                    )
                )

        existing_count = FuelStation.objects.count()

        self.stdout.write(
            f"Deleting {existing_count} existing "
            f"fuel stations..."
        )

        FuelStation.objects.all().delete()

        FuelStation.objects.bulk_create(
            stations,
            batch_size=500
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {len(stations)} fuel stations"
            )
        )

    @staticmethod
    def clean(value):
        if value is None:
            return ""

        return str(value).strip()

    @staticmethod
    def parse_int(value):
        if value is None:
            return None

        value = str(value).strip()

        if not value:
            return None

        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def parse_float(value):
        if value is None:
            return None

        value = str(value).strip()

        if not value:
            return None

        try:
            return float(value)
        except (ValueError, TypeError):
            return None
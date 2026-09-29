import openpyxl
from django.core.management.base import BaseCommand
from routes.models import FuelStation


class Command(BaseCommand):
    help="import fuel prices into the db"

    def add_arguments(self,parser):
        parser.add_argument("file_path")

    def handle(self,*args,**options):
        file_path= options["file_path"]

        workbook=openpyxl.load_workbook(
            file_path,
            read_only=True,
            data_only=True
        )
        sheet = workbook.active
        
        stations=[]

        rows=sheet.iter_rows(
                min_row=2,
                values_only=True
            )

        for row in rows:
            if not row or row[0] is None:
                continue

            (opis_truckstop_id,
                name,
                address,
                city,
                state,
                rack_id,
                retail_price,
            )=row
           
            stations.append(
                FuelStation(

                opis_truckstop_id=int(opis_truckstop_id),
                name=str(name).strip(),
                address=str(address).strip(),
                city=str(city).strip(),
                state=str(state).strip(),
                rack_id=int(rack_id),
                retail_price=retail_price,
                )
            )

        FuelStation.objects.bulk_create(stations)
        self.stdout.write(
        self.style.SUCCESS(
            f"Imported {len(stations)} fuel stations"
        )
        )
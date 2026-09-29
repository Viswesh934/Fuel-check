from django.db import models


class FuelStation(models.Model):
    opis_truckstop_id = models.IntegerField()
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2)

    rack_id = models.IntegerField(null=True, blank=True)

    retail_price = models.DecimalField(
        max_digits=8,
        decimal_places=5
    )

    latitude = models.FloatField(
        null=True,
        blank=True
    )

    longitude = models.FloatField(
        null=True,
        blank=True
    )

    geocode_status = models.CharField(
        max_length=30,
        null=True,
        blank=True
    )

    geocode_match_type = models.CharField(
        max_length=30,
        null=True,
        blank=True
    )

    def __str__(self):
        return f"{self.name} - {self.city}, {self.state}"
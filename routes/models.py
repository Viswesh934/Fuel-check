from django.db import models

class FuelStation(models.Model):

    opis_truckstop_id= models.IntegerField()
    name= models.CharField(max_length=255)
    address= models.CharField(max_length=255)
    city= models.CharField(max_length=100)
    state=models.CharField(max_length=2)
    rack_id=models.IntegerField()
    retail_price= models.DecimalField(
        max_digits=8,
        decimal_places=5
    )
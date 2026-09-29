from rest_framework.response import Response
from rest_framework.views import APIView

from .models import FuelStation

class HealthView(APIView):
    def get(self,request):
        return Response({
            "status": "ok"
        })


class DbCheckView(APIView):
    def get(self,request):
        records= FuelStation.objects.all()

        return Response({
            "connected": True,
            "records":[{
                "id": record.id,
                "name": record.name
            }
            for record in records]
        })
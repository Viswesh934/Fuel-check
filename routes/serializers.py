from rest_framework import serializers


class OptimizeRouteSerializer(serializers.Serializer):
    start = serializers.CharField(
        required=True,
        allow_blank=False,
    )

    finish = serializers.CharField(
        required=True,
        allow_blank=False,
    )

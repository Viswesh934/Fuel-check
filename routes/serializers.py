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


class VoiceQuerySerializer(serializers.Serializer):
    query = serializers.CharField(
        required=True,
        allow_blank=False,
    )
    start = serializers.CharField(
        required=False,
        default="Chicago, IL",
    )
    finish = serializers.CharField(
        required=False,
        default="Little Rock, AR",
    )

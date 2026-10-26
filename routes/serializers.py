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

    language = serializers.CharField(
        required=False,
        default="en",
    )


class VoiceQuerySerializer(serializers.Serializer):
    query = serializers.CharField(
        required=True,
        allow_blank=False,
    )
    start = serializers.CharField(
        required=False,
        default="Delhi",
    )
    finish = serializers.CharField(
        required=False,
        default="Mumbai",
    )
    language = serializers.CharField(
        required=False,
        default="en",
    )


class VoiceTTSSerializer(serializers.Serializer):
    text = serializers.CharField(
        required=True,
        allow_blank=False,
    )
    language = serializers.CharField(
        required=False,
        default="en",
    )

from rest_framework import serializers


class TimeStampedSerializer(serializers.ModelSerializer):
    """Base serializer for timestamped models."""
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class DynamicFieldsSerializer(serializers.ModelSerializer):
    """
    A serializer that allows dynamic field selection via query params.
    Usage: ?fields=field1,field2,field3
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if 'request' in self.context:
            fields = self.context['request'].query_params.get('fields')
            if fields:
                fields = fields.split(',')
                allowed = set(fields)
                existing = set(self.fields.keys())
                for field_name in existing - allowed:
                    self.fields.pop(field_name)
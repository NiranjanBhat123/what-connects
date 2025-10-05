from rest_framework import status
from rest_framework.response import Response


class ActionSerializerMixin:
    """
    Mixin to allow different serializers for different actions.
    """
    serializer_action_classes = {}

    def get_serializer_class(self):
        try:
            return self.serializer_action_classes[self.action]
        except (KeyError, AttributeError):
            return super().get_serializer_class()


class MultipleFieldLookupMixin:
    """
    Mixin to allow lookup by multiple fields.
    """
    def get_object(self):
        queryset = self.get_queryset()
        queryset = self.filter_queryset(queryset)
        filter_kwargs = {}

        for field in self.lookup_fields:
            if self.kwargs.get(field):
                filter_kwargs[field] = self.kwargs[field]

        obj = queryset.filter(**filter_kwargs).first()
        if not obj:
            from rest_framework.exceptions import NotFound
            raise NotFound()

        self.check_object_permissions(self.request, obj)
        return obj
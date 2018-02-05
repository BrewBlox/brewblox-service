from marshmallow import fields

class ControllerData(fields.Field):
    """
    Serialize a ControllerDataField that is made of three element.
    Only outputs the actual value.
    """
    def _serialize(self, field, attr, obj):
        return field.get_actual_value()

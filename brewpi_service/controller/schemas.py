from marshmallow_polyfield import PolyField

from brewpi_service import ma

from .models import Controller, ControllerBlock


class ControllerBlockDisambiguator:
    class_to_schema = {
    }


def controller_block_schema_serialization_disambiguation(base_object, parent_obj):
    try:
        return ControllerBlockDisambiguator.class_to_schema[base_object.__class__.__name__]()
    except KeyError:
        pass

    raise TypeError("Could not detect type of {0}. "
                    "Did not have a base or a length. "
                    "Are you sure this is a Controller Block?".format(base_object.__class__))


class ControllerSchema(ma.ModelSchema):
    class Meta:
        model = Controller
        fields = ('id', 'connected', 'name', 'blocks', 'description', 'uri')

    blocks = ma.List(PolyField(
        serialization_schema_selector=controller_block_schema_serialization_disambiguation,
    ))


class ControllerBlockSchema(ma.ModelSchema):
    class Meta:
        model = ControllerBlock
        fields = ('id', 'object_id', 'name')


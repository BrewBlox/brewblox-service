from marshmallow_polyfield import PolyField

from brewpi_service import ma

from .models import Controller, ControllerDevice, ControllerLoop

class ControllerDeviceDisambiguator:
    class_to_schema = {
    }

def controller_device_schema_serialization_disambiguation(base_object, parent_obj):
    try:
        return ControllerDeviceDisambiguator.class_to_schema[base_object.__class__.__name__]()
    except KeyError:
        pass

    raise TypeError("Could not detect type of {0}. "
                    "Did not have a base or a length. "
                    "Are you sure this is a Controller Device?".format(base_object.__class__))


class ControllerLoopDisambiguator:
    class_to_schema = {
    }

def controller_loop_schema_serialization_disambiguation(base_object, parent_obj):
    try:
        return ControllerLoopDisambiguator.class_to_schema[base_object.__class__.__name__]()
    except KeyError:
        pass

    raise TypeError("Could not detect type of {0}. "
                    "Did not have a base or a length. "
                    "Are you sure this is a Controller Loop?".format(base_object.__class__))



class ControllerSchema(ma.ModelSchema):
    class Meta:
        model = Controller
        fields = ('id', 'name', 'devices', 'loops', 'description', 'uri')

    devices = ma.List(PolyField(
        serialization_schema_selector=controller_device_schema_serialization_disambiguation,
    ))

    loops = ma.List(PolyField(
        serialization_schema_selector=controller_loop_schema_serialization_disambiguation,
    ))



class ControllerDeviceSchema(ma.ModelSchema):
    class Meta:
        model = ControllerDevice
        fields = ('id', 'object_id')

class ControllerLoopSchema(ma.ModelSchema):
    class Meta:
        model = ControllerLoop
        fields = ('id', 'object_id')



# Schema instanciations
controller_schema = ControllerSchema()
controllers_schema = ControllerSchema(many=True)

controller_device_schema = ControllerDeviceSchema()
controller_devices_schema = ControllerDeviceSchema(many=True)

controller_loop_schema = ControllerLoopSchema()
controller_loops_schema = ControllerLoopSchema(many=True)


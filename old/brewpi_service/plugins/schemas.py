from brewpi_service import ma


class PluginSchema(ma.Schema):
    id = ma.String(attribute="identifier")
    url = ma.AbsoluteUrlFor('plugin_detail', id='<identifier>')
    name = ma.String()
    description = ma.String()
    author = ma.String()
    license = ma.String()
    version = ma.String()
    website = ma.String()
    enabled = ma.Boolean()


plugin_schema = PluginSchema()
plugins_schema = PluginSchema(many=True)

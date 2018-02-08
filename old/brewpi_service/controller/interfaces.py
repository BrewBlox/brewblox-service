from zope.interface import Interface, Attribute


class IBlock(Interface):
    """
    The base block, for all control blocks
    """
    name = Attribute("""Name of this block""")

Hardware communication
======================

serivce layer is source of truth

Contstructing
-------------

- application fires an object created events which represents the object and the construction parameters
- e.g. a dict containing construction values and the application id of the object 
- controlbox bridge layer listens for that event (by registering as a listener to the application layer), and propagates this to controlbox
 
Updates from Controller
-----------------------
- the controlbox bridge fires an application defined event to subscribers on an app object
- application takes care of subscribing to the event and managing the update

Changes to app state (from elsewhere in the system)
---------------------------------------------------

- app classes fires a changed event describing the change (such as a dictionary of changed fields and the id of the object)
- controlbox bridge listens for that, and propagates the change to controlbox via a masked write

Deleting
--------

- application fires an object deleted event with at least the application defined ID for the object that corresponds to the construction event
- controlbox bridge listens for that, locates the corresponding object and issues a delete request to controlbox

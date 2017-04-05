System communication overview
=============================

Proposal for communication between UI and service.

Data goes through REST interface (always)
-----------------------------------------
REST is a proven standard that any client can interact with.
It has good error handling, is well understood by developers and easy to debug.
With HTTP 2.0 there is little overhead in sending multiple requests, because the connection is left open. Each component of the UI can handle fetching its own data at the REST API.

Notifications are sent over a websocket
---------------------------------------
We cannot push from the server to the browser with REST, so we need websockets to do this.
Because we only want 1 way of handling data, the websocket message does not contain data, only a notification. The UI is responsible for fetching updated data (through REST) when the notification signals the need for that.

Considerations
--------------
Another option would be JSON-RPC over websockets, but we need to define our own verbs for this. Each client needs to know this set of verbs.
RPC is verbs driven, our application is data (resource) driven. Even actions on the controller are triggered by writing a data field with controlbox. If we are going to use JSON-RPC in a REST-like fashion (CRUD verbs), going with REST for data + notifications for events is a simpler solution.

Example
-------
The example below shows how a view of active controller can be kept up-to-data between browser and service.

This example uses React + Redux. Vue + Vuex will be similar.
The UI is rendered from the data in the redux store (one-way data binding).
Actions (with payload) are processed by the reducer and can result in a new store state. Actions can also trigger sagas for async behavior.
Sagas are used for fetching data asynchronously and dispatching actions when events occur.

Note that other than the initial trigger, the sequence diagrams for pull and push are the same.

.. seqdiag::

    seqdiag browser_service {
        // Set fontsize.
        default_fontsize = 12;

        // Do not show activity line
        activation = none;
        
        # define order of elements
        # seqdiag sorts elements by order they appear
        UI; sagas; reducer; redux-store; REST-api; websocket;
        
        === Pull ===

        UI --> sagas [label = "action:\n CTRL_UPDATE_CLICKED(id)", rightnote = "watcher triggers"];
        sagas --> sagas [note = "yield saga\n fetch_ctrl_data(id)"];
        sagas -> REST-api [label = "axios GET", rightnote = "GET /controllers/<id>"];
        sagas <- REST-api [label = "result:\n controller data"];
        sagas --> reducer [label = "dispatch action:\n CTRL_UPDATE_RECEIVED(data)", note = "reducer processes\n action + data"];
        UI <-- reducer [label = "new store state"];

        === Push ===

        websocket -> sagas [label = "noficication:\n CTRL_UPDATED(id)",
        rightnote = "new controller\n discovered in service",         leftnote = "watcher triggers"];
        sagas --> sagas [note = "yield saga\n fetch_ctrl_data(id)"];
        sagas -> REST-api [label = "axios GET", rightnote = "GET /controllers/<id>"];
        sagas <- REST-api [label = "result:\n controller data"];
        sagas --> reducer [label = "dispatch action:\n CTRL_UPDATE_RECEIVED(data)", note = "reducer processes\n action + data"];
        UI <-- reducer [label = "new store state"];
    }
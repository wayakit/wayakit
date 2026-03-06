.. _changelog:

Changelog
=========

`17.0.1.6.2`
------------

- Improved handling of "lead" events on the website.

- Add logging to console for 'update_cart', 'remove_from_cart' events.

`17.0.1.6.1`
------------

- Implement the Lead event tracking for all standard Odoo forms.

`17.0.1.6.0`
------------

- Change the tracking endpoint from "/shop/tracking_data" to "/website/tracking_data" to compatibility with third-party apps for user-friendly URLs.

- Improve the Lead event tracking on the Contact Us form.

`17.0.1.5.3`
------------

- Improve cleaning of website tracking logs by a cron.

`17.0.1.5.2`
------------

- Add methods to process URL parameters.

`17.0.1.5.1`
------------

- Improve the Begin Checkout event tracking.

`17.0.1.5.0`
------------

- Implement calling of the user data completing method in the main process.

- Improve user data getting for public users.

- Add an option to specify a partner identifier type.

- Implement the "Remove from Cart" tracking event.

- Implement the "Update the Cart" tracking event.

- Implement the "Purchase on Portal" tracking event.

`17.0.1.4.6`
------------

- Add the default app filter.

`17.0.1.4.5`
------------

- Add the action to send logs by API from the log list.

`17.0.1.4.4`
------------

- Add an option to hash the "Street" user data.

- Implement a logic to check available user tracking fields to activate.

- Add API fields to make them common.

`17.0.1.4.3`
------------

- Put the "IP address" and "User Agent" fields to the tracking log form.

- Improve the method to get user data.

`17.0.1.4.2`
------------

- Add user names and options to hash or not users' name, email, phone.

`17.0.1.4.1`
------------

- Improve product IDs tracking.

`17.0.1.4.0`
------------

- Add user fields for the advanced matching: zip, street, state.

- Improve the service view form.

`17.0.1.3.4`
------------

- Add alternative product IDs to webpages: Product List, Product Page.

`17.0.1.3.3`
------------

- Improve the method to get an user data.

`17.0.1.3.2`
------------

- Add checking of deleted sale orders.

`17.0.1.3.1`
------------

- Improve the tracking log list view.

`17.0.1.3.0`
------------

- Improve the form of tracking services.

- Add the Tracking Event model for custom events.

- Improve the tracking event "Add Payment Info".

`17.0.1.2.0`
------------

- Add an option to delete tracking logs completely after some period.

- Add logic to get customer data from the last order.

- Add a method to determine to do an internal logging or not.

`17.0.1.1.0`
------------

- Add a logic to deny sending tracking data by API.

- Add grouping by "State" for tracking logs.

- Add visitor country fields to tracking logs.

- Add the config parameter "Clean Up Period for Internal Tracking Logs" to clean up the sensitive visitor data from internal logs.

- Add option to get customer data from sale orders.

- Add the filter "Today" for tracking logs.

`17.0.1.0.0`
------------

- Migration from 16.0.



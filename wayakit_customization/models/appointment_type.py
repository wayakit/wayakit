from odoo import models, fields
from datetime import datetime, timedelta
import requests
import logging

_logger = logging.getLogger(__name__)

class AppointmentType(models.Model):
    _inherit = 'appointment.type'

    api_service = fields.Boolean(string="Api Service")
    api_description = fields.Text(string="Description")
    service_type = fields.Many2many('service.type' , string="Service Types")
    # reminder_featureName = fields.Char()
    reminder_notification_title = fields.Char()
    reminder_notification_body = fields.Text()
    # completion_featureName = fields.Char()
    completion_notification_title = fields.Char()
    completion_notification_body = fields.Text()

    def status_notification_update(self):
        token = self.env['ir.config_parameter'].sudo().get_param('wayakit_customization.notification_token')
        url = self.env['ir.config_parameter'].sudo().get_param('wayakit_customization.notification_url')
        if token and url:
            current_datetime = fields.Datetime.now()
            print('current_datetime')
            from_datetime = current_datetime - timedelta(minutes=7)
            to_datetime = current_datetime + timedelta(minutes=7)
            Appointments = self.search([('api_service', '=', True)])
            for appointment in Appointments:
                events_reminder = appointment.meeting_ids.filtered(lambda x: not x.reminder_notification)
                reminder_kaust_id = []
                reminder_event_ids = []
                completion_kaust_id = []
                completion_event_ids = []
                for event in events_reminder:
                    start = event.start - timedelta(hours=1)
                    if from_datetime <= start <= to_datetime:
                        reminder_kaust_id.append(event.appointment_booker_id.customer_kaust_id) if event.appointment_booker_id else None
                        reminder_event_ids.append(event.id)
                events_completion = appointment.meeting_ids.filtered(lambda x: x.reminder_notification and not x.completion_notification)
                for events_compl in events_completion:
                    if events_compl.stop <= current_datetime:
                        completion_kaust_id.append(events_compl.appointment_booker_id.customer_kaust_id) if event.appointment_booker_id else None
                        completion_event_ids.append(event.id)
                if reminder_kaust_id:
                    data = self.prepare_notification_api_values(appointment.reminder_notification_title,
                                                                appointment.reminder_notification_body,
                                                                reminder_kaust_id)
                    response = self.status_update_notification_api(url, token, data)
                    if response:
                        reminder_events = self.env['calendar.event'].browse(reminder_event_ids)
                        reminder_events.write({'reminder_notification': True})

                if completion_kaust_id:
                    data = self.prepare_notification_api_values(appointment.completion_notification_title,
                                                                appointment.completion_notification_body,
                                                                completion_kaust_id)
                    response = self.status_update_notification_api(url, token, data)
                    if response:
                        completion_events = self.env['calendar.event'].browse(completion_event_ids)
                        completion_events.write({'completion_notification': True})


    def prepare_notification_api_values(self, title, body, kaust_id):
        return{
            "featureName": "My GA",
            "kaustId": kaust_id,
            "userCodes": [],
            "notificationTitle": title,
            "notificationBody": body
        }

    def status_update_notification_api(self, url, token, data):
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer" + " " + token
        }
        print(data)
        try:
            response = requests.post(url, headers=headers, json=data)
            data = response.json()
            print('response:')
            print(data)
            if data.get('status') == 200:
                return True
        except Exception as e:
            _logger.error('Notification Update Error: %s', e)
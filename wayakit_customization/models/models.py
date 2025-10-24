# import json
# import logging
# import binascii
#
# from base64 import b64decode
#
# from odoo import api, models
#
# from cryptography import x509
# from cryptography.hazmat.backends import default_backend
#
# _logger = logging.getLogger(__name__)
#
#
# class AccountJournal(models.Model):
#     _inherit = "account.journal"
#
#     # Override to make the compute resilient and log what we got.
#     @api.depends('l10n_sa_production_csid_json')
#     def _l10n_sa_compute_production_csid_validity(self):
#         """
#         Compute the expiration date of the Production certificate (PCSID)
#         without crashing when ZATCA returns an error payload.
#         """
#         for journal in self:
#             journal.l10n_sa_production_csid_validity = False
#             raw = journal.sudo().l10n_sa_production_csid_json
#             if not raw:
#                 continue
#
#             # Parse JSON safely
#             try:
#                 data = raw if isinstance(raw, dict) else json.loads(raw)
#             except Exception:
#                 _logger.exception(
#                     "[PCSID] Invalid JSON in l10n_sa_production_csid_json "
#                     "for journal %s (id=%s): %r",
#                     journal.display_name, journal.id, raw[:500]
#                 )
#                 continue
#
#             # Log the raw payload for debugging
#             _logger.warning("[PCSID] Raw payload for journal %s (id=%s): %s",
#                             journal.display_name, journal.id, json.dumps(data)[:5000])
#
#             # Use our robust decoder below
#             journal.l10n_sa_production_csid_validity = self._l10n_sa_get_pcsid_validity(data)
#
#     # Override to gracefully handle error payloads and different encodings.
#     def _l10n_sa_get_pcsid_validity(self, data):
#         """
#         Return PCSID expiry datetime (naive) or False if not available.
#         Accepts success payloads only; ignores error payloads.
#         """
#         # 1) Guard: ensure dict
#         if not isinstance(data, dict):
#             try:
#                 data = json.loads(data or "{}")
#             except Exception:
#                 _logger.error("[PCSID] Could not parse data to JSON dict: %r", data)
#                 return False
#
#         # 2) ZATCA error payloads do not contain 'binarySecurityToken'
#         token = data.get("binarySecurityToken")
#         if not token:
#             # Log common error fields if present
#             err_code = data.get("errorCode") or data.get("code")
#             err_msg = data.get("message") or data.get("detail") or data.get("error")
#             _logger.error(
#                 "[PCSID] No binarySecurityToken in payload. errorCode=%r message=%r payload_keys=%s",
#                 err_code, err_msg, list(data.keys())
#             )
#             return False
#
#         # 3) Try to load certificate from token (handle DER, PEM, and base64-of-base64)
#         cert = None
#         try:
#             first = b64decode(token)
#             if b"-----BEGIN CERTIFICATE-----" in first:
#                 cert = x509.load_pem_x509_certificate(first, default_backend())
#             else:
#                 # Sometimes it's base64-of-base64. Try a second decode if possible.
#                 try:
#                     second = b64decode(first.decode())
#                     cert = x509.load_der_x509_certificate(second, default_backend())
#                 except (binascii.Error, UnicodeDecodeError):
#                     # Assume first is DER
#                     cert = x509.load_der_x509_certificate(first, default_backend())
#         except Exception:
#             _logger.exception("[PCSID] Failed to decode/load certificate from token")
#             return False
#
#         # 4) Normalize notValidAfter across cryptography versions
#         try:
#             not_after = cert.not_valid_after_utc.replace(tzinfo=None)  # cryptography >= 42
#         except AttributeError:
#             not_after = cert.not_valid_after
#
#         _logger.info("[PCSID] Certificate not_valid_after: %s", not_after)
#         return not_after

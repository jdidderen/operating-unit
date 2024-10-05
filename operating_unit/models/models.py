# Copyright 2024-TODAY Jérémy Didderen
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

from odoo import models
import logging
_logger = logging.getLogger(__name__)

class BaseModel(models.AbstractModel):
    _inherit = "base"

    _check_operating_unit_auto = False

    def write(self, vals):
        if not self:
            return True

        check_operating_unit = False
        for field_name, value in vals.items():
            field = self._fields.get(field_name)
            if not field:
                raise ValueError("Invalid field %r on model %r" % (field_name, self._name))
            if field_name == 'operating_unit_id' or (hasattr(field, "check_operating_unit") and field.relational and field.check_operating_unit):
                check_operating_unit = True
        if check_operating_unit and self._check_operating_unit_auto:
            self._check_operating_unit()
        return super().write(vals)

    def to_operating_unit_ids(self, operating_unit_ids):
        if isinstance(operating_unit_ids, BaseModel):
            return operating_unit_ids.ids
        elif isinstance(operating_unit_ids, (list, tuple)):
            return operating_unit_ids
        return [operating_unit_ids]

    def _check_operating_unit_domain(self, operating_units):
        if not operating_units:
            return [('operating_unit_id', '=', False)]
        return ['|', ('company_id', '=', False), ('company_id', 'in', self.to_operating_unit_ids(operating_units))]

    def _check_operating_unit(self, field_names=None):
        if field_names is None or 'operating_unit_id' in field_names:
            field_names = self._fields

        regular_fields = []
        property_fields = []
        for name in field_names:
            field = self._fields[name]
            if hasattr(field, "check_operating_unit") and field.relational and field.check_operating_unit and \
                ('operating_unit_id' in self.env[field.comodel_name] or 'operating_unit_ids' in self.env[field.comodel_name]):
                if not field.company_dependent:
                    regular_fields.append(name)
                else:
                    property_fields.append(name)

        if not (regular_fields or property_fields):
            return

        inconsistencies = []
        for record in self:
            if record._name == "operating.unit":
                operating_unit_ids = record
            elif hasattr(record, "operating_unit_ids"):
                operating_unit_ids = record.operating_unit_ids
            else:
                operating_unit_ids = record.operating_unit_id
            for name in regular_fields:
                corecord = record.sudo()[name]
                if corecord:
                    domain = corecord._check_operating_unit_domain(operating_unit_ids)
                    if domain and not corecord.with_context(active_test=False).filtered_domain(domain):
                        inconsistencies.append((record, name, corecord))
            company = self.env.company
            for name in property_fields:
                corecord = record.sudo()[name]
                if corecord:
                    domain = corecord._check_company_domain(company)
                    if domain and not corecord.with_context(active_test=False).filtered_domain(domain):
                        inconsistencies.append((record, name, corecord))

        if inconsistencies:
            lines = [_("Incompatible companies on records:")]
            company_msg = _lt("- Record is company %(company)r and %(field)r (%(fname)s: %(values)s) belongs to another company.")
            record_msg = _lt("- %(record)r belongs to company %(company)r and %(field)r (%(fname)s: %(values)s) belongs to another company.")
            root_company_msg = _lt("- Only a root company can be set on %(record)r. Currently set to %(company)r")
            for record, name, corecords in inconsistencies[:5]:
                if record._name == 'res.company':
                    msg, company = company_msg, record
                elif record == corecords and name == 'company_id':
                    msg, company = root_company_msg, record.company_id
                else:
                    msg, company = record_msg, record.company_id
                field = self.env['ir.model.fields']._get(self._name, name)
                lines.append(str(msg) % {
                    'record': record.display_name,
                    'company': company.display_name,
                    'field': field.field_description,
                    'fname': field.name,
                    'values': ", ".join(repr(rec.display_name) for rec in corecords),
                })
            raise UserError("\n".join(lines))

    def _valid_field_parameter(self, field, name):
        extra_params = ("check_operating_unit",)
        return name in extra_params or super()._valid_field_parameter(field, name)

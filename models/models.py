from odoo import models, fields, api, _
import time
import logging
import odoo.addons.decimal_precision as dp
from datetime import datetime, timedelta
from odoo.exceptions import UserError

STATES = [('draft', 'Draft'), ('open', 'Open'),
          ('close', 'Close'), ('reject', 'Reject')]


class vit_bilyet_giro(models.Model):
    _name = "vit.vit_bilyet_giro"

    def _get_invoices(self):
        results = {}
        for giro in self:
            results[giro.id] = ""
            for gi in giro.giro_invoice_ids:
                results[giro.id] += "%s " % (gi.invoice_id.number or "")
        return results

    name = fields.Char(string="Number", help="Nomor Giro",
                       required=True, states={'draft': [('readonly', False)]})
    due_date = fields.Date(string="Due Date", required=True, readonly=True, states={
                               'draft': [('readonly', False)]})
    receive_date = fields.Date(string="Receive Date", readonly=True, required=True,states={
                                   'draft': [('readonly', False)]})
    submit_date = fields.Date(string="Submit Date", readonly=True, states={
                                   'draft': [('readonly', False)]})
    clearing_date = fields.Datetime(string="Clearing Date", readonly=True, states={
                                    'draft': [('readonly', True)]})
    amount = fields.Float(string="Amount", readonly=True, states={
                          'draft': [('readonly', False)]})
    partner_id = fields.Many2one(comodel_name="res.partner", string="Partner", readonly=True, states={
                                 'draft': [('readonly', False)]})
    journal_id = fields.Many2one(comodel_name="account.journal", string="Bank Journal", domain=[
                                 ('type', '=', 'bank')], readonly=True, states={'draft': [('readonly', False)]})
    giro_invoice_ids = fields.One2many(comodel_name="vit_giro_invoice", inverse_name="giro_id", readonly=True, states={
                                       'draft': [('readonly', False)]})
    invoice_names = fields.Char(
        string="Allocated Invoices", compute='_get_invoices')
    type = fields.Selection([('payment', 'Payment'), ('receipt', 'Receipt')], default='payment',
                            string="Type", readonly=True, required=True, states={'draft': [('readonly', False)]})
    invoice_type = fields.Char(string="Invoice Type", default='in_invoice', readonly=True, states={
                               'draft': [('readonly', False)]})
    state = fields.Selection(string="State", selection=STATES,
                             required=True, readonly=True, default=STATES[0][0])
    param_id = fields.Many2one(comodel_name="vit.vit_config_giro", string="Submit Term", required=True, states={'draft':[('readonly', False)]})
    _sql_constraints = [('name_uniq', 'unique(name)',
                         _('Nomor Giro tidak boleh sama'))]
                         
    @api.multi
    def _cek_total(self):
        inv_total = 0.0
        for giro in self:
            for gi in giro.giro_invoice_ids:
                inv_total += gi.amount
            if giro.amount == inv_total:
                return True
        return False
    
    _constraints = [(_cek_total, _(
        'Total amount allocated for the invoices must be the same as total Giro amount'), ['amount'])]
        
    @api.multi
    def action_cancel(self):
        self.write({'state': STATES[0][0]})

    @api.multi
    def action_confirm(self):
        due_date = str(self.due_date)
        receive_date = str(self.receive_date)
        # start = datetime.strptime(due_date, '%Y-%m-%d %H:%M:%S')
        # sub = datetime.strptime(receive_date, '%Y-%m-%d %H:%M:%S')
        # end = self.param_id.search([('id','=', 1)])
        # par = start-sub
        # print(int(end.name_parameter))
        # print('=========================')
        # if (str(par)[0:3]) <= (str(end.name_parameter)) :
        if due_date <= receive_date :
            raise UserError(_('Tanggal Due Date harus lebih besar dari tanggal Receive Date'))

        # self.write({'state': STATES[1][0], 'submit_date': (start - timedelta(days=end.name_parameter))})
        self.write({'state': STATES[1][0]})
        

    @api.multi
    def action_clearing(self):
        for giro in self:
            payment = giro.env['account.payment']
            company_id = giro._context.get(
                'company_id', giro.env.user.company_id.id)
            if giro.type == 'payment':
                pay_type = 'outbound'
                partner_type = 'supplier'
                payment_method = giro.journal_id.outbound_payment_method_ids.id
            else:
                pay_type = 'inbound'
                partner_type = 'customer'
                payment_method = giro.journal_id.inbound_payment_method_ids.id

            payment_id = payment.create({
                'payment_type': pay_type,
                'partner_id': giro.partner_id.id,
                'partner_type': partner_type,
                'journal_id': giro.journal_id.id,
                'amount': giro.amount,
                'communication': 'Payment giro ' + self.name,
                'company_id': company_id,
                'payment_method_id': payment_method,

            })
            payment.browse(payment_id.id).post()
            self.write({'state': STATES[2][0], 'clearing_date': time.strftime("%Y-%m-%d %H:%M:%S")})

    @api.multi
    def action_reject(self):
        self.write({'state': STATES[3][0]})

    @api.onchange('type')
    def on_change_type(self):
        inv_type = 'in_invoice'
        if self.type == 'payment':
            inv_type = 'in_invoice'
        elif self.type == 'receipt':
            inv_type = 'out_invoice'
        self.invoice_type = inv_type

    @api.onchange('due_date')
    def on_change_submit_date(self):
        if self.due_date != False:
            due_date = str(self.due_date)
            # start = datetime.strptime(due_date, '%Y-%m-%d %H:%M:%S')
            start = datetime.strptime(due_date, '%Y-%m-%d').date()
            end = self.param_id
            self.submit_date = (start - timedelta(days=end.term))

class vit_config_giro(models.Model):
    _name = "vit.vit_config_giro"

    name = fields.Char(string="Name", help="Nama Submit term",
                       required=True)
    term = fields.Integer(string="Term", help="parameter", required=True)
    category = fields.Char(string="Type", readonly=True, default='Days')

class vit_giro_invoice(models.Model):
    _name = "vit_giro_invoice"

    giro_id = fields.Many2one(
        comodel_name="vit.vit_bilyet_giro", string="Giro")
    invoice_id = fields.Many2one(comodel_name="account.invoice", string="Invoice",
                                 help="Invoice to be paid", domain=[('state', '=', 'open')])
    amount_invoice = fields.Float(string="Invoice Amount")
    amount = fields.Float(string="Amount Allocated")

    @api.onchange('invoice_id')
    def on_change_invoice_id(self):
        self.amount_invoice = self.invoice_id.residual


class account_invoice(models.Model):
    _name = "account.invoice"
    _inherit = 'account.invoice'

    giro_invoice_ids = fields.One2many(
        comodel_name="vit_giro_invoice", inverse_name="invoice_id", string="Giro")

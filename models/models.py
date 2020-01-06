from odoo import models, fields, api, _
import time
import logging
import odoo.addons.decimal_precision as dp
import datetime

STATES = [('draft', 'Draft'), ('open', 'Open'), ('close', 'Close'), ('reject', 'Reject')]

class vit_bilyet_giro(models.Model):
    _name = "vit.vit_bilyet_giro"

    name = fields.Char(string="Number", help="Nomor Giro", readonly=True, states={'draft':[('readonly', True)]})
    due_date = fields.Date(string="Due Date", readonly=True, states={'draft':[('readonly', False)]})
    receive_date = fields.Date(string="Receive Date", readonly=True, states={'draft':[('readonly', False)]})
    clearing_date = fields.Datetime(string="Clearing Date", readonly=True, states={'draft':[('readonly', True)]})
    amount = fields.Float(string="Amount", readonly=True, states={'draft':[('readonly', False)]})
    partner_id = fields.Many2one(comodel_name="res.partner", string="Partner", readonly=True, states={'draft':[('readonly', False)]})
    journal_id = fields.Many2one(comodel_name="account.journal", string="Bank Journal", domain=[('type', '=', 'bank')], readonly=True, states={'draft':[('readonly', False)]})
    giro_invoice_ids = fields.One2many(comodel_name="vit.giro_invoice", inverse_name="giro_id", readonly=True, states={'draft':[('readonly', False)]})
    invoice_names = fields.Char(string="Allocated Invoices", compute='_get_invoices')
    type = fields.Selection([('payment','Payment'),('receipt','Receipt')], string="Type", readonly=True, required=True, states={'draft':[('readonly', False)]})
    invoice_type = fields.Char(string="Invoice Type", readonly=True, states={'draft':[('readonly', False)]})
    state = fields.Selection(string="State", selection=STATES, required=True, readonly=True, default=STATES[0][0])
    # _sql_constraints = [('name_uniq', 'unique(name)', _('Nomor Giro tidak boleh sama'))]
    
    @api.depends
    def _get_invoices(self):
        results = {}
        for giro in self.env():
            results[giro.id] = ""
            for gi in giro.giro_invoice_ids:
                results[giro.id] += "%s " % (gi.invoice_id.number or "")
        return results
    
    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('vit.vit_bilyet_giro')
        return super(vit_bilyet_giro, self).create(vals)
    
    @api.multi
    def _cek_total(self):
        inv_total = 0.0
        for giro in self.env():
            for gi in giro.giro_invoice_ids:
                inv_total += gi.amount
            if giro.amount == inv_total:
                return True
        return False
    # _constraints = [(_cek_total, _('Total amount allocated for the invoices must be the same as total Giro amount'), ['amount'])]
    _defaults = {
        'state': STATES[0][0],
        'receive_date': time.strftime("%Y-%m-%d %H:%M:%S"),
        'type': 'payment',
        'inv_type': 'in_invoice',
    }
    
    @api.multi
    def action_cancel(self):
        self.write({'state': STATES[0][0]})
        
    @api.multi
    def action_confirm(self):
        self.write({'state': STATES[1][0]})
        
    @api.multi
    def action_clearing(self):     
        voucher_obj = self.env['account.voucher']
        users_obj = self.env['res.users']
        company_id = users_obj.company_id.id
        # print(users_obj.company_id.name)
        # print("===================")
        
        for giro in self:
            for gi in giro.giro_invoice_ids:
                invoice_id = gi.invoice_id
                partner_id = giro.partner_id.id
                amount = gi.amount
                journal_id = giro.journal_id
                type = giro.type
                name = giro.name
                vid = voucher_obj.create_payment()
                # voucher_obj.payment_confirm()        
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

class vit_giro_invoice(models.Model):
    _name = "vit.giro_invoice"
    
    giro_id = fields.Many2one(comodel_name="vit.vit_bilyet_giro", string="Giro")
    invoice_id = fields.Many2one(comodel_name="account.invoice", string="Invoice", help="Invoice to be paid", domain=[('state', '=', 'open')])
    amount_invoice = fields.Float(string="Invoice Amount")
    amount = fields.Float(string="Amount Allocated")
    
    @api.onchange('invoice_id')
    def on_change_invoice_id(self):
        self.amount_invoice = self.invoice_id.residual
        
class account_invoice(models.Model):
    _name = "account.invoice"
    _inherit = 'account.invoice'
    
    giro_invoice_ids = fields.One2many(comodel_name="vit.giro_invoice", inverse_name="invoice_id", string="Giro")
